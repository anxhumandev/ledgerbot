"""Analyst tooling: the human review queue (active learning) and hotel search.

Review queue: the record pairs LedgerBot refused to decide automatically (the uncertain band between the certified
reject and accept thresholds), ordered most-uncertain first so each human decision teaches the model the most.
Every decision is kept as a gold label for the next calibration and retraining run.

Search: find any golden record by its canonical name or by any supplier's spelling of it.
"""
from __future__ import annotations

import time
from statistics import median

import numpy as np
from rapidfuzz import fuzz, process

from app.demo import DEMO
from app.pipeline.features import haversine_m
from app.services.views import explain_records, record_view

_CACHE: dict = {}


def _queue_pairs() -> list[tuple[str, str, float]]:
    key = (id(DEMO.state.get("band")), DEMO.tau_accept_raw, DEMO.tau_reject_raw)
    if _CACHE.get("key") == key:
        return _CACHE["pairs"]
    st = DEMO.state
    rid = [n["record_id"] for n in st["norms"]]
    raw = st["raw"]
    idx = np.where((raw > DEMO.tau_reject_raw) & (raw < DEMO.tau_accept_raw))[0]
    p = st["p"]
    # uncertainty sampling: closest to 50/50 first
    order = sorted(idx.tolist(), key=lambda k: abs(float(p[k]) - 0.5))
    pairs = [(rid[st["pairs"][k][0]], rid[st["pairs"][k][1]], float(p[k])) for k in order]
    _CACHE.update(key=key, pairs=pairs)
    return pairs


def _diffs(a: dict, b: dict) -> list[dict]:
    rows = []
    for f, label in (("name", "Name"), ("address", "Address"), ("phone_e164", "Phone"), ("stars", "Stars")):
        va, vb = a.get(f), b.get(f)
        state = "missing" if va in (None, "") or vb in (None, "") else ("same" if str(va).lower() == str(vb).lower() else "different")
        if f == "name" and state == "different" and fuzz.token_set_ratio(str(va), str(vb)) >= 90:
            state = "similar"
        rows.append({"field": label, "a": a.get("phone") if f == "phone_e164" else va, "b": b.get("phone") if f == "phone_e164" else vb, "state": state})
    if None not in (a.get("lat"), b.get("lat")):
        d = haversine_m(a["lat"], a["lng"], b["lat"], b["lng"])
        rows.append({"field": "Location", "a": f"{a['lat']:.4f}, {a['lng']:.4f}", "b": f"{b['lat']:.4f}, {b['lng']:.4f}",
                     "state": "same" if d <= 150 else "different", "note": f"{d:,.0f} m apart"})
    return rows


def queue(limit: int = 40) -> dict:
    pairs = _queue_pairs()
    log = DEMO.review_log
    items = []
    for a, b, p in pairs:
        pid = f"{a}|{b}"
        if pid in log or len(items) >= limit:
            continue
        ex = explain_records(a, b)
        A, B = record_view(a), record_view(b)
        lean = "same" if p >= 0.5 else "different"
        items.append({"pair_id": pid, "a": A, "b": B, "p": p, "lean": lean, "explain": ex, "diffs": _diffs(A, B),
                      "hotel_a": DEMO.hotels.get(DEMO.record_cluster.get(a), {}).get("name"),
                      "hotel_b": DEMO.hotels.get(DEMO.record_cluster.get(b), {}).get("name")})
    return {"items": items, "stats": stats(), "tau_accept": DEMO.current_risk.get("tau_accept"),
            "tau_reject": DEMO.current_risk.get("tau_reject"), "alpha": DEMO.alpha}


def decide(pair_id: str, verdict: str, seconds: float | None = None) -> dict:
    if verdict not in ("same", "different", "skip"):
        raise ValueError("verdict must be same, different or skip")
    DEMO.review_log[pair_id] = {"verdict": verdict, "seconds": seconds, "at": time.time()}
    return stats()


def undo(pair_id: str) -> dict:
    DEMO.review_log.pop(pair_id, None)
    return stats()


def stats() -> dict:
    log = DEMO.review_log
    total = len(_queue_pairs())
    decided = [v for v in log.values() if v["verdict"] != "skip"]
    secs = [v["seconds"] for v in decided if v.get("seconds")]
    return {"total": total, "reviewed": len(decided), "skipped": sum(v["verdict"] == "skip" for v in log.values()),
            "remaining": max(0, total - len(log)), "same": sum(v["verdict"] == "same" for v in decided),
            "different": sum(v["verdict"] == "different" for v in decided),
            "median_seconds": round(median(secs), 1) if secs else None}


# ---------------------------------------------------------------- search
def _search_index():
    if "search" not in _CACHE or _CACHE.get("search_n") != len(DEMO.hotels):
        keys, owners = [], []
        for tid, h in DEMO.hotels.items():
            keys.append(h["name"])
            owners.append(tid)
            for m in h["members"]:
                r = DEMO.rec_by_id.get(m)
                if r and r["name"] != h["name"]:
                    keys.append(r["name"])
                    owners.append(tid)
        _CACHE.update(search=(keys, owners), search_n=len(DEMO.hotels))
    return _CACHE["search"]


def search(q: str, limit: int = 8) -> list[dict]:
    q = (q or "").strip()
    if len(q) < 2:
        return []
    keys, owners = _search_index()
    hits = process.extract(q, keys, scorer=fuzz.WRatio, limit=limit * 4, processor=str.lower)
    out, seen = [], set()
    for key, score, i in hits:
        tid = owners[i]
        if tid in seen or score < 55:
            continue
        seen.add(tid)
        h = DEMO.hotels[tid]
        out.append({"tessera_id": tid, "name": h["name"], "matched": key, "score": round(score), "city": h["city"],
                    "neighbourhood": h.get("neighbourhood"), "stars": h.get("stars"), "suppliers": h["suppliers"],
                    "n_records": h["n_records"]})
        if len(out) >= limit:
            break
    return out
