"""Learning to rank for agent personas, with position-bias correction (Joachims et al., WSDM 2017).

Clicks in the logs are biased by position. Propensities are estimated from the 5% of sessions the
platform randomized, then click-through rates are re-weighted by 1/propensity (IPW). Both a naive and
an IPW LambdaRank model are trained; NDCG@10 is measured against the hidden *true* relevance.
"""
from __future__ import annotations

import hashlib
import math
import pickle
from collections import defaultdict

import lightgbm as lgb
import numpy as np
import orjson
import pandas as pd
from scipy.stats import kendalltau

from app import config
from app.pipeline import offers as off
from data.tables import CITIES, PERSONAS

PERSONA = {p["id"]: p for p in PERSONAS}
FEATS = ["price_log", "price_rel_median", "price_rank", "stars", "star_gap", "review", "dist_pref_km", "in_pref_area",
         "budget_ratio", "refundable", "refundable_need", "breakfast", "breakfast_aff", "suite", "suite_aff",
         "reliability", "popularity", "refundable_available", "refundable_avail_need", "breakfast_available", "breakfast_avail_aff"]
NB_CENTER = {nb: ((a + b) / 2, (c + d) / 2) for nb, (a, b, c, d) in CITIES["dubai"]["neighbourhoods"].items()}
MODEL_PATH = config.CACHE_DIR / "ranking.pkl"


def km(lat1, lng1, lat2, lng2):
    return math.hypot((lat1 - lat2) * 111.3, (lng1 - lng2) * 111.3 * math.cos(math.radians(lat1)))


def lead_offer(h: dict, p_success, cap_pct: float = config.DEFAULT_PRICE_CAP_PCT, paused: frozenset = frozenset()) -> dict | None:
    """The offer a search result shows for this hotel: in each comparable group (room x board x refundability) the
    eligible expected-value winner (cheapest available offer sets the competitiveness baseline; paused suppliers
    excluded); across groups, the cheapest of those winners. Its price, supplier and terms are one coherent offer."""
    best = None
    for g in h.get("rooms") or []:
        for s in g["slots"]:
            avail = [o for o in s["offers"] if o["supplier"] not in paused]
            if not avail:
                continue
            scored = off.score_slot(avail, p_success)
            base = min(o["price"] for o in scored)
            elig = [o for o in scored if (o["price"] / base - 1) * 100 <= cap_pct + 1e-9]
            w = max(elig, key=lambda o: (o["ev"], -o["price"]))
            if best is None or w["price"] < best["price"]:
                best = w
    return best


def hotel_table(state: dict, p_success=None, cap_pct: float | None = None, paused=frozenset()) -> dict:
    """Per Dubai hotel: content features plus the attributes of ONE coherent lead offer (price, supplier, meal plan,
    refundability all describe the same bookable offer). What the hotel offers at other price points is modelled
    separately as availability flags (refundable_available, breakfast_available)."""
    recs = {r["record_id"]: r for r in state["recs"]}
    if p_success is None:
        prior = {c: v["profile"]["confirm"] * (1 - v["profile"]["price_jump"]) for c, v in config.SUPPLIERS.items()}
        p_success = lambda c: prior.get(c, 0.97)  # noqa: E731
    cap = config.DEFAULT_PRICE_CAP_PCT if cap_pct is None else cap_pct
    out = {}
    for tid, h in state["hotels"].items():
        if h["city"] != "dubai" or not h.get("rooms"):
            continue
        lead = lead_offer(h, p_success, cap, frozenset(paused))
        if lead is None:
            continue
        offers = [o for g in h["rooms"] for s in g["slots"] for o in s["offers"]]
        reviews = [recs[r]["review_score"] for r in h["members"] if r in recs and recs[r].get("review_score")]
        out[tid] = {
            "tid": tid, "name": h["name"], "stars": h["stars"] or 3, "neighbourhood": h["neighbourhood"],
            "lat": h["lat"], "lng": h["lng"],
            # the lead offer
            "price": lead["price"], "head_supplier": lead["supplier"], "lead_offer_id": lead["offer_id"],
            "refundable": bool(lead["refundable"]), "breakfast": lead["board"] in ("BB", "HB", "FB", "AI"),
            "lead_board": lead["board"], "lead_cancel_hours": lead.get("cancel_hours") if lead["refundable"] else None,
            "lead_payment": lead.get("payment"),
            "margin": lead["price"] * config.SUPPLIERS[lead["supplier"]]["take_rate"],
            # availability at any price point, kept separate from the lead offer
            "refundable_available": any(o["refundable"] for o in offers),
            "breakfast_available": any(o["board"] in ("BB", "HB", "FB", "AI") for o in offers),
            "suite": any(g["ident"].get("class") in ("Junior Suite", "Suite", "Villa") for g in h["rooms"]),
            "review": float(np.mean(reviews)) if reviews else 7.8,
            "platinum": any(recs[r].get("platinum") for r in h["members"] if r in recs),
            "hero": (h.get("photos") or {}).get("hero"),
        }
    return out


