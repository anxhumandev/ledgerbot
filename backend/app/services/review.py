"""Match Review: persistent review cases for record pairs the engine will not decide alone.

Cases come from two places:
- the certified review band (calibrated p between the auto-reject and auto-merge thresholds at the current α), and
- supplier ingestion, when an imported listing is ambiguous against an existing property.

A decision is validated, version-checked (optimistic concurrency), applied to the canonical catalog as a merge or a
split, persisted with actor, time and reason, and written to the audit log. Re-sending the same Idempotency-Key
returns the original response instead of deciding twice. Re-opening a case undoes its catalog change.

The pipeline build resolved every band pair with a *simulated* reviewer so that the catalog is complete; each case
therefore shows the current provisional mapping, and a human decision overrides it.
"""
from __future__ import annotations

import hashlib

from app import audit, store
from app.demo import DEMO
from app.errors import ApiError
from app.services import analyst, catalog
from app.services.views import explain_records, record_view

DECISIONS = {"confirm": "confirmed", "reject": "rejected", "escalate": "escalated"}
OPEN_STATES = ("open", "escalated")


def case_id(a: str, b: str) -> str:
    return "RC-" + hashlib.sha1(f"{a}|{b}".encode()).hexdigest()[:8].upper()


def priority_of(p: float, a: str, b: str) -> str:
    stars = max((DEMO.rec_by_id.get(r, {}).get("stars") or 0) for r in (a, b))
    if abs(p - 0.5) < 0.12 or stars >= 5:
        return "high"
    if abs(p - 0.5) < 0.3:
        return "medium"
    return "low"


def sync_cases() -> int:
    """Create cases for every pair in the current review band (idempotent)."""
    now, added = store.now(), 0
    for a, b, p in analyst._queue_pairs():
        cur = store.execute("INSERT OR IGNORE INTO review_cases(id, pair_key, record_a, record_b, p, priority, source, status, "
                            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (case_id(a, b), f"{a}|{b}", a, b, p, priority_of(p, a, b), "review_band", "open", now, now))
        added += cur.rowcount
    return added


def create_case(a: str, b: str, p: float, source: str, actor="system") -> str:
    cid = case_id(a, b)
    now = store.now()
    cur = store.execute("INSERT OR IGNORE INTO review_cases(id, pair_key, record_a, record_b, p, priority, source, status, created_at, "
                        "updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (cid, f"{a}|{b}", a, b, p, priority_of(p, a, b), source, "open", now, now))
    if cur.rowcount:
        audit.record(actor, "review.case_created", "review_case", cid, after={"record_a": a, "record_b": b, "p": round(p, 4), "source": source})
    return cid


def _band_keys() -> set[str]:
    return {f"{a}|{b}" for a, b, _ in analyst._queue_pairs()}


def _mapping(a: str, b: str) -> dict:
    ta, tb = DEMO.record_cluster.get(a), DEMO.record_cluster.get(b)
    same = ta is not None and ta == tb
    conflict = []
    if not same and ta in DEMO.hotels and tb in DEMO.hotels:
        conflict = sorted({catalog.supplier_of(r) for r in catalog.primaries(DEMO.hotels[ta])}
                          & {catalog.supplier_of(r) for r in catalog.primaries(DEMO.hotels[tb])})
    return {"same_property": same, "property_a": ta, "property_b": tb,
            "property_a_name": DEMO.hotels.get(ta, {}).get("name"), "property_b_name": DEMO.hotels.get(tb, {}).get("name"),
            "merge_conflict_suppliers": conflict}


def _summary(r: dict, band: set[str], names: dict) -> dict:
    a, b = r["record_a"], r["record_b"]
    ra, rb = DEMO.rec_by_id.get(a, {}), DEMO.rec_by_id.get(b, {})
    return {"id": r["id"], "status": r["status"], "priority": r["priority"], "source": r["source"], "p": round(r["p"], 4),
            "record_a": a, "record_b": b, "name_a": ra.get("name"), "name_b": rb.get("name"),
            "supplier_a": ra.get("supplier"), "supplier_b": rb.get("supplier"),
            "city": catalog.city_name(DEMO.norm_by_id.get(a, {}).get("city", "")), "match_type": "Hotel property",
            "assignee": r["assignee"], "assignee_name": names.get(r["assignee"]), "in_band": r["pair_key"] in band,
            "created_at": r["created_at"], "updated_at": r["updated_at"], "decided_by": r["decided_by"],
            "decided_by_name": names.get(r["decided_by"]), "decided_at": r["decided_at"], "version": r["version"],
            "mapping": _mapping(a, b)}


def list_cases(status: str = "open", priority: str = "", assignee: str = "", q: str = "", source: str = "",
               page: int = 1, page_size: int = 50) -> dict:
    where, params = [], []
    if status and status != "all":
        st = status.split(",")
        where.append(f"status IN ({','.join('?' * len(st))})")
        params += st
    if priority:
        where.append("priority = ?")
        params.append(priority)
    if source:
        where.append("source = ?")
        params.append(source)
    if assignee == "unassigned":
        where.append("assignee IS NULL")
    elif assignee:
        where.append("assignee = ?")
        params.append(assignee)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    rows = store.query(f"SELECT * FROM review_cases {clause}", params)
    band = _band_keys()
    names = {u["id"]: u["name"] for u in store.query("SELECT id, name FROM users")}
    items = [_summary(r, band, names) for r in rows if r["record_a"] in DEMO.rec_by_id and r["record_b"] in DEMO.rec_by_id]
    if q:
        ql = q.lower()
        items = [i for i in items if ql in (i["name_a"] or "").lower() or ql in (i["name_b"] or "").lower() or ql in i["id"].lower()]
    pr = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda i: (i["status"] != "escalated" and i["status"] != "open", pr.get(i["priority"], 3), abs(i["p"] - 0.5), i["id"]))
    counts = {r["status"]: r["n"] for r in store.query("SELECT status, COUNT(*) AS n FROM review_cases GROUP BY status")}
    total = len(items)
    start = (max(page, 1) - 1) * page_size
    return {"items": items[start:start + page_size], "total": total, "page": page, "page_size": page_size, "counts": counts}


