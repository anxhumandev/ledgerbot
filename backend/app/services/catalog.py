"""Canonical catalog: read models for the inventory UI and the mutations operators make to it.

Source of truth
- The pipeline build (state.pkl) is the immutable base catalog: supplier records, golden records, room groups, offers.
- `catalog_mutations` (SQLite) is an ordered log of changes on top of it: merges and splits decided in Match Review,
  and records added or updated by supplier ingestion. On startup, and whenever a change is undone, the catalog is
  rebuilt from the base plus every active mutation, so the in-memory view always equals base + log.

Everything here is derived from that state; nothing is generated for display.
"""
from __future__ import annotations

import copy
import time
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np
import orjson

from app import audit, config, store
from app.demo import DEMO
from app.errors import ApiError
from app.pipeline import content, normalize, offers as off, ranking, rooms as room_match
from app.pipeline.enrich import golden_name, neighbourhood_of
from data.tables import CITIES

QUALITY_WEIGHTS = [("phone", 15), ("address", 15), ("coordinates", 10), ("stars", 10), ("photos", 15),
                   ("rooms", 15), ("corroborated", 10), ("no_open_review", 10)]

_SRC: dict = {}


# ---------------------------------------------------------------- inventory sources (rooms + rates per record)
def _sources():
    if "base_rooms" not in _SRC:
        rooms_raw = orjson.loads((config.WORLD_DIR / "rooms_raw.json").read_bytes())
        offers_raw = orjson.loads((config.WORLD_DIR / "offers_raw.json").read_bytes())
        rb, ob = defaultdict(list), defaultdict(list)
        for r in rooms_raw:
            rb[r["record_id"]].append(r)
        for o in offers_raw:
            ob[o["record_id"]].append(o)
        _SRC.update(rooms=rb, offers=ob, base_rooms={k: list(v) for k, v in rb.items()},
                    base_offers={k: list(v) for k, v in ob.items()})
        ph = config.CACHE_DIR / "phash.json"
        _SRC["phash"] = orjson.loads(ph.read_bytes()) if ph.exists() else {}
    return _SRC


def build_rooms(prim: list[str]) -> list[dict]:
    """Room groups and offer slots for one property, from its primary supplier records (same logic as the pipeline)."""
    src = _sources()
    srooms = [sr for r in prim for sr in src["rooms"].get(r, [])]
    if not srooms:
        return []
    groups = room_match.match_rooms(srooms)
    g_of = {m["supplier_room_id"]: gi for gi, g in enumerate(groups) for m in g["members"]}
    ident_of = {(sr["record_id"], tuple(sorted(normalize.room_identity(normalize.parse_room(sr["room_name"])).items()))): sr["supplier_room_id"]
                for sr in srooms}
    raw_name = {sr["supplier_room_id"]: sr["room_name"] for sr in srooms}
    slots = defaultdict(list)
    for r in prim:
        for o in src["offers"].get(r, []):
            no = off.normalize_offer(o)
            key = (r, tuple(sorted(normalize.room_identity(normalize.parse_room(o["room_name"])).items())))
            gi = g_of.get(ident_of.get(key, o["supplier_room_id"]), g_of.get(o["supplier_room_id"]))
            if gi is None:
                continue
            no["group"] = gi
            no["raw_room_name"] = raw_name.get(o["supplier_room_id"], o["room_name"])
            slots[off.slot_key(gi, no)].append(no)
    for gi, g in enumerate(groups):
        g["slots"] = []
        for key, offs in slots.items():
            if key[0] != gi:
                continue
            hours = max((o["cancel_hours"] for o in offs), default=0)
            g["slots"].append({"key": [key[1], key[2], key[3], key[4]], "board": key[1], "refundable": key[2],
                               "label": off.slot_label(key[1], key[2], hours or None), "offers": offs})
        g["slots"].sort(key=lambda s: (["RO", "BB", "HB", "FB", "AI"].index(s["board"]), not s["refundable"]))
    return groups


