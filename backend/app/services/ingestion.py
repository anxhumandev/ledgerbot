"""Supplier ingestion: validate a feed file, preview it, then run it through the real matching pipeline as a job.

Accepted formats
- JSON: {"hotels": [...], "rooms": [...], "offers": [...]}, the format of the bundled NovaBeds feed. Rooms and offers
  are optional; they matter for Dubai properties, where rooms and rates are modelled.
- CSV: one hotel per row with columns record_id,name,address,phone,lat,lng,stars,city.

Each valid hotel is normalised, embedded, blocked against the catalog and scored by the calibrated matcher. The
certified thresholds decide: attach to an existing property (auto-merge), create a new property (auto-reject), or
create a new property *and* a review case when the evidence is ambiguous or the property already lists this supplier.
Every applied record is a catalog mutation, so imports survive restarts and show up in the audit log.
A job only reports "completed" after every record has been processed and persisted.
"""
from __future__ import annotations

import csv
import io
import math
import threading
import traceback
import uuid

import orjson

from app import audit, config, store
from app.demo import DEMO
from app.errors import ApiError
from app.pipeline import adjudicator, blocking, normalize
from app.services import catalog, review, settings_svc

HOTEL_FIELDS = ["record_id", "name", "address", "phone", "lat", "lng", "stars", "city"]
KNOWN_CITIES = {"dubai", "abu_dhabi", "singapore", "bangkok", "bali"}
_RUNNING: dict[str, threading.Thread] = {}


def _issue(row, rid, field, severity, message):
    return {"row": row, "record_id": rid, "field": field, "severity": severity, "message": message}


