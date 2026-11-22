"""Search ranking workspace.

Hotels use the trained ranker (LambdaRank with inverse-propensity weighting, pipeline.ranking) and its three modes:
relevance only, + margin & Platinum (commercial), + reliability risk (balanced), each with the Kendall-τ guardrail.
"Price first" is a plain sort of the same candidate page by the recommended offer price.
Sightseeing has no learned ranker in this build: it uses a transparent rule-based score, labelled as such.
"""
from __future__ import annotations

from rapidfuzz import fuzz
from scipy.stats import kendalltau

from app import config
from app.demo import DEMO
from app.errors import ApiError
from app.pipeline import ranking
from app.services import catalog, offers_svc

HOTEL_STRATEGIES = {
    "relevance": {"label": "Relevance first", "mode": "relevance", "desc": "Learned relevance for the agent profile only."},
    "commercial": {"label": "Commercial value", "mode": "business", "desc": "Relevance plus margin and Platinum partner weight."},
    "balanced": {"label": "Balanced", "mode": "risk", "desc": "Relevance, margin, Platinum and supplier reliability risk."},
    "price": {"label": "Price first", "mode": "relevance", "desc": "Same candidate page, sorted by recommended offer price."},
}
ACTIVITY_STRATEGIES = {
    "relevance": {"label": "Relevance first", "desc": "Text match to the query, then number of suppliers."},
    "price": {"label": "Price first", "desc": "Lowest recommended adult price first."},
    "reliability": {"label": "Reliability-aware", "desc": "Text match weighted by the recommended supplier's reliability."},
}


def personas() -> list[dict]:
    return list(ranking.PERSONA.values())


def _table(area: str = "", q: str = "", min_stars: int = 0) -> dict:
    t = DEMO.hotel_table
    ql = q.lower().strip()
    return {k: r for k, r in t.items()
            if (not area or r["neighbourhood"] == area) and (not ql or ql in r["name"].lower()) and (r["stars"] or 0) >= min_stars}


def hotels(persona: str, strategy: str, area: str = "", q: str = "", min_stars: int = 0, offer_policy: str = "expected_value",
           top: int = 10) -> dict:
    if persona not in ranking.PERSONA:
        raise ApiError(404, "not_found", "Unknown agent profile.")
    if strategy not in HOTEL_STRATEGIES:
        raise ApiError(422, "invalid_value", f"Strategy must be one of {', '.join(HOTEL_STRATEGIES)}.")
    table = _table(area, q, min_stars)
    if not table:
        return {"results": [], "strategy": strategy, "kendall_tau": None, "candidates": 0, "persona": ranking.PERSONA[persona]}
    rel = {c: DEMO.reliability.get(c).score for c in config.SUPPLIERS}
    n = len(table)
    res = ranking.rank(persona, HOTEL_STRATEGIES[strategy]["mode"], table, DEMO.ranking, rel, top=n, candidates=min(40, n))
    results = res["results"]
    for r in results:
        r["offer"] = _offer(r["tessera_id"], offer_policy)
    if strategy == "price":
        results.sort(key=lambda r: (r["offer"] or {}).get("total", 1e12))
    results = results[:top]
    for i, r in enumerate(results, start=1):
        r["position"] = i
        r["location"] = r["neighbourhood"]
    return {"results": results, "strategy": strategy, "strategy_label": HOTEL_STRATEGIES[strategy]["label"],
            "kendall_tau": res["kendall_tau"], "business_scale": res["business_scale"], "weights": res["weights"],
            "candidates": min(40, n), "persona": res["persona"], "offer_policy": offer_policy}


def _offer(tid: str, policy: str) -> dict | None:
    if policy == "cheapest":
        h = DEMO.hotels.get(tid)
        offers = [o for g in (h.get("rooms") or []) for s in g["slots"] for o in s["offers"]] if h else []
        if not offers:
            return None
        o = min(offers, key=lambda x: (x["price"], x["supplier"]))
        return {"room": next(g["name"] for g in h["rooms"] for s in g["slots"] if o in s["offers"]), "rate_plan": offers_svc._terms(o),
                "supplier": o["supplier"], "supplier_name": config.SUPPLIERS[o["supplier"]]["name"], "total": int(o["price"] * 3),
                "nights": 3, "refundable": bool(o["refundable"]), "cancel_hours": o.get("cancel_hours") if o["refundable"] else None,
                "payment": o.get("payment"), "board": o.get("board"), "reliability": round(DEMO.p_success(o["supplier"]), 4)}
    return offers_svc.headline(tid)


