"""Operations Overview and Analytics read models. Every figure carries a `source` describing how it was produced:
measured (computed from the catalog / held-out evaluation), simulated (booking simulator, replay), assumption-based,
or live (operational records in the workspace database)."""
from __future__ import annotations

import time
from collections import Counter, defaultdict
from datetime import datetime

from app import audit, config, store
from app.demo import DEMO
from app.services import catalog, offers_svc, review, settings_svc, suppliers_ops

_CACHE: dict = {}


def _key() -> tuple:
    m = store.one("SELECT COUNT(*) AS n, COALESCE(MAX(id), 0) AS mx FROM catalog_mutations WHERE active = 1")
    return (m["n"], m["mx"], settings_svc.get("price_cap_pct"), tuple(sorted(settings_svc.paused_suppliers())),
            tuple(sorted(DEMO.sabotage)), round(DEMO.alpha, 6))


def competitiveness() -> dict:
    k = ("comp",) + _key()
    if _CACHE.get("comp_key") == k:
        return _CACHE["comp"]
    groups = cheapest_wins = 0
    premiums = []
    for h in DEMO.hotels.values():
        for g in h.get("rooms") or []:
            for s in g["slots"]:
                if len(s["offers"]) < 2:
                    continue
                sel = offers_svc.select(s["offers"])
                if not sel["winner"]:
                    continue
                groups += 1
                prem = sel["winner"]["price"] / sel["cheapest"]["price"] - 1
                premiums.append(prem)
                cheapest_wins += prem <= 1e-9
    out = {"groups": groups, "cheapest_share": cheapest_wins / groups if groups else None,
           "avg_premium_pct": 100 * sum(premiums) / len(premiums) if premiums else None,
           "max_premium_pct": 100 * max(premiums) if premiums else None}
    _CACHE.update(comp_key=k, comp=out)
    return out


def _quality_avg() -> float | None:
    open_records = catalog.open_case_records()
    vals = [catalog.quality(h, open_records)["score"] for h in DEMO.hotels.values()]
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def issues(limit: int = 40) -> list[dict]:
    """Actionable items across the workspace, each linking to the screen where it is resolved."""
    out = []
    names = {u["id"]: u["name"] for u in store.query("SELECT id, name FROM users")}
    for c in store.query("SELECT * FROM review_cases WHERE status IN ('open','escalated') ORDER BY CASE priority WHEN 'high' THEN 0 "
                         "WHEN 'medium' THEN 1 ELSE 2 END, ABS(p - 0.5) LIMIT 15"):
        ra, rb = DEMO.rec_by_id.get(c["record_a"], {}), DEMO.rec_by_id.get(c["record_b"], {})
        out.append({"id": c["id"], "type": "Match review" if c["status"] == "open" else "Escalated match",
                    "entity": f"{ra.get('name', c['record_a'])} ↔ {rb.get('name', c['record_b'])}", "entity_id": c["id"],
                    "supplier": ra.get("supplier"), "severity": "high" if c["status"] == "escalated" or c["priority"] == "high" else "medium",
                    "status": "Escalated" if c["status"] == "escalated" else ("Assigned" if c["assignee"] else "Open"),
                    "detected_at": c["created_at"], "owner": names.get(c["assignee"]), "link": f"/matching/review?case={c['id']}",
                    "action": "Review"})
    for code, f in DEMO.sabotage.items():
        out.append({"id": f"SIM-{code}", "type": "Supplier degradation (simulated)", "entity": config.SUPPLIERS[code]["name"],
                    "entity_id": code, "supplier": code, "severity": "high", "status": "Open",
                    "detected_at": f.get("started_at", time.time()), "owner": None, "link": f"/suppliers/{code}", "action": "Investigate"})
    for j in store.query("SELECT id, supplier, finished_at, error FROM ingestion_jobs WHERE status = 'failed' ORDER BY finished_at DESC LIMIT 5"):
        out.append({"id": j["id"], "type": "Ingestion failed", "entity": j["error"] or "Job failed", "entity_id": j["id"],
                    "supplier": j["supplier"], "severity": "high", "status": "Open", "detected_at": j["finished_at"], "owner": None,
                    "link": f"/suppliers/ingestion?job={j['id']}", "action": "Retry"})
    for code in sorted(settings_svc.paused_suppliers()):
        out.append({"id": f"PAUSED-{code}", "type": "Supplier feed paused", "entity": config.SUPPLIERS[code]["name"], "entity_id": code,
                    "supplier": code, "severity": "low", "status": "Open", "detected_at": (settings_svc.supplier_config(code)["updated_at"] or 0),
                    "owner": None, "link": f"/suppliers/{code}", "action": "Review feed"})
    dq = []
    for rid, r in DEMO.rec_by_id.items():
        if r.get("lat") is None or DEMO.record_cluster.get(rid) is None:
            continue
        for i in suppliers_ops.record_issues(rid):
            if i["code"] == "coordinates_off":
                dq.append((rid, r, i))
    dq.sort(key=lambda t: -float(t[2]["message"].split()[1]))
    for rid, r, i in dq[:8]:
        tid = DEMO.record_cluster[rid]
        out.append({"id": f"DQ-{rid}", "type": "Location mismatch", "entity": f"{r['name']} · {i['message']}", "entity_id": tid,
                    "supplier": r["supplier"], "severity": "medium", "status": "Open", "detected_at": catalog.built_ts(), "owner": None,
                    "link": f"/inventory/hotel/{tid}?tab=records", "action": "Inspect"})
    sev = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda x: (sev[x["severity"]], -(x["detected_at"] or 0)))
    return out[:limit]


