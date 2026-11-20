"""Live pipeline: single-record Break-It trace and incremental NovaBeds onboarding (streamed)."""
from __future__ import annotations

import asyncio
import math
import time
import copy
from collections import defaultdict

import numpy as np
import orjson

from app import config
from app.demo import DEMO
from app.pipeline import adjudicator, blocking, normalize, rooms, offers, ranking
from app.pipeline.enrich import neighbourhood_of
from app.pipeline.cost import METER
from app.pipeline.features import distinguishing_detail, haversine_m, pair_features
from app.pipeline.matcher import explain
from app.ws import HUB


def _features(n_new: dict, vec: np.ndarray, hashes, row: int) -> np.ndarray:
    st = DEMO.state
    other = st["norms"][row]
    a = dict(n_new)
    if a.get("lat") is None:
        a["lat"], a["lng"] = float("nan"), float("nan")
    return np.array(pair_features(a, other, float(vec @ st["emb"][row]), hashes, st["index"].hashes.get(other["record_id"])),
                    dtype=np.float32)


def _score_candidates(n_new: dict, vec: np.ndarray, hashes=None, topk: int = blocking.TOPK):
    idx = DEMO.state["index"]
    q = dict(n_new)
    if q.get("lat") is None:
        q["lat"], q["lng"] = 0.0, 0.0  # geo blocking yields nothing far from every hotel
    cands = idx.query(q, vec, hashes, topk=topk)
    rows = list(cands)
    if not rows:
        return [], np.zeros((0, 1)), np.zeros(0), np.zeros(0), cands
    X = np.vstack([_features(n_new, vec, hashes, r) for r in rows])
    raw, p = DEMO.matcher.predict(X)
    return rows, X, raw, p, cands


def _review_reason(ex: dict) -> str:
    # data-quality terms are not evidence a human can act on, so they stay out of the sentence
    items = [i for i in ex["items"] if i["group"] != "quality"]
    pos = [i["label"] for i in items if i["value"] > 0][:2]
    neg = [i["label"] for i in items if i["value"] < 0][:2]
    if pos and neg:
        return f"I'm not sure, sending to a human. For a match: {', '.join(pos)}. Against: {', '.join(neg)}."
    if neg:
        return f"I'm not sure, sending to a human. Against a match: {', '.join(neg)}."
    return "I'm not sure, sending to a human: the evidence is mixed."


# ---------------------------------------------------------------- Break-It trace
def presets() -> list[dict]:
    recs = DEMO.rec_by_id
    hotels = DEMO.hotels
    sc = DEMO.state["showcase"]

    def s1_of(tid):
        ms = [recs[m] for m in hotels[tid]["members"] if m in recs]
        return next((m for m in ms if m["supplier"] == "S1"), ms[0])

    palm = s1_of(sc["Atlantis The Palm"])
    royal = s1_of(sc["Atlantis The Royal"])
    addr = next(h for h in hotels.values() if h["name"] == "Address Downtown")
    addr_r = s1_of(addr["tessera_id"])
    hil = next(h for h in hotels.values() if h["name"] == "Hilton Dubai Jumeirah")
    hil_r = s1_of(hil["tessera_id"])
    lat8, lng8 = addr_r["lat"] + 400 / 111_320.0, addr_r["lng"]
    return [
        {"id": "misspelled", "label": "Misspelled", "record": {"name": "Atlantiss The Plam Resortt", "address": palm["address"],
         "lat": palm["lat"], "lng": palm["lng"], "phone": palm["phone"], "room_name": "Deluxe King Room – Sea View"}},
        {"id": "wrong_pin", "label": "Wrong pin (400 m off)", "record": {"name": addr_r["name"], "address": None,
         "lat": round(lat8, 6), "lng": lng8, "phone": None, "room_name": "Deluxe King Burj Khalifa View"}},
        {"id": "sister", "label": "Sister property", "record": {"name": "Atlantis Royal Resort Dubai", "address": None,
         "lat": royal["lat"], "lng": royal["lng"], "phone": None, "room_name": "Suite King Sea View"}},
        {"id": "spanish", "label": "Spanish room name", "record": {"name": "Hotel Hilton Dubái Jumeirah", "address": hil_r["address"],
         "lat": hil_r["lat"], "lng": hil_r["lng"], "phone": hil_r["phone"], "room_name": "Habitación Doble Deluxe Vista Mar – AD"}},
        {"id": "gibberish", "label": "Gibberish", "record": {"name": "Qzxv Blorp Inn", "address": "Unit 9, Nowhere Rd",
         "lat": 25.02, "lng": 55.43, "phone": "+971 4 000 0000", "room_name": "Mystery Room Galaxy Vibes Plus"}},
    ]


