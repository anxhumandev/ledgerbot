"""Canonical record detail: everything the inventory detail page shows for one property or experience."""
from __future__ import annotations

from app import audit, config, store
from app.demo import DEMO
from app.errors import ApiError
from app.pipeline.features import haversine_m
from app.services import catalog, offers_svc, views


def _cases_for(records: set[str]) -> list[dict]:
    if not records:
        return []
    rows = store.query("SELECT id, record_a, record_b, status, p, priority, decided_at FROM review_cases")
    return [r for r in rows if r["record_a"] in records or r["record_b"] in records]


def hotel(tid: str) -> dict:
    h = DEMO.hotels.get(tid)
    if h is None:
        raise ApiError(404, "not_found", f"Property {tid} does not exist. It may have been merged into another record.",
                       {"merged_into": _merged_into(tid)})
    open_records = catalog.open_case_records()
    touched = audit.last_touch("hotel")
    row = catalog.hotel_row(h, open_records, touched)
    q = catalog.quality(h, open_records)
    cd = views.cluster_detail(tid)
    prim = catalog.primaries(h)
    # evidence: every scored link inside the record, strongest first
    links = []
    for i, a in enumerate(prim):
        for b in prim[i + 1:]:
            p = catalog.pair_p(a, b)
            if p is None or catalog.supplier_of(a) == catalog.supplier_of(b):
                continue
            links.append({"record_a": a, "record_b": b, "supplier_a": catalog.supplier_of(a), "supplier_b": catalog.supplier_of(b),
                          "name_a": DEMO.rec_by_id[a]["name"], "name_b": DEMO.rec_by_id[b]["name"], "p": round(p, 4),
                          "band": DEMO.band_of(_raw(a, b)) if _raw(a, b) is not None else None})
    links.sort(key=lambda x: -x["p"])
    return {**row, "golden": {**cd["golden"], "country": config.COUNTRY_OF_CITY.get(h["city"], ""), "city_name": catalog.city_name(h["city"])},
            "quality_checks": q["checks"], "quality_weights": dict(catalog.QUALITY_WEIGHTS),
            "records": [{**r, "cells": d["cells"], "dup_of": d["dup_of"]} for r, d in zip(cd["members"], cd["diffs"])],
            "weakest_explain": cd["explain"], "links": links, "kept_separate": kept_separate(tid),
            "rooms": cd["rooms"], "photos": cd["photos"], "trust": cd["trust"],
            "headline_offer": offers_svc.headline(tid), "rates_loaded": bool(h.get("rooms")),
            "review_cases": _cases_for(set(h["members"])), "history": audit.for_entity("hotel", tid),
            "split_from": h.get("split_from"), "ingested": bool(h.get("ingested"))}


def _raw(a: str, b: str):
    k = DEMO.pair_index.get((a, b), DEMO.pair_index.get((b, a)))
    return float(DEMO.state["raw"][k]) if k is not None else None


def _merged_into(tid: str) -> str | None:
    base = DEMO.base_hotels.get(tid)
    if not base:
        return None
    for m in base["members"]:
        if m in DEMO.record_cluster:
            return DEMO.record_cluster[m]
    return None


def kept_separate(tid: str, limit: int = 6) -> list[dict]:
    """Nearby candidate pairs the engine scored but did not merge: the evidence that this record is not a duplicate."""
    h = DEMO.hotels[tid]
    mine = set(h["members"])
    best: dict[str, dict] = {}
    st = DEMO.state
    for (a, b), k in DEMO.pair_index.items():
        if (a in mine) == (b in mine):
            continue
        inside, outside = (a, b) if a in mine else (b, a)
        other = DEMO.record_cluster.get(outside)
        if other is None or other == tid:
            continue
        p = float(st["p"][k])
        if other not in best or p > best[other]["p"]:
            ri, ro = DEMO.rec_by_id.get(inside, {}), DEMO.rec_by_id.get(outside, {})
            dist = haversine_m(ri["lat"], ri["lng"], ro["lat"], ro["lng"]) if None not in (ri.get("lat"), ro.get("lat")) else None
            best[other] = {"tessera_id": other, "name": DEMO.hotels[other]["name"], "record_a": inside, "record_b": outside,
                           "p": round(p, 4), "band": DEMO.band_of(float(st["raw"][k])), "distance_m": round(dist) if dist is not None else None}
    # probabilities this low are all "clearly different"; among them the closest properties are the informative ones
    return sorted(best.values(), key=lambda x: (-round(x["p"], 2), x["distance_m"] if x["distance_m"] is not None else 1e9))[:limit]


def activity(pid: str) -> dict:
    p = catalog.product(pid)
    lst = catalog._listing_index()
    touched = audit.last_touch("activity")
    row = catalog.activity_row(p, touched)
    siblings = [{"product_id": o["product_id"], "label": o["label"], "tier": o["tier"], "n_listings": o["n_listings"]}
                for o in DEMO.state["products"] if o["attraction"] == p["attraction"] and o["product_id"] != pid]
    options = []
    for o in p["options"]:
        k = o["key"]
        units = []
        for u in o["units"]:
            raw = lst.get(u["listing_id"], {})
            units.append({**u, "meeting_point": raw.get("meeting_point"), "inclusions": raw.get("inclusions"),
                          "language": raw.get("language"), "city": raw.get("city"),
                          "supplier_name": config.SUPPLIERS[u["supplier"]]["name"]})
        durations = sorted({u["duration_min"] for u in units if u.get("duration_min")})
        options.append({"label": o["label"], "time_slot": k[0], "transfer": bool(k[1]), "meal": bool(k[2]), "private": bool(k[3]),
                        "language": k[4], "addons": list(k[5]) if len(k) > 5 else [], "suppliers": o["suppliers"],
                        "best_adult": o["best_adult"], "duration_range": [durations[0], durations[-1]] if durations else None,
                        "units": units})
    distinct_axes = []
    if len(options) > 1:
        for axis in ("time_slot", "transfer", "meal", "private", "language", "addons"):
            if len({str(o[axis]) for o in options}) > 1:
                distinct_axes.append(axis)
    return {**row, "attraction": p["attraction"], "access_tier": p["tier"], "options": options,
            "merge_rule": "Listings join this product when they describe the same attraction and the same access tier. "
                          "Within it, listings join one option only when time slot, transfer, meal, private/shared, language "
                          "and add-ons all agree.",
            "kept_separate_products": siblings, "option_axes": distinct_axes,
            "evaluation": DEMO.state["activity_eval"], "history": audit.for_entity("activity", pid)}


def explain_pair(a: str, b: str) -> dict:
    if a not in DEMO.rec_by_id or b not in DEMO.rec_by_id:
        raise ApiError(404, "not_found", "Unknown record.")
    ex = views.explain_records(a, b)
    from app.services import analyst
    return {"explain": ex, "diffs": analyst._diffs(ex["a"], ex["b"]),
            "same_property": DEMO.record_cluster.get(a) == DEMO.record_cluster.get(b)}