def overview() -> dict:
    s = DEMO.state["summary"]
    dirs = suppliers_ops.directory()
    act_units = sum(len(o["units"]) for p in DEMO.state["products"] for o in p["options"])
    hotel_listings = len(DEMO.rec_by_id)
    in_multi = sum(h["n_records"] for h in DEMO.hotels.values() if len(h["suppliers"]) >= 2)
    single = sum(h["n_records"] for h in DEMO.hotels.values() if len(h["suppliers"]) < 2)
    act_multi = sum(len(o["units"]) for p in DEMO.state["products"] for o in p["options"] if len({u["supplier"] for u in o["units"]}) >= 2)
    rv = review.stats()
    in_band = review.list_cases(status="open,escalated", page_size=1)["total"]
    active = [d for d in dirs if d["status"] == "active"]
    rel = [d["reliability"] for d in active if d["reliability"] is not None]
    comp = competitiveness()
    q = _quality_avg()
    kpis = [
        {"key": "suppliers", "label": "Active suppliers", "value": len(active), "of": len(dirs), "unit": "count", "source": "live",
         "hint": f"{len(dirs) - len(active)} paused or onboarding"},
        {"key": "listings", "label": "Supplier listings", "value": hotel_listings + act_units, "unit": "count", "source": "measured",
         "hint": f"{hotel_listings:,} hotel · {act_units:,} sightseeing"},
        {"key": "canonical", "label": "Canonical products", "value": len(DEMO.hotels) + len(DEMO.state["products"]), "unit": "count",
         "source": "measured", "hint": f"{len(DEMO.hotels):,} properties · {len(DEMO.state['products'])} experiences"},
        {"key": "dedup", "label": "Deduplication coverage", "value": (in_multi + act_multi) / (hotel_listings + act_units), "unit": "pct",
         "source": "measured", "hint": "Listings consolidated into a record shared by 2+ suppliers"},
        {"key": "reviews", "label": "Pending match reviews", "value": in_band, "unit": "count", "source": "live",
         "hint": f"{rv['escalated']} escalated · {rv['decided']} decided"},
        {"key": "reliability", "label": "Supplier reliability", "value": sum(rel) / len(rel) if rel else None, "unit": "pct",
         "source": "simulated", "hint": "Mean confirm-at-quoted-price score, active suppliers"},
        {"key": "competitiveness", "label": "Offer competitiveness", "value": comp["cheapest_share"], "unit": "pct", "source": "measured",
         "hint": f"Recommended offer is the cheapest · avg premium {comp['avg_premium_pct']:.2f}%" if comp["avg_premium_pct"] is not None else "No comparable offers"},
        {"key": "quality", "label": "Catalog quality score", "value": q, "unit": "score", "source": "measured",
         "hint": "Completeness and corroboration of golden records (0–100)"},
    ]
    by_city = defaultdict(lambda: {"listings": 0, "canonical": 0})
    for h in DEMO.hotels.values():
        c = catalog.city_name(h["city"])
        by_city[c]["listings"] += h["n_records"]
        by_city[c]["canonical"] += 1
    health = {"raw_records": hotel_listings + act_units, "matched": in_multi + act_multi, "unmatched": single + (act_units - act_multi),
              "review": in_band, "hotel": {"listings": hotel_listings, "canonical": len(DEMO.hotels)},
              "sightseeing": {"listings": act_units, "canonical": len(DEMO.state["products"])},
              "by_city": [{"city": k, **v} for k, v in sorted(by_city.items(), key=lambda t: -t[1]["listings"])]}
    activity = audit.search(page_size=12)["items"]
    return {"kpis": kpis, "inventory_health": health, "suppliers": dirs, "issues": issues(), "activity": activity,
            "built_at": catalog.built_ts(), "generated_at": time.time(), "world": DEMO.state.get("world"),
            "llm": {"enabled": config.LLM_ENABLED}}