def trace(record: dict) -> dict:
    t0 = time.perf_counter()
    timings = {}
    rec = {"record_id": "BREAKIT-1", "supplier": "S6", "name": record.get("name") or "", "address": record.get("address"),
           "phone": record.get("phone"), "lat": record.get("lat"), "lng": record.get("lng"), "stars": record.get("stars"),
           "city": record.get("city") or "Dubai", "photos": []}
    try:
        rec["lat"] = float(rec["lat"]) if rec["lat"] not in (None, "") else None
        rec["lng"] = float(rec["lng"]) if rec["lng"] not in (None, "") else None
    except (TypeError, ValueError):
        rec["lat"] = rec["lng"] = None
    if not all(isinstance(rec[k], float) and math.isfinite(rec[k]) and abs(rec[k]) <= limit for k, limit in (("lat", 90), ("lng", 180))):
        rec["lat"] = rec["lng"] = None
    n = normalize.normalize_hotel(rec)
    room = normalize.parse_room(record.get("room_name") or "") if record.get("room_name") else None
    timings["parse_ms"] = (time.perf_counter() - t0) * 1000
    t1 = time.perf_counter()
    vec = blocking.embed([n])[0]
    rows, X, raw, p, cands = _score_candidates(n, vec)
    timings["candidates_ms"] = (time.perf_counter() - t1) * 1000
    st = DEMO.state
    by_cluster = {}
    for k, r in enumerate(rows):
        rid = st["norms"][r]["record_id"]
        tid = DEMO.record_cluster.get(rid)
        if tid is None:
            continue
        if tid not in by_cluster or raw[k] > raw[by_cluster[tid]]:
            by_cluster[tid] = k
    order = sorted(by_cluster.items(), key=lambda t: -raw[t[1]])[:8]
    cand_out = []
    for tid, k in order:
        r = rows[k]
        other = st["norms"][r]
        ex = explain(X[k], DEMO.matcher.contributions(X[k:k + 1])[0], n, other, float(p[k]), distinguishing_detail(n, other))
        cand_out.append({"tessera_id": tid, "name": DEMO.hotels[tid]["name"], "record_id": other["record_id"], "record_name": DEMO.rec_by_id[other["record_id"]]["name"],
                         "supplier": other["supplier"], "sources": sorted(cands[r]), "p": float(p[k]), "raw": float(raw[k]),
                         "band": DEMO.band_of(float(raw[k])), "explain": ex,
                         "dist_m": None if rec["lat"] is None else round(haversine_m(rec["lat"], rec["lng"], other["lat"], other["lng"]))})
    timings["score_ms"] = (time.perf_counter() - t1) * 1000 - timings["candidates_ms"]
    decision = {"route": "new_property", "reason": "No candidate is close enough: this looks like a new property."}
    if cand_out:
        best = cand_out[0]
        if best["band"] == "auto_merge":
            decision = {"route": "auto_merge", "tessera_id": best["tessera_id"], "name": best["name"], "p": best["p"],
                        "reason": f"Merged into {best['name']} (p = {best['p']:.3f} ≥ τ = {DEMO.current_risk['tau_accept']:.3f})."}
        elif best["band"] == "uncertain":
            item = {"pair_id": f"BREAKIT|{best['tessera_id']}", "a": rec, "b": DEMO.rec_by_id[best["record_id"]],
                    "p": best["p"], "subbrand_conflict": any(i["group"] == "subbrand" and i["value"] < 0 for i in best["explain"]["items"])}
            v = adjudicator.adjudicate([item]).get(item["pair_id"])
            if v and v["route"] == "llm":
                decision = {"route": "llm", "verdict": v["verdict"], "reason": v["reason"], "tessera_id": best["tessera_id"],
                            "name": best["name"], "p": best["p"], "llm_json": {"pair_id": item["pair_id"], "verdict": v["verdict"], "reason": v["reason"]}}
            else:
                decision = {"route": "review", "tessera_id": best["tessera_id"], "name": best["name"], "p": best["p"],
                            "reason": _review_reason(best["explain"]),
                            "llm_offline": not config.LLM_ENABLED, "llm_json": ({"verdict": v["verdict"], "reason": v["reason"]} if v else None)}
        else:
            decision["p"] = best["p"]
    # room match inside the chosen hotel
    room_match = None
    if room and decision.get("tessera_id") and (decision["route"] == "auto_merge" or decision.get("verdict") == "same"):
        h = DEMO.hotels[decision["tessera_id"]]
        ident = normalize.room_identity(room)
        best_g, best_s = None, -1e9
        for g in h.get("rooms") or []:
            s, conflict, missing = rooms.attr_score(ident, g["ident"])
            if not conflict and s > best_s:
                best_g, best_s = g, s
        if best_g:
            room_match = {"name": best_g["name"], "tier": "Primary" if all(ident.get(k) for k in ("class", "bed", "view")) else "Secondary",
                          "suppliers": best_g["suppliers"]}
    timings["total_ms"] = (time.perf_counter() - t0) * 1000
    METER.add_pairs(len(rows))
    return {"parsed": {"name_norm": n["name_norm"], "brand": n["brand"], "core_name": n["core_name"], "phone": n["phone"],
                       "city": n["city"], "addr_tokens": sorted(n["addr_tokens"])[:8], "room": room,
                       "room_identity": normalize.room_identity(room) if room else None},
            "n_candidates_raw": len(rows), "candidates": cand_out, "decision": decision, "room_match": room_match,
            "tau_accept": DEMO.current_risk["tau_accept"], "tau_reject": DEMO.current_risk["tau_reject"], "alpha": DEMO.alpha,
            "timings": {k: round(v, 1) for k, v in timings.items()}, "llm_enabled": config.LLM_ENABLED}


