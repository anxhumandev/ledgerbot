"""Content enrichment: TruthFinder-lite truth discovery, pHash photo dedup, hero image pick."""
from __future__ import annotations

import re
from collections import defaultdict

import numpy as np
import orjson

from app import config
from app.pipeline.blocking import popcount64
from app.pipeline.features import haversine_m

INIT_TRUST = {"S1": 0.9}
ATTRS = ("stars", "phone", "address", "coords")
CATEGORY_PRIOR = {"exterior": 1.0, "lobby": 0.9, "pool": 0.85, "view": 0.8, "restaurant": 0.7, "room": 0.65, "bathroom": 0.4}


def _addr_key(n: dict):
    return " ".join(sorted(n["addr_tokens"])) if n["addr_tokens"] else None


def truth_discovery(clusters: list[list[dict]], iters: int = 6) -> tuple[dict, list[dict]]:
    """clusters: list of lists of normalized records. Returns (trust per supplier, consensus per cluster)."""
    sups = sorted({n["supplier"] for c in clusters for n in c})
    trust = {s: INIT_TRUST.get(s, 0.7) for s in sups}
    consensus = []
    for _ in range(iters):
        agree, total = defaultdict(float), defaultdict(float)
        consensus = []
        for c in clusters:
            cons = {}
            for attr in ATTRS:
                if attr == "coords":
                    pts = [(n["lat"], n["lng"], trust[n["supplier"]]) for n in c if n.get("lat") is not None]
                    if not pts:
                        continue
                    cons["coords"] = (_wmedian([p[0] for p in pts], [p[2] for p in pts]),
                                      _wmedian([p[1] for p in pts], [p[2] for p in pts]))
                    continue
                votes = defaultdict(float)
                for n in c:
                    v = _addr_key(n) if attr == "address" else n.get(attr)
                    if v is not None:
                        votes[v] += trust[n["supplier"]]
                if votes:
                    cons[attr] = max(votes.items(), key=lambda t: (t[1], str(t[0])))[0]
            consensus.append(cons)
            if len(c) < 2:
                continue
            for n in c:
                for attr in ATTRS:
                    if attr not in cons:
                        continue
                    if attr == "coords":
                        if n.get("lat") is None:
                            continue
                        ok = haversine_m(n["lat"], n["lng"], *cons["coords"]) <= 60
                    else:
                        v = _addr_key(n) if attr == "address" else n.get(attr)
                        if v is None:
                            continue
                        ok = v == cons[attr]
                    agree[n["supplier"]] += ok
                    total[n["supplier"]] += 1
        trust = {s: (agree[s] / total[s] if total[s] else trust[s]) for s in sups}
    return trust, consensus


def _wmedian(vals, ws):
    o = np.argsort(vals)
    v, w = np.array(vals)[o], np.array(ws)[o]
    c = np.cumsum(w)
    return float(v[np.searchsorted(c, c[-1] / 2)])


# ---------------------------------------------------------------- photos
_SHARP = None


def _sharpness_cache():
    global _SHARP
    if _SHARP is None:
        p = config.CACHE_DIR / "sharpness.json"
        _SHARP = orjson.loads(p.read_bytes()) if p.exists() else {}
    return _SHARP


def sharpness(url: str) -> float:
    cache = _sharpness_cache()
    if url not in cache:
        from PIL import Image
        img = np.asarray(Image.open(config.FRONTEND_PUBLIC / url.lstrip("/")).convert("L"), dtype=np.float32)
        lap = (-4 * img[1:-1, 1:-1] + img[:-2, 1:-1] + img[2:, 1:-1] + img[1:-1, :-2] + img[1:-1, 2:])
        cache[url] = float(lap.var())
    return cache[url]


def save_sharpness():
    if _SHARP is not None:
        (config.CACHE_DIR / "sharpness.json").write_bytes(orjson.dumps(_SHARP))


def tag_of(url: str) -> str:
    m = re.search(r"_([a-z]+)\.jpg$", url)
    return m.group(1) if m else "room"


def dedup_photos(records: list[dict], phash_of: dict[str, int]) -> dict:
    """records: raw supplier records in one cluster. Groups photos with Hamming <= 8, keeps the largest."""
    photos = []
    for r in records:
        for p in r.get("photos", []):
            if p["url"] in phash_of:
                photos.append({**p, "supplier": r["supplier"], "hash": phash_of[p["url"]]})
    if not photos:
        return {"total": 0, "unique": [], "hero": None, "suppliers": 0}
    hs = np.array([p["hash"] for p in photos], dtype=np.uint64)
    parent = list(range(len(photos)))

    def f(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i in range(len(photos)):
        d = popcount64(hs ^ hs[i])
        for j in np.where(d <= 8)[0]:
            if j > i:
                parent[f(int(j))] = f(i)
    groups = defaultdict(list)
    for i in range(len(photos)):
        groups[f(i)].append(photos[i])
    unique = []
    for g in groups.values():
        best = max(g, key=lambda p: (p["w"] * p["h"], p["url"]))  # keep the highest-resolution copy
        tag = tag_of(best["url"])
        sharp = sharpness(best["url"])
        res = min(1.0, best["w"] / 720.0)
        score = (sharp ** 0.5) * (0.5 + 0.5 * res) * CATEGORY_PRIOR.get(tag, 0.5)
        unique.append({"url": best["url"], "w": best["w"], "tag": tag, "copies": len(g),
                       "suppliers": sorted({p["supplier"] for p in g}), "score": round(score, 3),
                       "members": [p["url"] for p in g]})
    unique.sort(key=lambda p: -p["score"])
    return {"total": len(photos), "unique": unique, "hero": unique[0]["url"],
            "suppliers": len({p["supplier"] for p in photos})}