def compare(persona: str, a: str, b: str, area: str = "", q: str = "", offer_a: str = "expected_value", offer_b: str = "expected_value") -> dict:
    A = hotels(persona, a, area, q, offer_policy=offer_a, top=10)
    B = hotels(persona, b, area, q, offer_policy=offer_b, top=10)
    pos_a = {r["tessera_id"]: r["position"] for r in A["results"]}
    rows = []
    for r in B["results"]:
        pa = pos_a.get(r["tessera_id"])
        ra = next((x for x in A["results"] if x["tessera_id"] == r["tessera_id"]), None)
        oa, ob = (ra or {}).get("offer") or {}, r.get("offer") or {}
        rows.append({"tessera_id": r["tessera_id"], "name": r["name"], "position_b": r["position"], "position_a": pa,
                     "delta": (pa - r["position"]) if pa else None,
                     "offer_changed": bool(ra) and (oa.get("supplier"), oa.get("total"), oa.get("rate_plan")) != (ob.get("supplier"), ob.get("total"), ob.get("rate_plan")),
                     "offer_a": oa or None, "offer_b": ob or None, "chips": r["chips"]})
    common = [t for t in pos_a if t in {r["tessera_id"] for r in B["results"]}]
    tau = None
    if len(common) > 2:
        tau = float(kendalltau([pos_a[t] for t in common], [next(r["position"] for r in B["results"] if r["tessera_id"] == t) for t in common]).statistic)
    dropped = [{"tessera_id": r["tessera_id"], "name": r["name"], "position_a": r["position"]} for r in A["results"]
               if r["tessera_id"] not in {x["tessera_id"] for x in B["results"]}]
    return {"a": A, "b": B, "rows": rows, "dropped": dropped, "kendall_tau": tau,
            "offline_quality": {"ndcg": DEMO.ranking["ndcg"], "sessions": DEMO.ranking.get("n_sessions"),
                                "source": "NDCG@10 against known true relevance on simulated search logs"}}


def activities(q: str = "", city: str = "", strategy: str = "relevance", top: int = 10) -> dict:
    if strategy not in ACTIVITY_STRATEGIES:
        raise ApiError(422, "invalid_value", f"Strategy must be one of {', '.join(ACTIVITY_STRATEGIES)}.")
    rows = []
    for p in DEMO.state["products"]:
        c = catalog.activity_city(p)
        if city and c.lower().replace(" ", "_") != city:
            continue
        titles = [p["label"]] + [u["title"] for o in p["options"] for u in o["units"]]
        text = max(fuzz.partial_ratio(q.lower(), t.lower()) for t in titles) / 100 if q.strip() else 1.0
        if q.strip() and text < 0.6:
            continue
        off = offers_svc.activity_offers(p["product_id"])
        best = min((o["recommended"] for o in off["options"] if o["recommended"]), key=lambda r: r["adult"], default=None)
        sups = {u["supplier"] for o in p["options"] for u in o["units"]}
        score = {"relevance": text + 0.02 * len(sups),
                 "price": -(best["adult"] if best else 1e9),
                 "reliability": text * (best["reliability"] if best else 0.0)}[strategy]
        durations = sorted({u.get("duration_min") for o in p["options"] for u in o["units"] if u.get("duration_min")})
        incl = sorted({k for o in off["options"] for k, v in (("Transfer", o["transfer"]), ("Meal", o["meal"]), ("Private", o["private"])) if v})
        rows.append({"product_id": p["product_id"], "name": p["label"], "city": c, "options": len(p["options"]),
                     "suppliers": sorted(sups), "duration_range": [durations[0], durations[-1]] if durations else None,
                     "inclusions": incl, "offer": best, "score": round(score, 4), "text_match": round(text, 3)})
    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows[:top], start=1):
        r["position"] = i
        r["why"] = _activity_why(r, strategy)
    return {"results": rows[:top], "strategy": strategy, "strategy_label": ACTIVITY_STRATEGIES[strategy]["label"],
            "model": "Rule-based scoring (no learned sightseeing ranker in this build)"}


def _activity_why(r: dict, strategy: str) -> list[str]:
    out = []
    if r["text_match"] >= 0.9 and strategy != "price":
        out.append("Strong match to the search")
    if r["offer"]:
        out.append(f"From ₹{r['offer']['adult']:,} per adult via {r['offer']['supplier_name']}")
        if strategy == "reliability":
            out.append(f"Supplier confirms {r['offer']['reliability'] * 100:.1f}%")
    if len(r["suppliers"]) > 1:
        out.append(f"{len(r['suppliers'])} suppliers compete")
    return out[:3]


def areas() -> list[str]:
    return sorted({r["neighbourhood"] for r in DEMO.hotel_table.values()})