def parse(raw: bytes, filename: str) -> tuple[str, dict]:
    name = (filename or "").lower()
    if len(raw) > config.MAX_UPLOAD_BYTES:
        raise ApiError(413, "payload_too_large", f"Files are limited to {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if not raw.strip():
        raise ApiError(422, "empty_file", "The file is empty.")
    if name.endswith(".json"):
        try:
            data = orjson.loads(raw)
        except orjson.JSONDecodeError as e:
            raise ApiError(422, "malformed_file", f"Not valid JSON: {e}")
        if isinstance(data, list):
            data = {"hotels": data}
        if not isinstance(data, dict) or not isinstance(data.get("hotels"), list):
            raise ApiError(422, "schema_mismatch", "JSON must be an object with a 'hotels' array (and optional 'rooms' and 'offers').")
        return "json", {"hotels": data["hotels"], "rooms": data.get("rooms") or [], "offers": data.get("offers") or []}
    if name.endswith(".csv"):
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ApiError(422, "malformed_file", "CSV must be UTF-8 encoded.")
        reader = csv.DictReader(io.StringIO(text))
        missing = [f for f in ("record_id", "name", "city") if f not in (reader.fieldnames or [])]
        if missing:
            raise ApiError(422, "schema_mismatch", f"CSV is missing required columns: {', '.join(missing)}.",
                           {"expected": HOTEL_FIELDS, "found": reader.fieldnames})
        return "csv", {"hotels": [dict(r) for r in reader], "rooms": [], "offers": []}
    raise ApiError(415, "unsupported_type", "Upload a .json or .csv file.")


def validate_payload(supplier: str, data: dict) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """Returns (valid_hotels, rooms, offers, issues, rows) with each hotel coerced to the canonical record shape."""
    issues, valid, rows, seen = [], [], [], set()
    existing_offer_ids = {o["offer_id"] for offs in catalog._sources()["offers"].values() for o in offs}
    for i, h in enumerate(data["hotels"], start=1):
        if not isinstance(h, dict):
            issues.append(_issue(i, None, None, "error", "Row is not an object"))
            continue
        rid = str(h.get("record_id") or "").strip()
        errs = []
        if not rid:
            errs.append(("record_id", "Missing record_id"))
        elif rid in seen:
            errs.append(("record_id", "Duplicate record_id in this file"))
        elif rid in DEMO.rec_by_id and DEMO.rec_by_id[rid].get("supplier") != supplier:
            errs.append(("record_id", f"record_id already belongs to {config.SUPPLIERS[DEMO.rec_by_id[rid]['supplier']]['name']}"))
        name = str(h.get("name") or "").strip()
        if not name:
            errs.append(("name", "Missing name"))
        city = normalize.canon_city(str(h.get("city") or ""))
        if city not in KNOWN_CITIES:
            errs.append(("city", f"Unknown city '{h.get('city')}' (supported: Dubai, Abu Dhabi, Singapore, Bangkok, Bali)"))
        lat, lng = h.get("lat"), h.get("lng")
        try:
            lat = float(lat) if lat not in (None, "") else None
            lng = float(lng) if lng not in (None, "") else None
        except (TypeError, ValueError):
            errs.append(("lat", "Coordinates are not numbers"))
            lat = lng = None
        if (lat is None) != (lng is None):
            errs.append(("lng", "Give both latitude and longitude, or neither"))
        elif lat is not None and not (math.isfinite(lat) and math.isfinite(lng) and abs(lat) <= 90 and abs(lng) <= 180):
            errs.append(("lat", "Coordinates out of range"))
        stars = h.get("stars")
        try:
            stars = int(float(stars)) if stars not in (None, "") else None
            if stars is not None and not 1 <= stars <= 5:
                errs.append(("stars", "Stars must be 1–5"))
        except (TypeError, ValueError):
            errs.append(("stars", "Stars is not a number"))
            stars = None
        if h.get("supplier") and h.get("supplier") != supplier:
            issues.append(_issue(i, rid, "supplier", "warning", f"File says supplier {h.get('supplier')}; importing as {supplier}"))
        if not h.get("phone"):
            issues.append(_issue(i, rid, "phone", "warning", "No phone number: matching relies on name and location"))
        if lat is None:
            issues.append(_issue(i, rid, "lat", "warning", "No coordinates: location evidence unavailable"))
        for f, m in errs:
            issues.append(_issue(i, rid or None, f, "error", m))
        ok = not errs
        if rid:
            seen.add(rid)
        rec = {"record_id": rid, "supplier": supplier, "name": name, "address": (h.get("address") or None), "phone": (h.get("phone") or None),
               "lat": lat, "lng": lng, "stars": stars, "city": CITY_DISPLAY.get(city, h.get("city")), "photos": [],
               "review_score": h.get("review_score"), "platinum": bool(h.get("platinum"))}
        rows.append({"row": i, "record_id": rid, "name": name, "city": rec["city"], "lat": lat, "lng": lng, "stars": stars,
                     "phone": rec["phone"], "valid": ok, "update": rid in DEMO.rec_by_id})
        if ok:
            valid.append(rec)
    ids = {h["record_id"] for h in valid}
    rooms, offers = [], []
    for j, r in enumerate(data.get("rooms", []), start=1):
        if not isinstance(r, dict) or r.get("record_id") not in ids or not r.get("supplier_room_id") or not r.get("room_name"):
            issues.append(_issue(j, (r or {}).get("record_id") if isinstance(r, dict) else None, "rooms", "warning",
                                 "Room skipped: needs supplier_room_id, room_name and a valid record_id"))
            continue
        rooms.append({**r, "supplier": supplier})
    room_ids = {r["supplier_room_id"] for r in rooms}
    for j, o in enumerate(data.get("offers", []), start=1):
        need = ("offer_id", "record_id", "supplier_room_id", "room_name", "price_inr")
        if not isinstance(o, dict) or any(not o.get(k) for k in need) or o.get("record_id") not in ids or o.get("supplier_room_id") not in room_ids:
            issues.append(_issue(j, (o or {}).get("record_id") if isinstance(o, dict) else None, "offers", "warning",
                                 "Rate skipped: needs offer_id, record_id, supplier_room_id, room_name and price_inr"))
            continue
        if o["offer_id"] in existing_offer_ids:
            issues.append(_issue(j, o["record_id"], "offer_id", "warning", f"Rate {o['offer_id']} already exists; skipped"))
            continue
        try:
            price = int(float(o["price_inr"]))
            if price <= 0:
                raise ValueError
        except (TypeError, ValueError):
            issues.append(_issue(j, o["record_id"], "price_inr", "warning", "Rate skipped: price must be a positive number"))
            continue
        offers.append({**o, "supplier": supplier, "price_inr": price, "currency": o.get("currency", "INR"),
                       "payment": o.get("payment", "prepay"), "occupancy": int(o.get("occupancy", 2)), "nights": int(o.get("nights", 1)),
                       "rate_code": o.get("rate_code") or f"{supplier}|{o['offer_id']}"})
    return valid, rooms, offers, issues, rows


CITY_DISPLAY = {"dubai": "Dubai", "abu_dhabi": "Abu Dhabi", "singapore": "Singapore", "bangkok": "Bangkok", "bali": "Bali"}


def create_job(supplier: str, filename: str, raw: bytes, user) -> dict:
    if supplier not in config.SUPPLIERS:
        raise ApiError(422, "invalid_value", "Choose a supplier.", {"field": "supplier"})
    if settings_svc.supplier_status(supplier) == "paused":
        raise ApiError(409, "supplier_paused", f"{config.SUPPLIERS[supplier]['name']} is paused. Resume the feed before importing.")
    fmt, data = parse(raw, filename)
    valid, rooms, offers, issues, rows = validate_payload(supplier, data)
    jid = f"IJ-{uuid.uuid4().hex[:8].upper()}"
    payload = {"hotels": valid, "rooms": rooms, "offers": offers, "rows": rows}
    store.execute("INSERT INTO ingestion_jobs(id, supplier, filename, format, status, created_by, created_at, total, valid, invalid, issues, payload) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (jid, supplier, filename[:200], fmt, "validated", user.id, store.now(), len(data["hotels"]), len(valid),
                   len(data["hotels"]) - len(valid), store.dumps(issues[:500]), store.dumps(payload)))
    audit.record(user, "ingestion.validated", "ingestion_job", jid,
                 after={"supplier": supplier, "file": filename, "records": len(data["hotels"]), "valid": len(valid),
                        "rooms": len(rooms), "rates": len(offers)})
    return get_job(jid)