def _get(cid: str) -> dict:
    r = store.one("SELECT * FROM review_cases WHERE id = ?", (cid,))
    if not r:
        raise ApiError(404, "not_found", f"Review case {cid} does not exist.")
    return r


def get_case(cid: str) -> dict:
    r = _get(cid)
    a, b = r["record_a"], r["record_b"]
    if a not in DEMO.rec_by_id or b not in DEMO.rec_by_id:
        raise ApiError(410, "gone", "A record in this case is no longer in the catalog.")
    names = {u["id"]: u["name"] for u in store.query("SELECT id, name FROM users")}
    A, B = record_view(a), record_view(b)
    ex = explain_records(a, b)
    notes = store.query("SELECT * FROM review_notes WHERE case_id = ? ORDER BY created_at", (cid,))
    return {**_summary(r, _band_keys(), names), "a": A, "b": B, "diffs": analyst._diffs(A, B), "explain": ex,
            "decision_reason": r["decision_reason"], "mutation_id": r["mutation_id"],
            "policy": {"alpha": DEMO.alpha, "tau_accept": DEMO.current_risk.get("tau_accept"),
                       "tau_reject": DEMO.current_risk.get("tau_reject"), "band": ex["band"],
                       "certified": DEMO.current_risk.get("certifiable", True)},
            "notes": [{**n, "author_name": names.get(n["author"], n["author"])} for n in notes],
            "history": audit.for_entity("review_case", cid)}