# ---------------------------------------------------------------- graph
def graph(city: str = "dubai") -> dict:
    nodes, links = [], []
    for tid, h in DEMO.hotels.items():
        if h["city"] != city:
            continue
        ms = [m for m in h["members"]]
        for m in ms:
            nodes.append({"id": m, "supplier": DEMO.norm_by_id[m]["supplier"] if m in DEMO.norm_by_id else "S6", "cluster": tid})
        for m in ms[1:]:
            links.append({"source": ms[0], "target": m})
    return {"nodes": nodes, "links": links, "clusters": sum(1 for h in DEMO.hotels.values() if h["city"] == city)}


# ---------------------------------------------------------------- onboarding
def integrate_rooms(hotel, supplier_rooms, raw_offers):
    """Reconcile the incoming inventory with the hotel's existing physical rooms and slots."""
    if not supplier_rooms:
        return
    groups = hotel.get("rooms", [])
    members = [m for g in groups for m in g["members"]]
    incoming = [offers.normalize_offer(o) for o in raw_offers]
    raw_names = {r["supplier_room_id"]: r["room_name"] for r in supplier_rooms}
    by_identity = {tuple(sorted(normalize.room_identity(normalize.parse_room(r["room_name"])).items())): r["supplier_room_id"] for r in supplier_rooms}
    # Retain the original pipeline's corrections of raw supplier room IDs.
    assigned = {}
    for g in groups:
        by_supplier = {m["supplier"]: m["supplier_room_id"] for m in g["members"]}
        for s in g["slots"]:
            for o in s["offers"]:
                assigned[o["offer_id"]] = by_supplier[o["supplier"]]
    for o in incoming:
        ident = normalize.room_identity(normalize.parse_room(o["room_name"]))
        assigned[o["offer_id"]] = by_identity.get(tuple(sorted(ident.items())), o["supplier_room_id"])
        o["raw_room_name"] = raw_names.get(o["supplier_room_id"], o["room_name"])
    inventory = [o for g in groups for s in g["slots"] for o in s["offers"]] + incoming
    combined = rooms.match_rooms(members + supplier_rooms)
    group_index = {m["supplier_room_id"]: i for i, g in enumerate(combined) for m in g["members"]}
    slots = defaultdict(list)
    for o in inventory:
        gi = group_index[assigned[o["offer_id"]]]
        slots[offers.slot_key(gi, o)].append({**o, "group": gi})
    for g in combined:
        g["slots"] = []
    for (gi, board, refundable, occupancy, nights), entries in sorted(slots.items()):
        hours = max((o.get("cancel_hours") or 0 for o in entries), default=0)
        combined[gi]["slots"].append({"key": [board, refundable, occupancy, nights], "board": board,
                                      "refundable": refundable, "offers": entries, "label": offers.slot_label(board, refundable, hours)})
    hotel["rooms"] = combined
    hotel["n_offers"] = len(inventory)