def features_for(persona: dict, rows: list[dict], reliability: dict, popularity: dict) -> np.ndarray:
    prices = np.array([r["price"] for r in rows], dtype=float)
    med = float(np.median(prices)) if len(prices) else 1.0
    ranks = prices.argsort().argsort() / max(1, len(rows) - 1)
    X = np.zeros((len(rows), len(FEATS)), dtype=np.float32)
    for i, r in enumerate(rows):
        d = min(km(r["lat"], r["lng"], *NB_CENTER[a]) for a in persona["areas"])
        X[i] = [math.log(r["price"]), r["price"] / med, ranks[i], r["stars"], abs(r["stars"] - persona["stars"]),
                r["review"], d, float(r["neighbourhood"] in persona["areas"]), math.log(r["price"] / persona["budget"]),
                float(r["refundable"]), float(r["refundable"]) * persona["refundable"], float(r["breakfast"]),
                float(r["breakfast"]) * persona["breakfast"], float(r["suite"]), float(r["suite"]) * persona["suite"],
                reliability.get(r["head_supplier"], 0.97), popularity.get(r["tid"], 0.0),
                float(r["refundable_available"]), float(r["refundable_available"]) * persona["refundable"],
                float(r["breakfast_available"]), float(r["breakfast_available"]) * persona["breakfast"]]
    return X


def _split(tid: str) -> str:
    return "test" if int(hashlib.md5(tid.encode()).hexdigest(), 16) % 10 < 3 else "train"


def ndcg_at(scores, grades, k=10):
    order = np.argsort(-scores)[:k]
    gains = (2 ** np.asarray(grades)[order] - 1) / np.log2(np.arange(2, len(order) + 2))
    ideal = np.sort(np.asarray(grades))[::-1][:k]
    idcg = ((2 ** ideal - 1) / np.log2(np.arange(2, len(ideal) + 2))).sum()
    return float(gains.sum() / idcg) if idcg > 0 else 0.0