def decide(cid: str, decision: str, reason: str, version: int, user, idem_key: str | None = None) -> dict:
    if decision not in DECISIONS:
        raise ApiError(422, "invalid_value", "Decision must be confirm, reject or escalate.", {"field": "decision"})
    reason = (reason or "").strip()
    if decision in ("reject", "escalate") and len(reason) < 3:
        raise ApiError(422, "invalid_value", "Give a short reason for this decision.", {"field": "reason"})
    if idem_key:
        prev = store.one("SELECT response FROM idempotency WHERE key = ?", (f"{user.id}:{idem_key}",))
        if prev:
            return store.loads(prev["response"])
    with DEMO.lock:
        r = _get(cid)
        if r["status"] not in OPEN_STATES:
            raise ApiError(409, "already_decided", f"This case was already {r['status']} by {r['decided_by'] or 'someone'}.",
                           {"status": r["status"], "version": r["version"]})
        if r["version"] != version:
            raise ApiError(409, "stale_version", "This case changed since you opened it. Reload to see the latest state.",
                           {"version": r["version"]})
        a, b = r["record_a"], r["record_b"]
        before = _mapping(a, b)
        mutation = None
        if decision == "confirm" and not before["same_property"]:
            mutation = catalog.commit("merge", {"record_a": a, "record_b": b, "case_id": cid}, user, "review")
        elif decision == "reject" and before["same_property"]:
            mutation = catalog.commit("split", {"record_a": a, "record_b": b, "case_id": cid}, user, "review")
        now = store.now()
        cur = store.execute("UPDATE review_cases SET status = ?, decided_by = ?, decided_at = ?, decision_reason = ?, mutation_id = ?, "
                            "updated_at = ?, version = version + 1 WHERE id = ? AND version = ?",
                            (DECISIONS[decision], user.id, now, reason or None, mutation["mutation_id"] if mutation else None, now, cid, version))
        if cur.rowcount != 1:  # lost a race after the catalog change: undo it
            if mutation:
                catalog.deactivate(mutation["mutation_id"])
            raise ApiError(409, "stale_version", "Another analyst decided this case at the same moment. Reload.")
        after = _mapping(a, b)
        audit.record(user, f"review.{DECISIONS[decision]}", "review_case", cid,
                     before={"status": r["status"], **before}, after={"status": DECISIONS[decision], **after}, reason=reason or None)
        for tid in {before["property_a"], before["property_b"], after["property_a"], after["property_b"]} - {None}:
            if mutation:
                audit.record(user, "catalog.mapping_changed", "hotel", tid, before={"same_property": before["same_property"]},
                             after={"same_property": after["same_property"], "case_id": cid}, reason=reason or None)
    resp = {"case": get_case(cid), "catalog_change": mutation}
    if idem_key:
        store.execute("INSERT OR IGNORE INTO idempotency(key, response, created_at) VALUES (?,?,?)",
                      (f"{user.id}:{idem_key}", store.dumps(resp), store.now()))
    return resp


def reopen(cid: str, reason: str, user) -> dict:
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise ApiError(422, "invalid_value", "Say why this decision is being corrected.", {"field": "reason"})
    with DEMO.lock:
        r = _get(cid)
        if r["status"] == "open":
            raise ApiError(409, "not_decided", "This case is already open.")
        before = _mapping(r["record_a"], r["record_b"])
        if r["mutation_id"]:
            catalog.deactivate(r["mutation_id"])
        store.execute("UPDATE review_cases SET status = 'open', decided_by = NULL, decided_at = NULL, decision_reason = NULL, "
                      "mutation_id = NULL, updated_at = ?, version = version + 1 WHERE id = ?", (store.now(), cid))
        audit.record(user, "review.reopened", "review_case", cid, before={"status": r["status"], **before},
                     after={"status": "open", **_mapping(r["record_a"], r["record_b"])}, reason=reason)
    return get_case(cid)


def assign(cid: str, assignee: str | None, user) -> dict:
    r = _get(cid)
    if assignee and not store.one("SELECT 1 AS x FROM users WHERE id = ?", (assignee,)):
        raise ApiError(422, "invalid_value", "Unknown user.", {"field": "assignee"})
    store.execute("UPDATE review_cases SET assignee = ?, updated_at = ?, version = version + 1 WHERE id = ?", (assignee, store.now(), cid))
    audit.record(user, "review.assigned", "review_case", cid, before={"assignee": r["assignee"]}, after={"assignee": assignee})
    return get_case(cid)


def add_note(cid: str, body: str, user) -> dict:
    _get(cid)
    body = (body or "").strip()
    if not 1 <= len(body) <= 2000:
        raise ApiError(422, "invalid_value", "Notes must be 1–2000 characters.", {"field": "body"})
    store.execute("INSERT INTO review_notes(case_id, author, body, created_at) VALUES (?,?,?,?)", (cid, user.id, body, store.now()))
    audit.record(user, "review.note_added", "review_case", cid, after={"note": body[:200]})
    return get_case(cid)


def stats() -> dict:
    rows = store.query("SELECT status, decided_at, created_at, decided_by FROM review_cases")
    decided = [r for r in rows if r["decided_at"]]
    return {"open": sum(r["status"] == "open" for r in rows), "escalated": sum(r["status"] == "escalated" for r in rows),
            "confirmed": sum(r["status"] == "confirmed" for r in rows), "rejected": sum(r["status"] == "rejected" for r in rows),
            "decided": len(decided), "total": len(rows)}
