"""Analyst helpers: the current review band (record pairs between the certified reject and accept thresholds,
most uncertain first; persisted as cases by services/review.py), field diffs for a pair, and fuzzy search over every
supplier's spelling of a property."""
from __future__ import annotations

import numpy as np
from rapidfuzz import fuzz, process

from app.demo import DEMO
from app.pipeline.features import haversine_m

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