def get_job(jid: str) -> dict:
    j = store.one("SELECT * FROM ingestion_jobs WHERE id = ?", (jid,))
    if not j:
        raise ApiError(404, "not_found", f"Ingestion job {jid} does not exist.")
    payload = store.loads(j.pop("payload"), {})
    j["issues"] = store.loads(j["issues"], [])
    j["preview"] = payload.get("rows", [])[:25]
    j["n_rooms"] = len(payload.get("rooms", []))
    j["n_rates"] = len(payload.get("offers", []))
    j["supplier_name"] = config.SUPPLIERS[j["supplier"]]["name"]
    j["results"] = store.query("SELECT record_id, outcome, tessera_id, p, detail FROM ingestion_results WHERE job_id = ? ORDER BY rowid", (jid,))
    names = {u["id"]: u["name"] for u in store.query("SELECT id, name FROM users")}
    j["created_by_name"] = names.get(j["created_by"], j["created_by"])
    j["running"] = jid in _RUNNING and _RUNNING[jid].is_alive()
    return j


def list_jobs(supplier: str = "", page: int = 1, page_size: int = 25) -> dict:
    where, params = ("WHERE supplier = ?", [supplier]) if supplier else ("", [])
    total = store.one(f"SELECT COUNT(*) AS n FROM ingestion_jobs {where}", params)["n"]
    rows = store.query(f"SELECT id, supplier, filename, format, status, created_by, created_at, started_at, finished_at, total, valid, invalid, "
                       f"processed, merged, created, updated, review, rejected, error, attempts FROM ingestion_jobs {where} "
                       f"ORDER BY created_at DESC LIMIT ? OFFSET ?", params + [page_size, (page - 1) * page_size])
    for r in rows:
        r["supplier_name"] = config.SUPPLIERS[r["supplier"]]["name"]
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


def start(jid: str, user, retry: bool = False) -> dict:
    j = store.one("SELECT status FROM ingestion_jobs WHERE id = ?", (jid,))
    if not j:
        raise ApiError(404, "not_found", f"Ingestion job {jid} does not exist.")
    allowed = ("failed",) if retry else ("validated",)
    if j["status"] not in allowed:
        raise ApiError(409, "invalid_state", f"Job is {j['status']}; it can only be {'retried when failed' if retry else 'started once, after validation'}.")
    cur = store.execute("UPDATE ingestion_jobs SET status = 'queued', error = NULL WHERE id = ? AND status = ?", (jid, j["status"]))
    if cur.rowcount != 1:
        raise ApiError(409, "invalid_state", "Job state changed; reload.")
    audit.record(user, "ingestion.retried" if retry else "ingestion.started", "ingestion_job", jid)
    t = threading.Thread(target=_run, args=(jid, user.id), daemon=True, name=f"ingest-{jid}")
    _RUNNING[jid] = t
    t.start()
    return get_job(jid)


