"""Read models for scenes 00, 01, 03: summary, cold open, listings challenge, inspector, near-miss."""
from __future__ import annotations

from collections import Counter

import numpy as np

from app import config
from app.demo import DEMO
from app.pipeline import offers as off
from app.pipeline.features import distinguishing_detail, pair_features
from app.pipeline.matcher import explain

SUP = config.SUPPLIERS


def sup_name(c):
    return SUP[c]["name"]


def offer_view(o: dict, nights: int = 1) -> dict:
    return {"offer_id": o["offer_id"], "supplier": o["supplier"], "price": o["price"] * nights, "board": o["board"],
            "refundable": o["refundable"], "cancel_hours": o["cancel_hours"], "payment": o["payment"],
            "room_name": o["room_name"], "raw_room_name": o.get("raw_room_name"), "board_raw": o["board_raw"],
            "cancellation_raw": o["cancellation_raw"], "rate_code": o["rate_code"]}


def slot_view(slot: dict, strategy: str = "expected_value", nights: int = 1) -> dict:
    sel = off.select(slot["offers"], DEMO.p_success, strategy)
    w = sel["winner"]
    return {
        "label": slot["label"], "board": slot["board"], "refundable": slot["refundable"],
        "winner": {**offer_view(w, nights), "ev": round(w["ev"], 1), "p_success": round(w["p_success"], 4)},
        "why": sel["why"], "n_offers": len(slot["offers"]),
        "alternatives": [{**offer_view(o, nights), "ev": round(o["ev"], 1), "p_success": round(o["p_success"], 4)}
                         for o in sel["ranked"][1:]],
        "cheapest_offer_id": sel["cheapest"]["offer_id"],
    }


def hero_of(h: dict) -> str | None:
    return (h.get("photos") or {}).get("hero")


# ---------------------------------------------------------------- summary + cold open
def summary() -> dict:
    s = DEMO.state["summary"]
    return {**s, "consistency": DEMO.state["consistency"], "world": DEMO.state["world"],
            "built_at": DEMO.state["built_at"]}


def cold_open() -> dict:
    tid = DEMO.state["showcase"].get("Atlantis The Palm")
    h = DEMO.hotels[tid]
    best = max(h["rooms"], key=lambda g: (sum(len(s["offers"]) for s in g["slots"]), len(g["suppliers"])))
    rows = []
    by_sup = {}
    for s in best["slots"]:
        for o in s["offers"]:
            by_sup.setdefault(o["supplier"], []).append(o)
    recs = DEMO.rec_by_id
    # round-robin across suppliers so all are represented
    order = []
    while len(order) < 9 and any(by_sup.values()):
        for c in sorted(by_sup):
            if by_sup[c] and len(order) < 9:
                order.append(by_sup[c].pop(0))
    for o in order:
        rows.append({"offer_id": o["offer_id"], "supplier": o["supplier"], "supplier_name": sup_name(o["supplier"]),
                     "hotel_name": recs[o["record_id"]]["name"], "room_name": o["room_name"],
                     "board_raw": o["board_raw"], "cancellation_raw": o["cancellation_raw"], "price": o["price"],
                     "rate_code": o["rate_code"]})
    head = max(best["slots"], key=lambda s: (s["board"] == "BB" and s["refundable"], len(s["offers"])))
    sv = slot_view(head)
    total = sum(len(s["offers"]) for s in best["slots"])
    return {"hotel": {"tessera_id": tid, "name": h["name"], "stars": h["stars"], "neighbourhood": h["neighbourhood"],
                      "hero": hero_of(h)},
            "room": {"name": best["name"], "tier": best["tier"], "suppliers": best["suppliers"]},
            "rows": rows, "best": sv, "alternatives": total - 1, "n_slots": len(best["slots"]),
            "stats": summary()}


# ---------------------------------------------------------------- scene 01 listings
AREA_NB = {"marina": ["Dubai Marina"], "downtown": ["Downtown"], "jbr": ["JBR"], "palm": ["Palm Jumeirah"]}


