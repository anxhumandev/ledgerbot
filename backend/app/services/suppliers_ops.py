"""Supplier directory and operational profile.

Sources, in order of trust:
- Listings, coverage and data-quality findings are computed from the catalog (measured on the synthetic feeds).
- Confirmation, price-change and latency figures are Beta posteriors over the synthetic 30-day booking history plus any
  simulated live bookings (labelled "simulated" in the UI).
- Sync times come from completed ingestion jobs; before the first job, from the catalog build.
"""
from __future__ import annotations

import time
from collections import Counter, defaultdict
from functools import lru_cache

import pandas as pd

from app import audit, config, store
from app.demo import DEMO
from app.errors import ApiError
from app.pipeline.features import haversine_m
from app.services import catalog, offers_svc, settings_svc

ALL = list(config.SUPPLIERS)


def _records_of(code: str) -> list[str]:
    return [rid for rid, r in DEMO.rec_by_id.items() if r.get("supplier") == code]


def record_issues(rid: str) -> list[dict]:
    """Data-quality findings for one supplier record, compared with its golden record."""
    r, out = DEMO.rec_by_id[rid], []
    tid = DEMO.record_cluster.get(rid)
    h = DEMO.hotels.get(tid) if tid else None
    if not r.get("phone"):
        out.append({"code": "missing_phone", "severity": "low", "message": "Phone number missing"})
    if not r.get("address"):
        out.append({"code": "missing_address", "severity": "medium", "message": "Address missing"})
    if r.get("lat") is None or r.get("lng") is None:
        out.append({"code": "missing_coordinates", "severity": "high", "message": "Coordinates missing"})
    elif h and h.get("lat") is not None:
        d = haversine_m(r["lat"], r["lng"], h["lat"], h["lng"])
        if d > 1000:
            out.append({"code": "coordinates_off", "severity": "high", "message": f"Pin {d / 1000:.1f} km from the consensus location"})
    if h and r.get("stars") and h.get("stars") and r["stars"] != h["stars"]:
        out.append({"code": "star_mismatch", "severity": "low", "message": f"{r['stars']}★ vs consensus {h['stars']}★"})
    if rid in DEMO.state["alias"]:
        out.append({"code": "duplicate_listing", "severity": "medium", "message": "Duplicate of another listing from the same supplier"})
    return out


def _sync(code: str) -> dict:
    j = store.one("SELECT id, finished_at, status FROM ingestion_jobs WHERE supplier = ? AND status IN ('completed','failed') "
                  "ORDER BY finished_at DESC LIMIT 1", (code,))
    ok = store.one("SELECT finished_at FROM ingestion_jobs WHERE supplier = ? AND status = 'completed' ORDER BY finished_at DESC LIMIT 1", (code,))
    return {"last_job": j, "last_success": ok["finished_at"] if ok else (catalog.built_ts() if code in config.ACTIVE_SUPPLIERS else None),
            "last_success_source": "ingestion job" if ok else ("catalog build" if code in config.ACTIVE_SUPPLIERS else None)}


def feed_health(code: str, status: str, sync: dict, rel_score: float | None) -> str:
    if status == "paused":
        return "paused"
    if code in DEMO.sabotage:
        return "degraded"
    if sync["last_job"] and sync["last_job"]["status"] == "failed":
        return "error"
    if status == "onboarding":
        return "onboarding"
    if rel_score is not None and rel_score < 0.9:
        return "degraded"
    return "healthy"


def _competitiveness() -> dict:
    """Per supplier: comparable offer groups it competes in, wins (recommended) and is cheapest in. Dubai rates."""
    comp, wins, cheap = Counter(), Counter(), Counter()
    for h in DEMO.hotels.values():
        for g in h.get("rooms") or []:
            for s in g["slots"]:
                if len(s["offers"]) < 2:
                    continue
                sel = offers_svc.select(s["offers"])
                for sup in {o["supplier"] for o in s["offers"]}:
                    comp[sup] += 1
                if sel["winner"]:
                    wins[sel["winner"]["supplier"]] += 1
                cheap[sel["cheapest"]["supplier"]] += 1
    return {c: {"groups": comp[c], "recommended": wins[c], "cheapest": cheap[c]} for c in ALL}


def directory() -> list[dict]:
    snap = {s["code"]: s for s in DEMO.reliability.snapshot(ALL)}
    n_hotels = len(DEMO.hotels)
    by_sup = defaultdict(int)
    for h in DEMO.hotels.values():
        for s in h["suppliers"]:
            by_sup[s] += 1
    rows = []
    for code in ALL:
        recs = _records_of(code)
        issues = sum(1 for r in recs if any(i["severity"] in ("high", "medium") for i in record_issues(r)))
        st = settings_svc.supplier_status(code)
        sync = _sync(code)
        rel = snap.get(code)
        rejected = store.one("SELECT COALESCE(SUM(rejected), 0) AS n FROM ingestion_jobs WHERE supplier = ?", (code,))["n"]
        rows.append({"code": code, "name": config.SUPPLIERS[code]["name"], "persona": config.SUPPLIERS[code]["persona"],
                     "status": st, "feed_health": feed_health(code, st, sync, rel["score"] if rel and code in config.ACTIVE_SUPPLIERS else None),
                     "last_sync": sync["last_success"], "last_sync_source": sync["last_success_source"],
                     "listings": len(recs), "activity_listings": sum(1 for p in DEMO.state["products"] for o in p["options"] for u in o["units"] if u["supplier"] == code),
                     "coverage": by_sup[code] / n_hotels if n_hotels else 0.0, "properties": by_sup[code],
                     "validation_errors": issues + int(rejected or 0),
                     "confirm_rate": rel["confirm"] if rel else None, "price_change_rate": rel["price_jump"] if rel else None,
                     "p50_latency": rel["p50_latency"] if rel else None, "reliability": rel["score"] if rel else None,
                     "reliability_ci": rel["ci"] if rel else None, "observations": rel["n_obs"] if rel else 0,
                     "has_history": code in config.ACTIVE_SUPPLIERS,
                     "take_rate": config.SUPPLIERS[code]["take_rate"], "simulated_fault": DEMO.sabotage.get(code)})
    return rows