def _run(jid: str, actor: str) -> None:
    try:
        store.execute("UPDATE ingestion_jobs SET status = 'running', started_at = ?, attempts = attempts + 1 WHERE id = ?", (store.now(), jid))
        j = store.one("SELECT supplier, payload FROM ingestion_jobs WHERE id = ?", (jid,))
        supplier, payload = j["supplier"], store.loads(j["payload"])
        done = {r["record_id"] for r in store.query("SELECT record_id FROM ingestion_results WHERE job_id = ?", (jid,))}
        hotels = [h for h in payload["hotels"] if h["record_id"] not in done]
        rooms_of, offers_of = {}, {}
        for r in payload["rooms"]:
            rooms_of.setdefault(r["record_id"], []).append(r)
        for o in payload["offers"]:
            offers_of.setdefault(o["record_id"], []).append(o)
        norms = [normalize.normalize_hotel(h) for h in hotels]
        vecs = blocking.embed(norms) if norms else []
        from app.services.live import _score_candidates
        for h, n, vec in zip(hotels, norms, vecs):
            outcome, detail = _process(jid, supplier, h, n, vec, rooms_of.get(h["record_id"], []), offers_of.get(h["record_id"], []), actor)
            col = {"attach": "merged", "new": "created", "update": "updated", "review": "review", "rejected": "rejected"}[outcome]
            store.execute(f"UPDATE ingestion_jobs SET processed = processed + 1, {col} = {col} + 1 WHERE id = ?", (jid,))
        store.execute("UPDATE ingestion_jobs SET status = 'completed', finished_at = ? WHERE id = ?", (store.now(), jid))
        fin = store.one("SELECT total, merged, created, updated, review, rejected, invalid FROM ingestion_jobs WHERE id = ?", (jid,))
        audit.record(actor, "ingestion.completed", "ingestion_job", jid, after=fin)
    except Exception as e:  # keep the failure observable and retryable
        traceback.print_exc()
        store.execute("UPDATE ingestion_jobs SET status = 'failed', finished_at = ?, error = ? WHERE id = ?",
                      (store.now(), f"{type(e).__name__}: {e}"[:500], jid))
        audit.record(actor, "ingestion.failed", "ingestion_job", jid, after={"error": f"{type(e).__name__}: {e}"[:300]})
    finally:
        _RUNNING.pop(jid, None)