def primaries(h: dict) -> list[str]:
    alias = DEMO.state["alias"]
    return [m for m in h["members"] if m not in alias and m in DEMO.rec_by_id]


def supplier_of(rid: str) -> str:
    n = DEMO.norm_by_id.get(rid)
    return n["supplier"] if n else DEMO.rec_by_id.get(rid, {}).get("supplier", "?")


def refresh_hotel(tid: str, *, rename: bool = False) -> None:
    """Recompute derived fields of one golden record after its membership changed."""
    h = DEMO.hotels[tid]
    prim = primaries(h)
    h["members"] = sorted(set(h["members"]))
    h["suppliers"] = sorted({supplier_of(r) for r in prim})
    h["n_records"] = len(h["members"])
    if rename and prim:
        h["name"] = golden_name([DEMO.rec_by_id[r] for r in prim])
    if h["city"] == "dubai":
        h["rooms"] = build_rooms(prim)
        h["n_offers"] = sum(len(s["offers"]) for g in h["rooms"] for s in g["slots"])
        recs = [DEMO.rec_by_id[r] for r in prim]
        h["photos"] = content.dedup_photos(recs, _sources()["phash"]) if any(r.get("photos") for r in recs) else None
    _CONF.pop(tid, None)


# ---------------------------------------------------------------- match confidence
_CONF: dict[str, float | None] = {}


def pair_p(a: str, b: str) -> float | None:
    k = DEMO.pair_index.get((a, b), DEMO.pair_index.get((b, a)))
    if k is not None:
        return float(DEMO.state["p"][k])
    extra = getattr(DEMO, "extra_edges", {})
    return extra.get((a, b), extra.get((b, a)))


def confidence(tid: str) -> float | None:
    """Weakest scored link inside the golden record (calibrated match probability). None for single-source records."""
    if tid in _CONF:
        return _CONF[tid]
    h = DEMO.hotels[tid]
    prim = primaries(h)
    best = None
    if len(prim) > 1:
        # each member's strongest link to the rest; the record's confidence is the weakest of those
        for a in prim:
            links = [pair_p(a, b) for b in prim if b != a and supplier_of(a) != supplier_of(b)]
            links = [x for x in links if x is not None]
            if links:
                m = max(links)
                best = m if best is None else min(best, m)
    _CONF[tid] = best
    return best


# ---------------------------------------------------------------- quality and status
def quality(h: dict, open_records: set[str]) -> dict:
    prim = primaries(h)
    checks = {
        "phone": bool(h.get("phone")), "address": bool(h.get("address")),
        "coordinates": h.get("lat") is not None and h.get("lng") is not None,
        "stars": bool(h.get("stars")), "photos": bool((h.get("photos") or {}).get("hero")),
        "rooms": bool(h.get("rooms")) if h["city"] == "dubai" else None,
        "corroborated": len({supplier_of(r) for r in prim}) >= 2,
        "no_open_review": not any(m in open_records for m in h["members"]),
    }
    if h["city"] != "dubai":
        checks["photos"] = None  # photos and rooms are only generated for the detailed Dubai world
    num = sum(w for k, w in QUALITY_WEIGHTS if checks[k])
    den = sum(w for k, w in QUALITY_WEIGHTS if checks[k] is not None)
    return {"score": round(100 * num / den) if den else None, "checks": checks}


def status(h: dict, conf: float | None, open_records: set[str]) -> str:
    if any(m in open_records for m in h["members"]):
        return "needs_review"
    if h.get("ingested"):
        return "new"
    if len(h["suppliers"]) < 2:
        return "single_source"
    tau = DEMO.current_risk.get("tau_accept")
    if conf is not None and tau is not None and conf < tau:
        return "low_confidence"
    return "verified"


STATUS_LABEL = {"needs_review": "Needs review", "new": "New", "single_source": "Single source",
                "low_confidence": "Low confidence", "verified": "Verified"}


def built_ts() -> float:
    try:
        return datetime.strptime(DEMO.state["built_at"], "%Y-%m-%d %H:%M:%S").timestamp()
    except Exception:
        return 0.0