class Onboarder:
    def __init__(self):
        self.task: asyncio.Task | None = None

    def feed_summary(self) -> dict:
        feed = orjson.loads((config.WORLD_DIR / "novabeds_feed.json").read_bytes())
        return {"supplier": "S6", "name": feed["name"], "hotels": len(feed["hotels"]), "rooms": len(feed["rooms"]),
                "offers": len(feed["offers"]), "cities": sorted({normalize.canon_city(h["city"]) for h in feed["hotels"]})}

    async def start(self):
        if self.task and not self.task.done():
            return {"status": "running"}
        if DEMO.onboarding.get("status") == "done":
            return {"status": "done"}
        self.task = asyncio.create_task(self._guarded_run())
        return {"status": "started"}

    def cancel(self):
        if self.task and not self.task.done():
            self.task.cancel()

    async def _guarded_run(self):
        try:
            await self._run()
        except Exception as exc:
            DEMO.onboarding = {**DEMO.onboarding, "status": "error", "error": str(exc)}
            await HUB.broadcast("pipeline", "error", DEMO.onboarding)

    async def _run(self):
        loop = asyncio.get_running_loop()
        t_start = time.time()
        feed = orjson.loads((config.WORLD_DIR / "novabeds_feed.json").read_bytes())
        truth = orjson.loads((config.WORLD_DIR / "truth.json").read_bytes())["hotel_of_record"]
        feed_rooms, feed_offers = defaultdict(list), defaultdict(list)
        for room in feed["rooms"]:
            feed_rooms[room["record_id"]].append(room)
        for offer in feed["offers"]:
            feed_offers[offer["record_id"]].append(offer)
        recs = feed["hotels"]
        # interleave Dubai records so the graph keeps moving while counters cover every city
        dubai = [r for r in recs if normalize.canon_city(r["city"]) == "dubai"]
        other = [r for r in recs if normalize.canon_city(r["city"]) != "dubai"]
        ratio = max(1, len(other) // max(1, len(dubai)))
        ordered = []
        oi = 0
        for r in dubai:
            ordered.append(r)
            ordered += other[oi:oi + ratio]
            oi += ratio
        ordered += other[oi:]
        DEMO.onboarding = {"status": "running", "started": t_start}
        c = {"total": len(ordered), "parsed": 0, "candidates": 0, "candidate_true": 0, "true_pairs": 0, "scored": 0,
             "auto_merge": 0, "llm": 0, "review": 0, "new_cluster": 0, "clustered": 0, "violations": 0,
             "false_merges": 0, "elapsed": 0.0}
        DEMO.onboarding.update(counters=c, alpha=DEMO.alpha)
        await HUB.broadcast("pipeline", "start", {"counters": c, "feed": self.feed_summary()})
        norms = [normalize.normalize_hotel(r) for r in ordered]
        c["parsed"] = len(norms)
        await HUB.broadcast("pipeline", "progress", {"counters": c, "stage": "parsed"})
        vecs = await loop.run_in_executor(None, blocking.embed, norms)
        hashes_all = await loop.run_in_executor(None, blocking.photo_hashes, norms)
        # true pairs for recall (evaluation only)
        canon_members = defaultdict(set)
        for rid, h in truth.items():
            canon_members[h].add(rid)
        n_existing = len(DEMO.state["norms"])
        pace = config.ONBOARD_PACE_MS / 1000.0
        new_k = 0
        s6_in_cluster = set()
        for i, (r, n) in enumerate(zip(ordered, norms)):
            rows, X, raw, p, cands = await loop.run_in_executor(None, _score_candidates, n, vecs[i], hashes_all.get(r["record_id"]))
            true_h = truth.get(r["record_id"])
            true_existing = {m for m in canon_members.get(true_h, ()) if m in DEMO.row}
            c["true_pairs"] += len(true_existing)
            c["candidate_true"] += sum(1 for rr in rows if DEMO.state["norms"][rr]["record_id"] in true_existing)
            c["candidates"] += len(rows)
            c["scored"] += len(rows)
            METER.add_pairs(len(rows))
            best_tid, best_k = None, None
            for k, rr in enumerate(rows):
                tid = DEMO.record_cluster.get(DEMO.state["norms"][rr]["record_id"])
                if tid and (best_k is None or raw[k] > raw[best_k]):
                    best_tid, best_k = tid, k
            band = DEMO.band_of(float(raw[best_k])) if best_k is not None else "auto_reject"
            route, reason = band, None
            if band == "auto_merge" and best_tid in s6_in_cluster:
                route, reason = "review", "NovaBeds already mapped to this hotel (possible duplicate listing)"
            elif band == "uncertain":
                other_rec = DEMO.rec_by_id.get(DEMO.state["norms"][rows[best_k]]["record_id"])
                verdicts = await asyncio.to_thread(adjudicator.adjudicate, [{"pair_id": f"{r['record_id']}|{best_tid}", "a": r, "b": other_rec,
                                             "p": float(p[best_k]), "subbrand_conflict": bool(X[best_k][7])}])
                v = verdicts.get(f"{r['record_id']}|{best_tid}")
                if v and v["route"] == "llm":
                    route, reason = ("llm_merge" if v["verdict"] == "same" else "llm_new"), v["reason"]
                else:
                    route = "review"
            if route == "llm_merge" and best_tid in s6_in_cluster:
                route, reason = "review", "NovaBeds already mapped to this property"
            payload = {"record_id": r["record_id"], "name": r["name"], "city": n["city"], "p": float(p[best_k]) if best_k is not None else 0.0,
                       "candidates": len(rows), "sources": sorted(set().union(*[cands[x] for x in rows])) if rows else [],
                       "reason": reason}
            if route in ("auto_merge", "llm_merge"):
                h = copy.deepcopy(DEMO.hotels[best_tid])
                h["members"].append(r["record_id"])
                if "S6" not in h["suppliers"]:
                    h["suppliers"].append("S6")
                DEMO.record_cluster[r["record_id"]] = best_tid
                s6_in_cluster.add(best_tid)
                h["n_records"] = len(h["members"])
                DEMO.hotels[best_tid] = h
                c["auto_merge" if route == "auto_merge" else "llm"] += 1
                c["clustered"] += 1
                majority = [truth.get(m) for m in h["members"] if m != r["record_id"]]
                c["false_merges"] += int(bool(majority) and true_h != max(set(majority), key=majority.count))
                payload.update({"decision": "auto_merge" if route == "auto_merge" else "llm", "tessera_id": best_tid,
                                "cluster_name": h["name"], "link_to": h["members"][0]})
            elif route in ("auto_reject", "llm_new"):
                new_k += 1
                tid = f"TS-N{new_k:04d}"
                DEMO.hotels[tid] = {"tessera_id": tid, "name": normalize.clean_name(r["name"]).title(), "brand": n["brand"],
                                    "stars": r.get("stars"), "city": n["city"], "neighbourhood": neighbourhood_of(n["city"], r["lat"], r["lng"]), "lat": r["lat"], "lng": r["lng"],
                                    "phone": n["phone"], "address": r.get("address"), "members": [r["record_id"]],
                                    "suppliers": ["S6"], "n_records": 1, "dups": [], "new": True}
                DEMO.record_cluster[r["record_id"]] = tid
                c["new_cluster"] += 1
                c["clustered"] += 1
                if route == "llm_new":
                    c["llm"] += 1
                payload.update({"decision": "new_cluster", "tessera_id": tid})
            else:
                c["review"] += 1
                payload.update({"decision": "review", "tessera_id": best_tid,
                                "cluster_name": DEMO.hotels[best_tid]["name"] if best_tid else None})
            if r["record_id"] in DEMO.record_cluster:
                DEMO.rec_by_id[r["record_id"]] = r
                DEMO.norm_by_id[r["record_id"]] = n
                mapped = DEMO.hotels[DEMO.record_cluster[r["record_id"]]]
                integrate_rooms(mapped, feed_rooms[r["record_id"]], feed_offers[r["record_id"]])
            c["elapsed"] = time.time() - t_start
            payload["supplier"] = "S6"
            await HUB.broadcast("pipeline", "decision", payload)
            if i % 6 == 0 or i == len(ordered) - 1:
                c["recall"] = c["candidate_true"] / max(1, c["true_pairs"])
                c["reduction"] = 1 - c["candidates"] / max(1, (i + 1) * n_existing)
                await HUB.broadcast("pipeline", "progress", {"counters": c, "stage": "deciding"})
            await asyncio.sleep(pace)
        c["recall"] = c["candidate_true"] / max(1, c["true_pairs"])
        c["reduction"] = 1 - c["candidates"] / max(1, len(ordered) * n_existing)
        # consistency: supplier exclusivity on every touched cluster
        viol = 0
        for h in DEMO.hotels.values():
            sups = [DEMO.norm_by_id[m]["supplier"] if m in DEMO.norm_by_id else "S6" for m in h["members"] if m not in DEMO.state["alias"]]
            viol += len(sups) - len(set(sups))
        c["violations"] = viol
        c["elapsed"] = time.time() - t_start
        DEMO.hotel_table = ranking.hotel_table({**DEMO.state, "recs": list(DEMO.rec_by_id.values())})
        from app.services.simulator import SIM
        SIM.prepare()
        DEMO.onboarding = {"status": "done", "risk": DEMO.current_risk, "counters": c, "alpha": DEMO.alpha}
        await HUB.broadcast("pipeline", "done", {"risk": DEMO.current_risk, "counters": c, "alpha": DEMO.alpha, "llm_enabled": config.LLM_ENABLED})


ONBOARDER = Onboarder()