def listings(area: str = "marina", strategy: str = "cheapest", nights: int = 3, limit: int = 12) -> dict:
    nbs = AREA_NB.get(area, ["Dubai Marina"])
    hs = [h for h in DEMO.hotels.values() if h["city"] == "dubai" and h["neighbourhood"] in nbs and h.get("rooms")]
    hs.sort(key=lambda h: (-len(h["suppliers"]), h["name"]))
    hs = hs[:limit]
    # target: cheapest Deluxe King, breakfast, free cancellation across the search
    target = None
    for h in hs:
        for gi, g in enumerate(h["rooms"]):
            if g["ident"].get("class") == "Deluxe" and g["ident"].get("bed") in ("King", "Double", "Queen"):
                for s in g["slots"]:
                    if s["board"] == "BB" and s["refundable"]:
                        o = min(s["offers"], key=lambda x: x["price"])
                        if target is None or o["price"] < target["price"]:
                            target = {"price": o["price"], "offer_id": o["offer_id"], "tessera_id": h["tessera_id"],
                                      "group": gi, "hotel": h["name"], "room": g["name"]}
    cards = []
    raw_rows = []
    distinct_slots = set()
    for h in hs:
        groups = []
        for gi, g in enumerate(h["rooms"]):
            if not g["slots"]:
                continue
            slots = [{**slot_view(s, strategy, nights), "slot_ref": f"{h['tessera_id']}|{gi}|{s['board']}|{int(s['refundable'])}"}
                     for s in g["slots"]]
            groups.append({"group": gi, "name": g["name"], "tier": g["tier"], "suppliers": g["suppliers"], "slots": slots,
                           "from_price": min(sl["winner"]["price"] for sl in slots)})
        groups.sort(key=lambda g: (-(target is not None and target["tessera_id"] == h["tessera_id"] and g["group"] == target["group"]),
                                   -len(g["suppliers"]), g["from_price"]))
        cards.append({"tessera_id": h["tessera_id"], "name": h["name"], "stars": h["stars"], "hero": hero_of(h),
                      "neighbourhood": h["neighbourhood"], "suppliers": h["suppliers"], "rooms": groups[:3],
                      "n_rooms": len(groups), "from_price": min(g["from_price"] for g in groups) if groups else None})
        # raw rows: every supplier offer for this hotel's top rooms, as delivered
        for gi, g in enumerate(h["rooms"]):
            for s in g["slots"]:
                for o in s["offers"]:
                    raw_rows.append({"offer_id": o["offer_id"], "supplier": o["supplier"],
                                     "hotel_name": DEMO.rec_by_id[o["record_id"]]["name"], "room_name": o["room_name"],
                                     "board_raw": o["board_raw"], "cancellation_raw": o["cancellation_raw"],
                                     "price": o["price"] * nights, "_slot": (h["tessera_id"], gi, s["board"], s["refundable"]),
                                     "_target_slot": target is not None and h["tessera_id"] == target["tessera_id"] and gi == target["group"]
                                     and s["board"] == "BB" and s["refundable"]})
    # keep the raw panel at ~60 rows: whole multi-supplier slots (that is where duplicates live), target slot first
    by_slot = {}
    for r in raw_rows:
        by_slot.setdefault(r["_slot"], []).append(r)
    slots_sorted = sorted(by_slot.values(), key=lambda rs: (not rs[0]["_target_slot"], -len({x["supplier"] for x in rs}), rs[0]["offer_id"]))
    must, rest = [], []
    for rs in slots_sorted:
        if len(must) + len(rs) > 61:
            continue
        must += rs
    rest = []
    raw = sorted(must + rest, key=lambda r: (r["price"], r["offer_id"]))
    for r in raw:
        distinct_slots.add(r["_slot"])
    board_raw = {r["board_raw"] for r in raw}
    board_norm = {r["_slot"][2] for r in raw}
    for r in raw:
        r.pop("_slot")
        r.pop("_target_slot")
    return {
        "search": {"city": "Dubai", "area": nbs[0], "adults": 2, "nights": nights},
        "target": {**target, "price": target["price"] * nights, "label": "Deluxe King · Breakfast · Free cancellation · cheapest",
                   "slot_ref": f"{target['tessera_id']}|{target['group']}|BB|1"} if target else None,
        "raw": raw, "cards": cards,
        "stats": {"rows": len(raw), "cards": len(cards), "duplicate_rows_hidden": len(raw) - len(distinct_slots),
                  "board_codes_raw": len(board_raw), "board_codes_normalized": len(board_norm)},
    }


