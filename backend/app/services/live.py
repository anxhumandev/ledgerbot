"""Live pipeline: score one record against the catalog without changing it (Match tester; used by ingestion)."""
from __future__ import annotations

import math
import time

import numpy as np

from app import config
from app.demo import DEMO
from app.pipeline import adjudicator, blocking, normalize, rooms
from app.pipeline.cost import METER
from app.pipeline.features import distinguishing_detail, haversine_m, pair_features
from app.pipeline.matcher import explain


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