def city_name(city: str) -> str:
    return CITIES.get(city, {}).get("name", city.replace("_", " ").title())


def open_case_records() -> set[str]:
    out = set()
    for r in store.query("SELECT record_a, record_b FROM review_cases WHERE status IN ('open', 'escalated')"):
        out.add(r["record_a"])
        out.add(r["record_b"])
    return out


def hotel_row(h: dict, open_records: set[str], touched: dict[str, float]) -> dict:
    conf = confidence(h["tessera_id"])
    q = quality(h, open_records)
    st = status(h, conf, open_records)
    return {"id": h["tessera_id"], "type": "hotel", "name": h["name"], "category": "Hotel",
            "subcategory": f"{h['stars']}★" if h.get("stars") else None, "city": h["city"], "city_name": city_name(h["city"]),
            "country": config.COUNTRY_OF_CITY.get(h["city"], ""), "area": h.get("neighbourhood"),
            "suppliers": h["suppliers"], "n_suppliers": len(h["suppliers"]), "n_listings": h["n_records"],
            "confidence": round(conf, 4) if conf is not None else None, "quality": q["score"], "status": st,
            "status_label": STATUS_LABEL[st], "updated_at": touched.get(h["tessera_id"], built_ts()),
            "n_offers": h.get("n_offers", 0)}


# ---------------------------------------------------------------- sightseeing
def activity_city(p: dict) -> str:
    cities = Counter(u.get("city") or "Dubai" for o in p["options"] for u in o["units"])
    return cities.most_common(1)[0][0] if cities else "Dubai"


def _listing_index() -> dict:
    if "listings" not in _SRC:
        _SRC["listings"] = {l["listing_id"]: l for l in orjson.loads((config.WORLD_DIR / "activities_raw.json").read_bytes())}
    return _SRC["listings"]


def activity_row(p: dict, touched: dict[str, float]) -> dict:
    lst = _listing_index()
    units = [u for o in p["options"] for u in o["units"]]
    sups = sorted({u["supplier"] for u in units})
    filled = [sum(bool(lst.get(u["listing_id"], {}).get(f)) for f in ("meeting_point", "inclusions", "language")) +
              (u.get("duration_min") is not None) for u in units]
    qscore = round(100 * sum(filled) / (4 * len(units))) if units else None
    city = activity_city(p)
    st = "single_source" if len(sups) < 2 else "verified"
    return {"id": p["product_id"], "type": "activity", "name": p["label"], "category": "Sightseeing",
            "subcategory": f"{len(p['options'])} option{'s' if len(p['options']) != 1 else ''}", "city": city.lower().replace(" ", "_"),
            "city_name": city, "country": config.COUNTRY_OF_CITY.get(city.lower().replace(" ", "_"), ""), "area": None,
            "suppliers": sups, "n_suppliers": len(sups), "n_listings": len(units), "confidence": None,
            "match_rule": "Attraction + access tier", "quality": qscore, "status": st, "status_label": STATUS_LABEL[st],
            "updated_at": touched.get(p["product_id"], built_ts()), "n_offers": len(units)}


def product(pid: str) -> dict:
    for p in DEMO.state["products"]:
        if p["product_id"] == pid:
            return p
    raise ApiError(404, "not_found", f"Sightseeing product {pid} does not exist.")


# ---------------------------------------------------------------- listing
SORTABLE = {"relevance", "name", "city_name", "n_suppliers", "n_listings", "confidence", "quality", "updated_at", "id", "status"}


