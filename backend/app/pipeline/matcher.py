"""LightGBM pair matcher + isotonic calibration + per-pair explanations."""
from __future__ import annotations

import pickle
import time

import lightgbm as lgb
import numpy as np
from sklearn.isotonic import IsotonicRegression

from app import config
from app.pipeline.features import FEATURES, MONOTONE

PARAMS = {
    "objective": "binary", "learning_rate": 0.05, "num_leaves": 15, "min_child_samples": 10,
    "feature_fraction": 0.9, "bagging_fraction": 0.9, "bagging_freq": 1, "lambda_l2": 1.0,
    "monotone_constraints": [MONOTONE[f] for f in FEATURES], "monotone_constraints_method": "advanced",
    "verbose": -1, "seed": config.SEED, "deterministic": True, "force_row_wise": True, "num_threads": 4,
}
N_ROUNDS = 350


class Matcher:
    def __init__(self, booster: lgb.Booster, calibrator: IsotonicRegression | None):
        self.booster = booster
        self.calibrator = calibrator

    # raw = booster probability; p = calibrated probability
    def raw(self, X: np.ndarray) -> np.ndarray:
        if len(X) == 0:
            return np.zeros(0)
        return self.booster.predict(X)

    def calibrate(self, raw: np.ndarray) -> np.ndarray:
        if self.calibrator is None or len(raw) == 0:
            return raw
        return np.clip(self.calibrator.predict(raw), 0.0005, 0.9995)

    def predict(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        r = self.raw(X)
        return r, self.calibrate(r)

    def contributions(self, X: np.ndarray) -> np.ndarray:
        return self.booster.predict(X, pred_contrib=True)

    def save(self):
        self.booster.save_model(str(config.CACHE_DIR / "matcher.txt"))
        with open(config.CACHE_DIR / "calibrator.pkl", "wb") as f:
            pickle.dump(self.calibrator, f)

    @classmethod
    def load(cls) -> "Matcher":
        b = lgb.Booster(model_file=str(config.CACHE_DIR / "matcher.txt"))
        with open(config.CACHE_DIR / "calibrator.pkl", "rb") as f:
            cal = pickle.load(f)
        return cls(b, cal)


def train(X: np.ndarray, y: np.ndarray, w: np.ndarray | None = None) -> lgb.Booster:
    t0 = time.time()
    ds = lgb.Dataset(X, label=y, weight=w, feature_name=FEATURES, free_raw_data=False)
    b = lgb.train(PARAMS, ds, num_boost_round=N_ROUNDS)
    print(f"  matcher trained on {len(y)} pairs ({int(y.sum())} positive) in {time.time() - t0:.1f}s")
    return b


def fit_calibrator(raw: np.ndarray, y: np.ndarray) -> IsotonicRegression:
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0, increasing=True)
    iso.fit(raw, y)
    return iso


# ---------------------------------------------------------------- explanations
GROUPS = {
    "name": ["jw_core", "tsr_name", "pr_core", "emb_cos", "core_equal", "n_distinct", "core_jacc"],
    "brand": ["brand_equal", "brand_conflict"],
    "subbrand": ["subbrand_conflict"],
    "distance": ["dist_m", "log_dist"],
    "phone": ["phone_exact", "phone_last7", "phone_conflict", "phone_missing"],
    "address": ["addr_jacc"],
    "stars": ["star_diff"],
    "photos": ["photo_matches"],
    "quality": ["missing_count"],
}
FIDX = {f: i for i, f in enumerate(FEATURES)}


def explain(x: np.ndarray, contrib: np.ndarray, na: dict, nb: dict, p: float, detail=None) -> dict:
    """Turn LightGBM contributions into human phrases for the Explain waterfall."""
    def v(f):
        return float(x[FIDX[f]])

    items = []
    for g, feats in GROUPS.items():
        c = float(sum(contrib[FIDX[f]] for f in feats))
        if abs(c) < 0.05:
            continue
        if g == "name":
            label = f"Name similarity {v('tsr_name'):.2f}"
        elif g == "brand":
            if v("brand_conflict"):
                label = f"Brand conflict: {na['brand']} vs {nb['brand']}"
            elif v("brand_equal"):
                label = f"Same brand: {na['brand']}"
            else:
                label = "Brand unknown on one side"
        elif g == "subbrand":
            if v("subbrand_conflict") and detail:
                a, b = detail
                label = f"Sub-brand conflict: '{' '.join(a).title()}' vs '{' '.join(b).title()}'"
            elif v("subbrand_conflict"):
                label = "Sub-brand conflict"
            else:
                label = "No distinguishing tokens"
        elif g == "distance":
            d = v("dist_m")
            label = f"{d:,.0f} m apart" if d < 10000 else f"{d / 1000:,.1f} km apart"
        elif g == "phone":
            if v("phone_exact"):
                label = "Same phone number"
            elif v("phone_last7"):
                label = "Phone matches (last 7 digits)"
            elif v("phone_missing"):
                label = "Phone missing on one side"
            else:
                label = "Different phone numbers"
        elif g == "address":
            label = f"Address overlap {v('addr_jacc'):.0%}"
        elif g == "stars":
            label = "Same star rating" if v("star_diff") == 0 else f"Star mismatch ({na.get('stars')}★ vs {nb.get('stars')}★)"
        elif g == "photos":
            n = int(v("photo_matches"))
            label = f"{n} shared photo{'s' if n != 1 else ''}" if n else "No shared photos"
        else:
            label = "Missing fields" if v("missing_count") else "Complete records"
        items.append({"group": g, "label": label, "value": round(c, 2)})
    items.sort(key=lambda t: -abs(t["value"]))
    return {"base": round(float(contrib[-1]), 2), "items": items, "p": round(float(p), 4)}