def train(state: dict) -> dict:
    logs = pd.read_parquet(config.WORLD_DIR / "search_logs.parquet")
    truth = orjson.loads((config.WORLD_DIR / "truth.json").read_bytes())
    rc = state["record_cluster"]
    logs["tid"] = logs["listing_id"].map(rc)
    logs = logs.dropna(subset=["tid"])
    table = hotel_table(state)
    logs = logs[logs.tid.isin(table)]

    # ---- propensities from randomized sessions: CTR(k)/CTR(1), fitted as k^-eta
    rnd = logs[logs.randomized]
    ctr = rnd.groupby("position").click.mean()
    pos = ctr.index.values.astype(float)
    rel_ctr = np.clip(ctr.values / max(ctr.values[0], 1e-6), 1e-4, None)
    eta = float(-np.polyfit(np.log(pos), np.log(rel_ctr), 1)[0])
    prop = {int(k): float(k ** -eta) for k in range(1, 21)}

    pop = np.log1p(logs.groupby("tid").size())
    popularity = (pop / pop.max()).to_dict()
    nonrand = logs[~logs.randomized].copy()
    nonrand["w"] = 1.0 / nonrand.position.map(prop)
    agg = nonrand.groupby(["persona", "tid"]).agg(imp=("click", "size"), clicks=("click", "sum"))
    agg["ipw_clicks"] = (nonrand.click * nonrand.w).groupby([nonrand.persona, nonrand.tid]).sum()
    agg["naive"] = agg.clicks / agg.imp
    agg["ipw"] = agg.ipw_clicks / agg.imp
    reliability0 = {c: v["profile"]["confirm"] * (1 - v["profile"]["price_jump"]) for c, v in config.SUPPLIERS.items()}

    # canonical mapping for evaluation only
    canon_of = {}
    for tid, h in state["hotels"].items():
        if tid in table:
            hs = [truth["hotel_of_record"][r] for r in h["members"]]
            canon_of[tid] = max(set(hs), key=hs.count)
    models, evals = {}, {}
    for kind in ("naive", "ipw"):
        # Paired comparison: both learners see identical training slates and held-out queries.
        rng = np.random.default_rng(config.SEED)
        Xs, ys, groups = [], [], []
        for p in PERSONAS:
            sub = agg.loc[p["id"]] if p["id"] in agg.index.get_level_values(0) else None
            if sub is None:
                continue
            sub = sub[sub.imp >= 3]
            tids = [t for t in sub.index if _split(t) == "train"]
            if len(tids) < 25:
                continue
            vals = sub.loc[tids, kind].values
            q = np.quantile(vals, [0.5, 0.75, 0.9, 0.97])
            grade = {t: int(np.searchsorted(q, v)) for t, v in zip(tids, vals)}
            for _ in range(150):
                pick = list(rng.choice(tids, size=20, replace=False))
                rows = [table[t] for t in pick]
                Xs.append(features_for(p, rows, reliability0, popularity))
                ys.append([grade[t] for t in pick])
                groups.append(20)
        X = np.vstack(Xs)
        y = np.concatenate(ys)
        mdl = lgb.LGBMRanker(objective="lambdarank", n_estimators=220, learning_rate=0.05, num_leaves=15,
                             min_child_samples=20, random_state=config.SEED, verbose=-1, deterministic=True,
                             force_row_wise=True, n_jobs=4)
        mdl.fit(X, y, group=groups, feature_name=FEATS)
        models[kind] = mdl
        # ---- NDCG@10 vs true relevance on held-out hotels
        scores = []
        for p in PERSONAS:
            test_t = [t for t in table if _split(t) == "test" and t in canon_of]
            g_true = {t: truth["relevance"][p["id"]][canon_of[t]] for t in test_t}
            for _ in range(60):
                pick = list(rng.choice(test_t, size=20, replace=False))
                rows = [table[t] for t in pick]
                s = mdl.predict(features_for(p, rows, reliability0, popularity))
                scores.append(ndcg_at(s, [g_true[t] for t in pick]))
        evals[kind] = float(np.mean(scores))
    res = {"models": models, "eta": eta, "propensity_curve": {int(k): float(v) for k, v in zip(pos, rel_ctr)},
           "ndcg": evals, "popularity": popularity, "n_sessions": int(logs.session_id.nunique()),
           "n_randomized": int(rnd.session_id.nunique())}
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(res, f)
    print(f"  ranking: eta={eta:.3f} (true 0.9) · NDCG@10 vs true relevance: naive {evals['naive']:.3f} -> IPW {evals['ipw']:.3f}")
    return res


def load() -> dict:
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