def list_inventory(kind: str = "hotel", q: str = "", country: str = "", city: str = "", supplier: str = "", status_: str = "",
                   quality_: str = "", conf_min: float | None = None, conf_max: float | None = None, sort: str = "relevance",
                   order: str = "asc", page: int = 1, page_size: int = 25) -> dict:
    if kind not in ("hotel", "activity"):
        raise ApiError(400, "bad_request", "type must be 'hotel' or 'activity'")
    if sort not in SORTABLE:
        raise ApiError(400, "bad_request", f"cannot sort by '{sort}'", {"allowed": sorted(SORTABLE)})
    open_records = open_case_records()
    if kind == "hotel":
        touched = audit.last_touch("hotel")
        rows = [hotel_row(h, open_records, touched) for h in DEMO.hotels.values()]
    else:
        touched = audit.last_touch("activity")
        rows = [activity_row(p, touched) for p in DEMO.state["products"]]
    facets = {"countries": sorted({r["country"] for r in rows if r["country"]}),
              "cities": sorted({(r["city"], r["city_name"]) for r in rows}, key=lambda t: t[1]),
              "suppliers": sorted({s for r in rows for s in r["suppliers"]})}
    score: dict[str, float] = {}
    if q:
        ql = q.lower().strip()
        if kind == "hotel":  # also matches any supplier's spelling of the property
            from app.services import analyst
            score = {x["tessera_id"]: x["score"] for x in analyst.search(q, limit=200) if x["score"] >= 75}
        for r in rows:
            nm = r["name"].lower()
            if nm == ql or r["id"].lower() == ql:
                score[r["id"]] = 300
            elif nm.startswith(ql):
                score[r["id"]] = 200
            elif ql in nm or ql in r["id"].lower():
                score[r["id"]] = max(score.get(r["id"], 0), 150)
        rows = [r for r in rows if r["id"] in score]
    if sort == "relevance":
        rows.sort(key=lambda r: (-score.get(r["id"], 0), r["name"].lower()))
    if country:
        rows = [r for r in rows if r["country"] == country]
    if city:
        rows = [r for r in rows if r["city"] == city]
    if supplier:
        rows = [r for r in rows if supplier in r["suppliers"]]
    if status_:
        wanted = set(status_.split(","))
        rows = [r for r in rows if r["status"] in wanted]
    if quality_:
        lo, hi = {"high": (85, 101), "medium": (60, 85), "low": (-1, 60)}.get(quality_, (-1, 101))
        rows = [r for r in rows if r["quality"] is not None and lo <= r["quality"] < hi]
    if conf_min is not None:
        rows = [r for r in rows if r["confidence"] is not None and r["confidence"] >= conf_min]
    if conf_max is not None:
        rows = [r for r in rows if r["confidence"] is not None and r["confidence"] <= conf_max]
    status_counts = Counter(r["status"] for r in rows)
    if sort != "relevance":
        present = [r for r in rows if r[sort] is not None]
        present.sort(key=lambda r: r[sort].lower() if isinstance(r[sort], str) else r[sort], reverse=order == "desc")
        rows = present + [r for r in rows if r[sort] is None]  # missing values always last
    total = len(rows)
    page_size = max(1, min(page_size, 200))
    start = (max(page, 1) - 1) * page_size
    return {"items": rows[start:start + page_size], "total": total, "page": page, "page_size": page_size,
            "facets": {**facets, "cities": [{"id": c, "name": n} for c, n in facets["cities"]]},
            "status_counts": dict(status_counts)}


# ---------------------------------------------------------------- mutations
def _new_tid(mutation_id: int) -> str:
    return f"TS-M{mutation_id:04d}"


def _ensure_extras():
    for name in ("extra_emb", "extra_edges", "extra_hashes"):
        if not hasattr(DEMO, name):
            setattr(DEMO, name, {})


