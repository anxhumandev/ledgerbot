"""Pair features for hotel matching."""
from __future__ import annotations

import math

import numpy as np
from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler

from app.pipeline.blocking import popcount64

FEATURES = [
    "jw_core", "tsr_name", "pr_core", "emb_cos", "core_equal", "brand_equal", "brand_conflict",
    "subbrand_conflict", "n_distinct", "core_jacc", "dist_m", "log_dist", "phone_exact", "phone_last7",
    "phone_conflict", "phone_missing",
    "addr_jacc", "star_diff", "photo_matches", "missing_count",
]
# monotone constraints for LightGBM (+1 increasing evidence of a match, -1 decreasing, 0 free)
MONOTONE = {
    "jw_core": 1, "tsr_name": 1, "pr_core": 1, "emb_cos": 1, "core_equal": 1, "brand_equal": 1,
    "brand_conflict": -1, "subbrand_conflict": -1, "n_distinct": 0, "core_jacc": 1, "phone_conflict": -1, "dist_m": -1, "log_dist": -1,
    "phone_exact": 1, "phone_last7": 1, "phone_missing": 0, "addr_jacc": 1, "star_diff": -1,
    "photo_matches": 1, "missing_count": 0,
}
# tokens too generic to signal a different property
SOFT_TOKENS = {"city", "centre", "road", "street", "dubai", "residence", "towers", "tower", "&", "and"}


def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def distinct_tokens(a: list[str], b: list[str]) -> tuple[list[str], list[str]]:
    """Tokens of a with no fuzzy counterpart in b (and vice versa)."""
    def unmatched(x, y):
        out = []
        for t in x:
            if len(t) < 2:
                continue
            if t in y or any(fuzz.ratio(t, u) >= 80 for u in y):
                continue
            out.append(t)
        return out
    return unmatched(a, b), unmatched(b, a)


def pair_features(na: dict, nb: dict, cos: float, hashes_a=None, hashes_b=None) -> list[float]:
    ca, cb = na["core_name"], nb["core_name"]
    jw = JaroWinkler.similarity(ca, cb) if (ca and cb) else (1.0 if ca == cb else 0.0)
    tsr = fuzz.token_set_ratio(na["match_name"], nb["match_name"]) / 100.0
    pr = fuzz.partial_ratio(ca, cb) / 100.0 if (ca and cb) else (1.0 if ca == cb else 0.0)
    core_equal = float(ca == cb)
    ba, bb = na["brand"], nb["brand"]
    brand_equal = float(bool(ba) and ba == bb)
    brand_conflict = float(bool(ba) and bool(bb) and ba != bb)
    da, db = distinct_tokens(na["core_tokens"], nb["core_tokens"])
    hard_a = [t for t in da if t not in SOFT_TOKENS]
    hard_b = [t for t in db if t not in SOFT_TOKENS]
    sub_conf = float(bool(hard_a) and bool(hard_b))
    n_distinct = float(len(da) + len(db))
    sa_t, sb_t = set(na["core_tokens"]), set(nb["core_tokens"])
    core_jacc = len(sa_t & sb_t) / len(sa_t | sb_t) if (sa_t or sb_t) else 1.0
    d = haversine_m(na["lat"], na["lng"], nb["lat"], nb["lng"])
    pa, pb = na["phone"], nb["phone"]
    phone_missing = float(not pa or not pb)
    phone_exact = float(bool(pa) and pa == pb)
    phone_last7 = float(bool(pa) and bool(pb) and pa[-7:] == pb[-7:])
    phone_conflict = float(bool(pa) and bool(pb) and pa[-7:] != pb[-7:])
    ta, tb = na["addr_tokens"], nb["addr_tokens"]
    addr = len(ta & tb) / len(ta | tb) if (ta and tb) else 0.0
    sa, sb = na.get("stars"), nb.get("stars")
    star_diff = float(abs(sa - sb)) if (sa and sb) else 0.0
    ph = 0.0
    if hashes_a and hashes_b:
        A = np.array(hashes_a, dtype=np.uint64)
        for h in hashes_b:
            ph += float((popcount64(A ^ np.uint64(h)) <= 8).any())
    return [jw, tsr, pr, float(cos), core_equal, brand_equal, brand_conflict, sub_conf, n_distinct, core_jacc, d,
            math.log1p(d), phone_exact, phone_last7, phone_conflict, phone_missing, addr, star_diff, ph,
            float(na["missing"] + nb["missing"])]


def feature_matrix(pairs, norms, emb, hashes) -> np.ndarray:
    X = np.zeros((len(pairs), len(FEATURES)), dtype=np.float32)
    for k, (i, j) in enumerate(pairs):
        na, nb = norms[i], norms[j]
        cos = float(emb[i] @ emb[j])
        X[k] = pair_features(na, nb, cos, hashes.get(na["record_id"]), hashes.get(nb["record_id"]))
    return X


def distinguishing_detail(na: dict, nb: dict) -> tuple[list[str], list[str]]:
    da, db = distinct_tokens(na["core_tokens"], nb["core_tokens"])
    return [t for t in da if t not in SOFT_TOKENS], [t for t in db if t not in SOFT_TOKENS]


PHONE_COLS = [FEATURES.index(f) for f in ("phone_exact", "phone_last7", "phone_conflict")]
PHONE_MISSING = FEATURES.index("phone_missing")
MISSING_COUNT = FEATURES.index("missing_count")


def mask_phone(X: np.ndarray) -> np.ndarray:
    """Augmentation: pretend one side's phone is missing (common in real feeds)."""
    Y = X.copy()
    Y[:, PHONE_COLS] = 0.0
    Y[:, MISSING_COUNT] += (1.0 - Y[:, PHONE_MISSING])
    Y[:, PHONE_MISSING] = 1.0
    return Y