def analytics() -> dict:
    s = DEMO.state
    ev = s["evals"]
    days = defaultdict(lambda: Counter())
    for e in store.query("SELECT ts, action FROM audit_events WHERE action LIKE 'review.%'"):
        d = datetime.fromtimestamp(e["ts"]).strftime("%Y-%m-%d")
        days[d][e["action"]] += 1
    by_user = Counter(r["decided_by"] for r in store.query("SELECT decided_by FROM review_cases WHERE decided_by IS NOT NULL"))
    names = {u["id"]: u["name"] for u in store.query("SELECT id, name FROM users")}
    comp = suppliers_ops._competitiveness()
    return {
        "matching": {"source": "measured", "basis": "Held-out test split of the synthetic world (ground truth hidden from the pipeline)",
                     "pairwise": ev["test_pairwise"], "bcubed": ev["test_bcubed"], "auto_only": ev["test_pairwise_auto_only"],
                     "auc": ev["auc_test"], "consistency": s["consistency"], "routes": s["routes"],
                     "blocking": {k: s["blocking"].get(k) for k in ("recall", "reduction_ratio", "n_candidates", "by_source") if k in s["blocking"]},
                     "duplicates": s["dup_stats"]},
        "by_category": {"hotel": {"pair_f1": ev["test_pairwise"].get("f1"), "room_f1": s["room_eval"].get("f1"),
                                  "offer_wrong_room_rate": s["offer_eval"]["tessera_rate"], "raw_wrong_room_rate": s["offer_eval"]["raw_rate"]},
                        "sightseeing": {"product_f1": s["activity_eval"]["product"]["f1"], "option_f1": s["activity_eval"]["option"]["f1"]}},
        "risk": {"source": "measured", "alpha": DEMO.alpha, "current": DEMO.current_risk, "curve": DEMO.dense_curve},
        "workload": {"source": "live", "cases": review.stats(),
                     "per_day": [{"day": d, **dict(c)} for d, c in sorted(days.items())],
                     "by_user": [{"user": names.get(u, u), "decisions": n} for u, n in by_user.most_common()]},
        "competitiveness": {"source": "measured", "summary": competitiveness(),
                            "by_supplier": [{"code": c, "name": config.SUPPLIERS[c]["name"], **v} for c, v in comp.items() if v["groups"]]},
        "ranking": {"source": "measured on simulated search logs", "ndcg": DEMO.ranking["ndcg"],
                    "sessions": DEMO.ranking.get("n_sessions"), "randomized": DEMO.ranking.get("n_randomized")},
        "consolidation": overview()["inventory_health"]["by_city"],
        "replay": {"source": "simulated", "last": getattr(DEMO, "last_replay", None)},
    }