def _apply(m: dict) -> dict:
    """Apply one mutation to the in-memory catalog. Raises ApiError(409) when it would break an invariant."""
    _ensure_extras()
    kind, pl = m["kind"], m["payload"]
    if kind == "merge":
        a, b = pl["record_a"], pl["record_b"]
        ta, tb = DEMO.record_cluster.get(a), DEMO.record_cluster.get(b)
        if ta is None or tb is None:
            raise ApiError(409, "unknown_record", "One of the records is no longer in the catalog.")
        if ta == tb:
            return {"changed": False, "tessera_id": ta}
        ha, hb = DEMO.hotels[ta], DEMO.hotels[tb]
        clash = {supplier_of(r) for r in primaries(ha)} & {supplier_of(r) for r in primaries(hb)}
        if clash:
            raise ApiError(409, "supplier_conflict",
                           f"Merging would put two listings from {', '.join(config.SUPPLIERS[s]['name'] for s in sorted(clash))} "
                           "into one property. Resolve the duplicate listing first or escalate.",
                           {"suppliers": sorted(clash), "tessera_ids": [ta, tb]})
        ha["members"] = ha["members"] + hb["members"]
        for r in hb["members"]:
            DEMO.record_cluster[r] = ta
        del DEMO.hotels[tb]
        refresh_hotel(ta)
        return {"changed": True, "tessera_id": ta, "absorbed": tb}
    if kind == "split":
        a, b = pl["record_a"], pl["record_b"]
        ta, tb = DEMO.record_cluster.get(a), DEMO.record_cluster.get(b)
        if ta is None or tb is None:
            raise ApiError(409, "unknown_record", "One of the records is no longer in the catalog.")
        if ta != tb:
            return {"changed": False, "tessera_id": tb}
        alias = DEMO.state["alias"]
        moving = {b} | {r for r in DEMO.hotels[ta]["members"] if alias.get(r) == b}
        src = DEMO.hotels[ta]
        if set(src["members"]) <= moving:
            return {"changed": False, "tessera_id": ta}
        new_tid = pl.get("new_id") or _new_tid(m["id"])
        rec = DEMO.rec_by_id[b]
        n = DEMO.norm_by_id[b]
        src["members"] = [r for r in src["members"] if r not in moving]
        DEMO.hotels[new_tid] = {
            "tessera_id": new_tid, "name": golden_name([rec]), "brand": n.get("brand"), "stars": rec.get("stars") or src.get("stars"),
            "city": src["city"], "neighbourhood": neighbourhood_of(src["city"], rec["lat"], rec["lng"]) if rec.get("lat") is not None else src.get("neighbourhood"),
            "lat": rec.get("lat") if rec.get("lat") is not None else src["lat"], "lng": rec.get("lng") if rec.get("lng") is not None else src["lng"],
            "phone": n.get("phone"), "address": rec.get("address"), "members": sorted(moving), "suppliers": [n["supplier"]],
            "n_records": len(moving), "dups": [r for r in moving if r in alias], "split_from": ta}
        for r in moving:
            DEMO.record_cluster[r] = new_tid
        refresh_hotel(ta)
        refresh_hotel(new_tid)
        return {"changed": True, "tessera_id": ta, "created": new_tid}
    if kind == "ingest":
        return _apply_ingest(m)
    raise ApiError(400, "bad_request", f"unknown mutation kind {kind}")


def _apply_ingest(m: dict) -> dict:
    pl = m["payload"]
    rec, outcome = pl["record"], pl["outcome"]
    rid = rec["record_id"]
    src = _sources()
    n = normalize.normalize_hotel(rec)
    DEMO.rec_by_id[rid] = rec
    DEMO.norm_by_id[rid] = n
    src["rooms"][rid] = pl.get("rooms") or []
    src["offers"][rid] = pl.get("offers") or []
    if pl.get("embedding") is not None:
        DEMO.extra_emb[rid] = np.asarray(pl["embedding"], dtype=np.float32)
    if pl.get("matched_record") and pl.get("p") is not None:
        DEMO.extra_edges[(rid, pl["matched_record"])] = float(pl["p"])
    if outcome == "update":
        tid = DEMO.record_cluster.get(rid)
        if tid:
            refresh_hotel(tid)
        return {"changed": True, "tessera_id": tid}
    if outcome == "attach":
        tid = DEMO.record_cluster.get(pl["matched_record"]) or pl.get("tessera_id")
        if tid not in DEMO.hotels:
            outcome = "new"
        else:
            h = DEMO.hotels[tid]
            if rec["supplier"] in {supplier_of(r) for r in primaries(h)}:
                outcome = "new"  # the property gained a listing from this supplier in the meantime
            else:
                h["members"] = h["members"] + [rid]
                DEMO.record_cluster[rid] = tid
                refresh_hotel(tid)
                return {"changed": True, "tessera_id": tid}
    city = n["city"]
    tid = pl.get("new_id") or f"TS-{rid}"
    DEMO.hotels[tid] = {"tessera_id": tid, "name": golden_name([rec]), "brand": n.get("brand"), "stars": rec.get("stars"),
                        "city": city, "neighbourhood": neighbourhood_of(city, rec["lat"], rec["lng"]) if rec.get("lat") is not None else None,
                        "lat": rec.get("lat"), "lng": rec.get("lng"), "phone": n.get("phone"), "address": rec.get("address"),
                        "members": [rid], "suppliers": [rec["supplier"]], "n_records": 1, "dups": [], "ingested": True}
    DEMO.record_cluster[rid] = tid
    refresh_hotel(tid)
    return {"changed": True, "tessera_id": tid, "created": tid}