# ---------------------------------------------------------------- explain
def explain_records(a: str, b: str) -> dict:
    n = DEMO.norm_by_id
    st = DEMO.state
    emb, row = st["emb"], DEMO.row
    ia, ib = row[a], row[b]
    x = np.array(pair_features(n[a], n[b], float(emb[ia] @ emb[ib]), st["index"].hashes.get(a), st["index"].hashes.get(b)),
                 dtype=np.float32).reshape(1, -1)
    raw = float(DEMO.matcher.raw(x)[0])
    p = float(DEMO.matcher.calibrate(np.array([raw]))[0])
    contrib = DEMO.matcher.contributions(x)[0]
    ex = explain(x[0], contrib, n[a], n[b], p, distinguishing_detail(n[a], n[b]))
    ex["raw"] = raw
    ex["band"] = DEMO.band_of(raw)
    ex["tau_accept"] = DEMO.current_risk["tau_accept"]
    ex["tau_reject"] = DEMO.current_risk["tau_reject"]
    ex["a"] = record_view(a)
    ex["b"] = record_view(b)
    return ex


def record_view(rid: str) -> dict:
    r = DEMO.rec_by_id.get(rid)
    if r is None:
        return {"record_id": rid}
    n = DEMO.norm_by_id.get(rid, {})
    return {"record_id": rid, "supplier": r["supplier"], "supplier_name": sup_name(r["supplier"]), "name": r["name"],
            "address": r.get("address"), "phone": r.get("phone"), "phone_e164": n.get("phone"), "lat": r.get("lat"),
            "lng": r.get("lng"), "stars": r.get("stars"), "brand": n.get("brand"), "core_name": n.get("core_name")}


# ---------------------------------------------------------------- inspector
def cluster_detail(tid: str) -> dict:
    h = DEMO.hotels[tid]
    members = [m for m in h["members"] if m in DEMO.rec_by_id]
    recs = [record_view(m) for m in members]
    # diff table vs golden values
    gold = {"name": h["name"], "address": h.get("address"), "phone": h.get("phone"), "stars": h["stars"],
            "coords": [round(h["lat"], 5), round(h["lng"], 5)]}
    from app.pipeline.features import haversine_m
    from app.pipeline.normalize import address_tokens
    names = Counter(DEMO.norm_by_id[m]["match_name"] for m in members)
    gold_name_key = names.most_common(1)[0][0]
    gold_addr = address_tokens(h.get("address"))
    diffs = []
    for r in recs:
        n = DEMO.norm_by_id[r["record_id"]]
        d = haversine_m(r["lat"], r["lng"], h["lat"], h["lng"])
        diffs.append({
            "record_id": r["record_id"], "supplier": r["supplier"],
            "cells": {
                "name": {"value": r["name"], "match": n["match_name"] == gold_name_key},
                "address": {"value": r["address"], "match": bool(r["address"]) and n["addr_tokens"] == gold_addr},
                "phone": {"value": r["phone"], "match": r["phone_e164"] == h.get("phone")},
                "coords": {"value": f"{r['lat']:.4f}, {r['lng']:.4f}", "match": d <= 60, "dist_m": round(d)},
                "stars": {"value": r["stars"], "match": r["stars"] == h["stars"]},
            },
            "dup_of": DEMO.state["alias"].get(r["record_id"]),
        })
    # weakest merge edge inside the cluster
    weakest = None
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            a, b = members[i], members[j]
            k = DEMO.pair_index.get((a, b), DEMO.pair_index.get((b, a)))
            if k is None or DEMO.norm_by_id[a]["supplier"] == DEMO.norm_by_id[b]["supplier"]:
                continue
            pk = float(DEMO.state["p"][k])
            if weakest is None or pk < weakest[0]:
                weakest = (pk, a, b)
    ex = explain_records(weakest[1], weakest[2]) if weakest else None
    rooms = []
    for gi, g in enumerate(h.get("rooms") or []):
        rooms.append({"group": gi, "name": g["name"], "tier": g["tier"], "suppliers": g["suppliers"], "ambiguous": g["ambiguous"],
                      "raw_names": [{"supplier": m["supplier"], "room_name": m["room_name"]} for m in g["members"]],
                      "slots": [slot_view(s) for s in g["slots"]]})
    photos = h.get("photos")
    trust = DEMO.state["trust"]
    return {
        "golden": {"tessera_id": tid, "name": h["name"], "brand": h["brand"], "stars": h["stars"], "city": h["city"],
                   "neighbourhood": h["neighbourhood"], "lat": h["lat"], "lng": h["lng"], "phone": h.get("phone"),
                   "address": h.get("address"), "hero": hero_of(h), "suppliers": h["suppliers"]},
        "gold_values": gold, "members": recs, "diffs": diffs, "explain": ex,
        "photos": {"total": photos["total"], "unique": photos["unique"][:24], "n_unique": len(photos["unique"]),
                   "suppliers": photos["suppliers"]} if photos else None,
        "rooms": rooms, "trust": [{"supplier": k, "name": sup_name(k), "trust": round(v, 3)} for k, v in sorted(trust.items())],
    }