WHY = {
    "star_gap": lambda p, r: f"Matches your {p['stars']}★ profile" if abs(r["stars"] - p["stars"]) == 0 else None,
    "stars": lambda p, r: f"{r['stars']}★ property",
    "in_pref_area": lambda p, r: f"In {r['neighbourhood']}" if r["neighbourhood"] in p["areas"] else None,
    "dist_pref_km": lambda p, r: f"Close to {p['areas'][0]}",
    "refundable_need": lambda p, r: "Shown rate has free cancellation" if r["refundable"] else None,
    "refundable": lambda p, r: "Shown rate has free cancellation" if r["refundable"] else None,
    "refundable_available": lambda p, r: "Refundable rates available" if r["refundable_available"] else None,
    "refundable_avail_need": lambda p, r: "Refundable rates available" if r["refundable_available"] else None,
    "breakfast_available": lambda p, r: "Breakfast rates available" if r["breakfast_available"] else None,
    "breakfast_avail_aff": lambda p, r: "Breakfast rates available" if r["breakfast_available"] else None,
    "review": lambda p, r: f"Guests rate it {r['review']:.1f}",
    "suite_aff": lambda p, r: "Suites available" if r["suite"] else None,
    "suite": lambda p, r: "Suites available" if r["suite"] else None,
    "breakfast_aff": lambda p, r: "Shown rate includes breakfast" if r["breakfast"] else None,
    "budget_ratio": lambda p, r: f"Within budget · ₹{r['price']:,}/night" if r["price"] <= p["budget"] else None,
    "price_rel_median": lambda p, r: f"Good value · ₹{r['price']:,}/night",
    "price_log": lambda p, r: f"Good value · ₹{r['price']:,}/night",
    "price_rank": lambda p, r: f"Good value · ₹{r['price']:,}/night",
    "reliability": lambda p, r: None,
    "popularity": lambda p, r: "Popular with agents",
}


def rank(persona_id: str, mode: str, table: dict, model_res: dict, reliability: dict, top: int = 6,
         candidates: int = 40) -> dict:
    p = PERSONA[persona_id]
    mdl = model_res["models"]["ipw"]
    rows = list(table.values())
    X = features_for(p, rows, reliability, model_res["popularity"])
    rel = mdl.predict(X)
    contrib = mdl.predict(X, pred_contrib=True)
    # restrict to a realistic result page: top candidates by relevance
    cand = np.argsort(-rel)[:candidates]
    rows = [rows[i] for i in cand]
    rel, X, contrib = rel[cand], X[cand], contrib[cand]
    z = (rel - rel.mean()) / (rel.std() + 1e-9)
    margins = np.array([r["margin"] for r in rows])
    nm = (margins - margins.min()) / (np.ptp(margins) + 1e-9)
    plat = np.array([float(r["platinum"]) for r in rows])
    relia = np.array([reliability.get(r["head_supplier"], 0.97) for r in rows])
    w = dict(config.RANK_WEIGHTS)
    use_margin = mode in ("business", "risk")
    use_risk = mode == "risk"
    scale, tau = 1.0, 1.0
    base_order = np.argsort(-z, kind="stable")
    for _ in range(12):
        final = z + scale * ((w["margin"] * nm + w["platinum"] * plat) * use_margin - w["risk"] * (1 - relia) * use_risk)
        order = np.argsort(-final, kind="stable")
        tau = kendalltau(np.argsort(base_order), np.argsort(order)).statistic if mode != "relevance" and len(rows) > 1 else 1.0
        if tau >= config.KENDALL_GUARDRAIL or mode == "relevance":
            break
        scale *= 0.8
    else:
        final, order, scale, tau = z, base_order, 0.0, 1.0
    out = []
    for i in order[:top]:
        r = rows[i]
        chips = []
        for f in np.argsort(-contrib[i][:-1]):
            if contrib[i][f] <= 0 or len(chips) >= 2:
                break
            txt = WHY.get(FEATS[f], lambda *_: None)(p, r)
            if txt and txt not in chips:
                chips.append(txt)
        if use_margin and r["platinum"]:
            chips.append("Platinum partner")
        if use_risk:
            chips.append(f"{config.SUPPLIERS[r['head_supplier']]['name']} confirms {relia[i] * 100:.1f}%")
        out.append({"tessera_id": r["tid"], "name": r["name"], "stars": r["stars"], "neighbourhood": r["neighbourhood"],
                    "price": r["price"], "supplier": r["head_supplier"], "review": round(r["review"], 1),
                    "hero": r["hero"], "platinum": r["platinum"], "chips": chips[:3],
                    "relevance": round(float(z[i]), 3), "final": round(float(final[i]), 3)})
    return {"persona": p, "mode": mode, "results": out, "kendall_tau": round(float(tau), 3),
            "business_scale": round(scale, 3), "weights": w}