def commit(kind: str, payload: dict, actor, source: str) -> dict:
    """Validate by applying, then persist. Either both happen or neither."""
    with DEMO.lock:
        actor_id = getattr(actor, "id", actor)
        cur = store.execute("INSERT INTO catalog_mutations(ts, kind, payload, actor, active, source) VALUES (?,?,?,?,1,?)",
                            (store.now(), kind, store.dumps(payload), actor_id, source))
        mid = cur.lastrowid
        try:
            result = _apply({"id": mid, "kind": kind, "payload": payload})
        except Exception:
            store.execute("DELETE FROM catalog_mutations WHERE id = ?", (mid,))
            raise
        _after_change()
        return {"mutation_id": mid, **result}


def deactivate(mutation_id: int) -> None:
    with DEMO.lock:
        store.execute("UPDATE catalog_mutations SET active = 0 WHERE id = ?", (mutation_id,))
        rebuild()


def rebuild() -> dict:
    """Base catalog + every active mutation, in order. Mutations that no longer apply are skipped and reported."""
    t0 = time.time()
    with DEMO.lock:
        DEMO.state["hotels"] = copy.deepcopy(DEMO.base_hotels)
        DEMO.hotels = DEMO.state["hotels"]
        DEMO.record_cluster = dict(DEMO.base_record_cluster)
        DEMO.rec_by_id = {r["record_id"]: r for r in DEMO.state["recs"]}
        DEMO.norm_by_id = {n["record_id"]: n for n in DEMO.state["norms"]}
        DEMO.extra_emb, DEMO.extra_edges, DEMO.extra_hashes = {}, {}, {}
        src = _sources()
        src["rooms"] = defaultdict(list, {k: list(v) for k, v in src["base_rooms"].items()})
        src["offers"] = defaultdict(list, {k: list(v) for k, v in src["base_offers"].items()})
        _CONF.clear()
        skipped = []
        for m in store.query("SELECT id, kind, payload FROM catalog_mutations WHERE active = 1 ORDER BY id"):
            try:
                _apply({"id": m["id"], "kind": m["kind"], "payload": store.loads(m["payload"])})
            except ApiError as e:
                skipped.append({"mutation_id": m["id"], "reason": e.message})
        _after_change()
    return {"applied_in_s": round(time.time() - t0, 2), "skipped": skipped}


def refresh_ranking_table() -> None:
    """Ranking features use the same lead offer the app shows: live reliability, the workspace price cap and paused suppliers."""
    from app.services import settings_svc
    DEMO.hotel_table = ranking.hotel_table({**DEMO.state, "recs": list(DEMO.rec_by_id.values())}, DEMO.p_success,
                                           float(settings_svc.get("price_cap_pct")), frozenset(settings_svc.paused_suppliers()))


def _after_change():
    refresh_ranking_table()
    try:
        from app.services.simulator import SIM
        SIM.prepare()
    except Exception:
        pass


def has_mutations() -> bool:
    return bool(store.one("SELECT 1 AS x FROM catalog_mutations WHERE active = 1 LIMIT 1"))