def detail(code: str) -> dict:
    if code not in config.SUPPLIERS:
        raise ApiError(404, "not_found", f"Supplier {code} does not exist.")
    row = next(r for r in directory() if r["code"] == code)
    recs = _records_of(code)
    cities = Counter(catalog.city_name(DEMO.norm_by_id[r]["city"]) for r in recs if r in DEMO.norm_by_id)
    issue_counts = Counter(i["code"] for r in recs for i in record_issues(r))
    comp = _competitiveness().get(code, {})
    jobs = store.query("SELECT id, filename, status, created_at, finished_at, total, valid, invalid, merged, created, updated, review, rejected "
                       "FROM ingestion_jobs WHERE supplier = ? ORDER BY created_at DESC LIMIT 20", (code,))
    return {**row, "config": settings_svc.supplier_config(code), "cities": [{"city": c, "listings": n} for c, n in cities.most_common()],
            "issue_counts": dict(issue_counts), "competitiveness": comp, "jobs": jobs,
            "history": audit.for_entity("supplier", code)}


def listings(code: str, q: str = "", issues_only: bool = False, page: int = 1, page_size: int = 25) -> dict:
    if code not in config.SUPPLIERS:
        raise ApiError(404, "not_found", f"Supplier {code} does not exist.")
    items = []
    ql = q.lower().strip()
    for rid in _records_of(code):
        r = DEMO.rec_by_id[rid]
        if ql and ql not in r["name"].lower() and ql not in rid.lower():
            continue
        iss = record_issues(rid)
        if issues_only and not iss:
            continue
        tid = DEMO.record_cluster.get(rid)
        items.append({"record_id": rid, "name": r["name"], "city": catalog.city_name(DEMO.norm_by_id.get(rid, {}).get("city", "")),
                      "tessera_id": tid, "canonical_name": DEMO.hotels.get(tid, {}).get("name"),
                      "n_suppliers": len(DEMO.hotels.get(tid, {}).get("suppliers", [])), "issues": iss})
    items.sort(key=lambda x: (-len(x["issues"]), x["name"]))
    start = (max(page, 1) - 1) * page_size
    return {"items": items[start:start + page_size], "total": len(items), "page": page, "page_size": page_size}


@lru_cache(maxsize=1)
def _history_frame() -> pd.DataFrame:
    return pd.read_parquet(config.WORLD_DIR / "booking_history.parquet")


def reliability_history(code: str) -> dict:
    """Daily outcomes from the synthetic 30-day booking history, plus the live (simulated) posterior trace."""
    if code not in config.SUPPLIERS:
        raise ApiError(404, "not_found", f"Supplier {code} does not exist.")
    h = _history_frame()
    h = h[h.supplier == code]
    days = []
    for d, g in h.groupby("day"):
        conf = g[g.confirmed]
        days.append({"day": int(d), "bookings": int(len(g)), "confirm_rate": float(g.confirmed.mean()),
                     "price_change_rate": float(conf.price_jump.mean()) if len(conf) else 0.0,
                     "p50_latency": float(g.latency_s.median())})
    post = DEMO.reliability.get(code)
    return {"daily": days, "source": "Synthetic 30-day booking history", "live": post.snapshot()["spark"],
            "live_source": "Simulated booking stream (posterior score)"}


# ---------------------------------------------------------------- fault simulation (what-if)
def simulate(code: str, mode: str, severity: float, user) -> dict:
    from app.services.simulator import SIM
    if code not in config.ACTIVE_SUPPLIERS:
        raise ApiError(422, "invalid_value", "Simulations run on active suppliers only.")
    if mode not in ("price_jump", "timeouts", "failures") or not 0.05 <= severity <= 0.9:
        raise ApiError(422, "invalid_value", "Choose a fault type and a severity between 5% and 90%.")
    SIM.sabotage(code, mode, severity)
    DEMO.sabotage[code]["started_at"] = time.time()
    audit.record(user, "simulation.fault_started", "supplier", code, after={"mode": mode, "severity": severity},
                 reason="What-if simulation: hidden supplier behaviour changed; reliability moves only through simulated bookings.")
    return simulation_state()


def heal(user) -> dict:
    from app.services.simulator import SIM
    before = dict(DEMO.sabotage)
    SIM.heal()
    if before:
        audit.record(user, "simulation.faults_cleared", "workspace", "simulation", before={k: v["mode"] for k, v in before.items()})
    return simulation_state()


def simulation_state() -> dict:
    from app.services.simulator import SIM
    return {"running": SIM.running(), "faults": DEMO.sabotage, "switch_report": SIM.switch_report() if DEMO.sabotage else None,
            "suppliers": DEMO.reliability.snapshot(ALL)}