def _process(jid, supplier, rec, n, vec, rooms, offers, actor) -> tuple[str, dict]:
    from app.services.live import _score_candidates
    rid = rec["record_id"]
    base = {"record": rec, "rooms": rooms, "offers": offers, "supplier": supplier, "job_id": jid,
            "embedding": [round(float(x), 6) for x in vec]}
    if rid in DEMO.rec_by_id:  # same supplier re-sent an existing listing: update in place
        res = catalog.commit("ingest", {**base, "outcome": "update"}, actor, "ingestion")
        _result(jid, rid, "update", res.get("tessera_id"), None, "Existing listing updated")
        return "update", res
    q = dict(n)
    rows, X, raw, p, _ = _score_candidates(q, vec)
    best_k, best_tid = None, None
    for k, r in enumerate(rows):
        tid = DEMO.record_cluster.get(DEMO.state["norms"][r]["record_id"])
        if tid and (best_k is None or raw[k] > raw[best_k]):
            best_k, best_tid = k, tid
    if best_k is None:
        res = catalog.commit("ingest", {**base, "outcome": "new"}, actor, "ingestion")
        _result(jid, rid, "new", res.get("tessera_id"), None, "No candidate nearby: new property")
        return "new", res
    other = DEMO.state["norms"][rows[best_k]]["record_id"]
    pk, band = float(p[best_k]), DEMO.band_of(float(raw[best_k]))
    clash = supplier in {catalog.supplier_of(r) for r in catalog.primaries(DEMO.hotels[best_tid])}
    if band == "uncertain" and config.LLM_ENABLED:
        v = adjudicator.adjudicate([{"pair_id": f"{rid}|{other}", "a": rec, "b": DEMO.rec_by_id[other], "p": pk,
                                     "subbrand_conflict": bool(X[best_k][7])}]).get(f"{rid}|{other}")
        if v and v["route"] == "llm":
            band = "auto_merge" if v["verdict"] == "same" else "auto_reject"
    payload = {**base, "matched_record": other, "tessera_id": best_tid, "p": pk}
    if band == "auto_merge" and not clash:
        res = catalog.commit("ingest", {**payload, "outcome": "attach"}, actor, "ingestion")
        _result(jid, rid, "attach", res.get("tessera_id"), pk, f"Merged into {DEMO.hotels[res['tessera_id']]['name']}")
        return "attach", res
    if band == "auto_reject":
        res = catalog.commit("ingest", {**payload, "outcome": "new"}, actor, "ingestion")
        _result(jid, rid, "new", res.get("tessera_id"), pk, "Closest candidate below the reject threshold: new property")
        return "new", res
    res = catalog.commit("ingest", {**payload, "outcome": "new"}, actor, "ingestion")
    why = (f"{config.SUPPLIERS[supplier]['name']} already lists {DEMO.hotels[best_tid]['name']}: possible duplicate listing"
           if clash else f"Ambiguous match with {DEMO.hotels[best_tid]['name']} (p = {pk:.3f})")
    cid = review.create_case(rid, other, pk, "ingestion", actor)
    _result(jid, rid, "review", res.get("tessera_id"), pk, f"{why}; review case {cid}")
    return "review", res


def _result(jid, rid, outcome, tid, p, detail):
    store.execute("INSERT OR REPLACE INTO ingestion_results(job_id, record_id, outcome, tessera_id, p, detail) VALUES (?,?,?,?,?,?)",
                  (jid, rid, outcome, tid, p, detail))


def recover_interrupted() -> int:
    """Jobs that were running when the server stopped are marked failed (retryable; finished records are kept)."""
    cur = store.execute("UPDATE ingestion_jobs SET status = 'failed', error = 'Interrupted by a server restart; retry to continue.', "
                        "finished_at = ? WHERE status IN ('queued', 'running')", (store.now(),))
    return cur.rowcount


def sample_feed(fmt: str = "json", n: int = 40) -> tuple[bytes, str, str]:
    """A slice of the synthetic NovaBeds feed (never loaded at startup) for trying the import flow."""
    feed = orjson.loads((config.WORLD_DIR / "novabeds_feed.json").read_bytes())
    # The ground truth is used only to pick a representative test file (some hotels the catalog already has, some
    # it does not); matching never sees it.
    hor = orjson.loads((config.WORLD_DIR / "truth.json").read_bytes())["hotel_of_record"]
    known = {h for rid, h in hor.items() if rid in DEMO.rec_by_id and DEMO.rec_by_id[rid].get("supplier") != "S6"}
    is_dubai = lambda h: normalize.canon_city(h["city"]) == "dubai"  # noqa: E731
    fresh = [h for h in feed["hotels"] if hor.get(h["record_id"]) not in known]
    existing = [h for h in feed["hotels"] if hor.get(h["record_id"]) in known]
    hotels = ([h for h in existing if is_dubai(h)][:n - 14] + [h for h in fresh if is_dubai(h)][:4] + [h for h in fresh if not is_dubai(h)][:4]
              + [h for h in existing if not is_dubai(h)][:6])[:n]
    ids = {h["record_id"] for h in hotels}
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=HOTEL_FIELDS, extrasaction="ignore")
        w.writeheader()
        for h in hotels:
            w.writerow(h)
        return buf.getvalue().encode(), "novabeds_sample.csv", "text/csv"
    body = {"supplier": feed["supplier"], "name": feed["name"], "hotels": hotels,
            "rooms": [r for r in feed["rooms"] if r["record_id"] in ids], "offers": [o for o in feed["offers"] if o["record_id"] in ids]}
    return orjson.dumps(body, option=orjson.OPT_INDENT_2), "novabeds_sample.json", "application/json"