def featured() -> list[dict]:
    out = []
    for h in DEMO.hotels.values():
        if h["city"] == "dubai" and h.get("photos"):
            out.append({"tessera_id": h["tessera_id"], "name": h["name"], "n_records": h["n_records"], "hero": hero_of(h)})
    out.sort(key=lambda x: (x["name"] != "Atlantis The Palm", -x["n_records"], x["name"]))
    return out


def near_miss() -> dict:
    sc = DEMO.state["showcase"]
    a_t, b_t = sc["Atlantis The Palm"], sc["Atlantis The Royal"]
    A, B = DEMO.hotels[a_t]["members"], DEMO.hotels[b_t]["members"]
    best = None
    for a in A:
        for b in B:
            k = DEMO.pair_index.get((a, b), DEMO.pair_index.get((b, a)))
            if k is None:
                continue
            if DEMO.norm_by_id[a]["supplier"] != "S1" and best is not None:
                pass
            pk = float(DEMO.state["p"][k])
            key = (DEMO.norm_by_id[a]["supplier"] == "S1" and DEMO.norm_by_id[b]["supplier"] == "S1", pk)
            if best is None or key > best[0]:
                best = (key, a, b)
    ex = explain_records(best[1], best[2])
    risky = max(((float(DEMO.state["p"][DEMO.pair_index.get((a, b), DEMO.pair_index.get((b, a)))]), a, b)
                 for a in A for b in B if DEMO.pair_index.get((a, b), DEMO.pair_index.get((b, a))) is not None), default=None)
    return {"pair": ex, "hotels": [{"tessera_id": a_t, "name": DEMO.hotels[a_t]["name"], "hero": hero_of(DEMO.hotels[a_t])},
                                   {"tessera_id": b_t, "name": DEMO.hotels[b_t]["name"], "hero": hero_of(DEMO.hotels[b_t])}],
            "max_cross_p": risky[0] if risky else None,
            "n_cross_pairs": sum(1 for a in A for b in B if DEMO.pair_index.get((a, b), DEMO.pair_index.get((b, a))) is not None)}


def activities() -> dict:
    prods = DEMO.state["products"]
    burj = [p for p in prods if p["attraction"] == "burj_khalifa"]
    return {"products": prods, "burj": burj, "eval": DEMO.state["activity_eval"],
            "n_listings": DEMO.state["summary"]["activities_listings"]}
