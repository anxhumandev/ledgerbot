"""Offer intelligence: compare every supplier offer for a property or experience and recommend one, with reasons.

Rules (enforced here, used by the inventory detail, Offer Intelligence, ranking preview and the Clean Feed API):
- Offers are only compared inside a comparable group: same physical room, board and refundability (hotels), or the
  same experience option (sightseeing). Different terms are never collapsed into one rate plan.
- The recommended offer is shown with its own price, cancellation deadline and payment terms; nothing is borrowed
  from a different offer.
- Eligibility: the supplier must not be paused, and the price must be within the configured competitiveness cap of the
  cheapest comparable offer. A supplier cannot win on margin alone if that breaks the cap.
- Among eligible offers, the winner maximises expected value: P(book) x P(confirm at the quoted price) x margin
  - (1 - P(confirm)) x failure cost (pipeline.offers.score_slot, with live supplier reliability).
- The synthetic feeds carry quotes, not inventory counts or taxes: availability is reported as "quoted" with the quote
  time, taxes as not provided.
"""
from __future__ import annotations

from app import config
from app.demo import DEMO
from app.errors import ApiError
from app.pipeline import offers as off
from app.services import catalog, settings_svc

BOARD = off.BOARD_LABEL


def _terms(o: dict) -> str:
    canc = (f"Free cancellation until {o['cancel_hours']} h before" if o.get("cancel_hours") else "Free cancellation") \
        if o.get("refundable") else "Non-refundable"
    pay = "Pay later" if o.get("payment") == "pay_later" else "Prepay"
    return f"{BOARD.get(o.get('board'), o.get('board'))} · {canc} · {pay}"


def select(offers: list[dict], cap_pct: float | None = None, paused: set[str] | None = None) -> dict:
    """Score a comparable group, mark eligibility and pick the recommended offer."""
    if not offers:
        return {"winner": None, "rows": [], "reasons": [], "cheapest": None}
    cap = settings_svc.get("price_cap_pct") if cap_pct is None else cap_pct
    paused = settings_svc.paused_suppliers() if paused is None else paused
    scored = off.score_slot(offers, DEMO.p_success)
    cheapest = min(scored, key=lambda o: (o["price"], o["supplier"]))
    for o in scored:
        prem = o["price"] / cheapest["price"] - 1 if cheapest["price"] else 0.0
        o["premium_pct"] = prem * 100
        o["eligible"], o["ineligible_reason"] = True, None
        if o["supplier"] in paused:
            o["eligible"], o["ineligible_reason"] = False, "Supplier feed paused"
        elif prem * 100 > cap + 1e-9:
            o["eligible"], o["ineligible_reason"] = False, f"{prem * 100:.1f}% above cheapest exceeds the {cap:g}% cap"
    elig = [o for o in scored if o["eligible"]]
    winner = max(elig, key=lambda o: (o["ev"], -o["price"])) if elig else None
    reasons = []
    if winner:
        others = [o for o in elig if o is not winner]
        if winner is cheapest or winner["price"] == cheapest["price"]:
            reasons.append("Lowest eligible price")
        else:
            reasons.append(f"₹{winner['price'] - cheapest['price']:,.0f} ({winner['premium_pct']:.1f}%) above the cheapest, within the {cap:g}% cap")
        if others and winner["p_success"] >= max(o["p_success"] for o in others) - 1e-9:
            reasons.append(f"Most reliable supplier here: {winner['p_success'] * 100:.1f}% confirm at quoted price")
        if others:
            runner = max(others, key=lambda o: o["ev"])
            reasons.append(f"Best reliability-adjusted value: +₹{winner['ev'] - runner['ev']:,.0f} expected vs {config.SUPPLIERS[runner['supplier']]['name']}")
        if winner.get("refundable") and (winner.get("cancel_hours") or 0) > (cheapest.get("cancel_hours") or 0) and winner is not cheapest:
            reasons.append(f"More flexible cancellation ({winner['cancel_hours']} h vs {cheapest.get('cancel_hours') or 0} h)")
        if winner.get("payment") == "pay_later" and cheapest.get("payment") != "pay_later":
            reasons.append("Pay-later terms")
    order = sorted(scored, key=lambda o: (o is not winner, not o["eligible"], -o["ev"]))
    return {"winner": winner, "rows": order, "cheapest": cheapest, "reasons": reasons, "cap_pct": cap}


def _hotel_row(o: dict, winner, cheapest, nights: int) -> dict:
    st = "recommended" if o is winner else ("ineligible" if not o["eligible"] else "alternative")
    return {"offer_id": o["offer_id"], "supplier": o["supplier"], "supplier_name": config.SUPPLIERS[o["supplier"]]["name"],
            "supplier_room_name": o.get("raw_room_name") or o.get("room_name"), "rate_text": o.get("room_name"),
            "rate_plan": _terms(o), "board": o.get("board"), "board_label": BOARD.get(o.get("board"), o.get("board")),
            "board_raw": o.get("board_raw"), "refundable": bool(o.get("refundable")),
            "cancel_hours": o.get("cancel_hours") if o.get("refundable") else None, "cancellation_raw": o.get("cancellation_raw"),
            "payment": o.get("payment"), "total": int(o["price"] * nights), "per_night": int(o["price"]), "currency": "INR",
            "taxes": None, "availability": "quoted", "rate_code": o.get("rate_code"),
            "reliability": round(float(o["p_success"]), 4), "expected_value": round(float(o["ev"]), 1),
            "premium_pct": round(o["premium_pct"], 2), "cheapest": o is cheapest, "eligible": o["eligible"],
            "ineligible_reason": o["ineligible_reason"], "status": st}


def hotel_offers(tid: str, nights: int = 3, board: str = "", refundable: str = "", payment: str = "", supplier: str = "") -> dict:
    h = DEMO.hotels.get(tid)
    if h is None:
        raise ApiError(404, "not_found", f"Property {tid} does not exist.")
    if not 1 <= nights <= 30:
        raise ApiError(422, "invalid_value", "Nights must be between 1 and 30.", {"field": "nights"})
    boards = set(board.split(",")) if board else None
    rooms_out, n_offers, n_groups = [], 0, 0
    for gi, g in enumerate(h.get("rooms") or []):
        groups = []
        for s in g["slots"]:
            offs = [o for o in s["offers"]
                    if (not boards or o.get("board") in boards)
                    and (refundable != "yes" or o.get("refundable")) and (refundable != "no" or not o.get("refundable"))
                    and (not payment or o.get("payment") == payment) and (not supplier or o["supplier"] == supplier)]
            if not offs:
                continue
            sel = select(offs)
            n_offers += len(offs)
            n_groups += 1
            win = sel["winner"]
            groups.append({"label": s["label"], "board": s["board"], "board_label": BOARD.get(s["board"], s["board"]),
                           "refundable": s["refundable"],
                           "recommended": _hotel_row(win, win, sel["cheapest"], nights) if win else None,
                           "reasons": sel["reasons"],
                           "offers": [_hotel_row(o, win, sel["cheapest"], nights) for o in sel["rows"]],
                           "terms_differ": len({(o.get("cancel_hours"), o.get("payment")) for o in offs}) > 1})
        if groups:
            ident = g["ident"]
            rooms_out.append({"room_id": f"{tid}-R{gi:02d}", "name": g["name"], "tier": g["tier"], "ambiguous": g.get("ambiguous", False),
                              "identity": {k: ident.get(k) for k in ("class", "bed", "view", "occupancy", "accessible")},
                              "suppliers": g["suppliers"], "supplier_room_names": [{"supplier": m["supplier"], "name": m["room_name"]} for m in g["members"]],
                              "groups": groups})
    return {"id": tid, "type": "hotel", "name": h["name"], "city": h["city"], "city_name": catalog.city_name(h["city"]),
            "nights": nights, "currency": "INR", "cap_pct": settings_svc.get("price_cap_pct"),
            "paused_suppliers": sorted(settings_svc.paused_suppliers()), "quoted_at": catalog.built_ts(),
            "rates_loaded": bool(h.get("rooms")), "rooms": rooms_out, "n_offers": n_offers, "n_groups": n_groups,
            "note": None if h.get("rooms") else "Rates are only generated for Dubai properties in the synthetic world."}


def activity_offers(pid: str, supplier: str = "") -> dict:
    p = catalog.product(pid)
    lst = catalog._listing_index()
    options = []
    for o in p["options"]:
        k = o["key"]  # time_slot, transfer, meal, private, language, addons
        units = [u for u in o["units"] if not supplier or u["supplier"] == supplier]
        if not units:
            continue
        pseudo = [{"offer_id": u["listing_id"], "supplier": u["supplier"], "price": u["prices"]["adult"], "refundable": False,
                   "payment": "prepay", "_u": u} for u in units]
        sel = select(pseudo)
        win = sel["winner"]
        rows = []
        for x in sel["rows"]:
            u, raw = x["_u"], lst.get(x["_u"]["listing_id"], {})
            rows.append({"listing_id": u["listing_id"], "supplier": u["supplier"], "supplier_name": config.SUPPLIERS[u["supplier"]]["name"],
                         "title": u["title"], "duration": u["duration"], "duration_min": u.get("duration_min"),
                         "adult": u["prices"]["adult"], "child": u["prices"].get("child"), "infant": u["prices"].get("infant"),
                         "currency": "INR", "meeting_point": raw.get("meeting_point"), "inclusions": raw.get("inclusions"),
                         "language": raw.get("language"), "cancellation": None, "availability": "quoted",
                         "reliability": round(float(x["p_success"]), 4), "expected_value": round(float(x["ev"]), 1),
                         "premium_pct": round(x["premium_pct"], 2), "cheapest": x is sel["cheapest"], "eligible": x["eligible"],
                         "ineligible_reason": x["ineligible_reason"],
                         "status": "recommended" if x is win else ("ineligible" if not x["eligible"] else "alternative")})
        durations = sorted({r["duration_min"] for r in rows if r["duration_min"]})
        options.append({"label": o["label"], "time_slot": k[0], "transfer": bool(k[1]), "meal": bool(k[2]), "private": bool(k[3]),
                        "language": k[4], "addons": list(k[5]) if len(k) > 5 else [], "suppliers": o["suppliers"],
                        "duration_range": [durations[0], durations[-1]] if durations else None,
                        "recommended": next((r for r in rows if r["status"] == "recommended"), None),
                        "reasons": sel["reasons"], "units": rows})
    return {"id": pid, "type": "activity", "name": p["label"], "attraction": p["attraction"], "access_tier": p["tier"],
            "currency": "INR", "cap_pct": settings_svc.get("price_cap_pct"), "quoted_at": catalog.built_ts(),
            "price_basis": "Adult ticket price. Supplier feeds do not include cancellation terms for sightseeing.",
            "options": options}


def headline(tid: str, nights: int = 3) -> dict | None:
    """The recommended offer of the cheapest comparable group: a coherent 'from' offer for search results."""
    h = DEMO.hotels.get(tid)
    if not h or not h.get("rooms"):
        return None
    best = None
    for g in h["rooms"]:
        for s in g["slots"]:
            sel = select(s["offers"])
            w = sel["winner"]
            if w and (best is None or w["price"] < best[0]["price"]):
                best = (w, g, s)
    if not best:
        return None
    w, g, s = best
    return {"room": g["name"], "rate_plan": _terms(w), "supplier": w["supplier"], "supplier_name": config.SUPPLIERS[w["supplier"]]["name"],
            "total": int(w["price"] * nights), "nights": nights, "refundable": bool(w["refundable"]),
            "cancel_hours": w.get("cancel_hours") if w.get("refundable") else None, "payment": w.get("payment"),
            "board": w.get("board"), "reliability": round(float(w["p_success"]), 4)}


def search(kind: str = "hotel", q: str = "", city: str = "", limit: int = 20) -> list[dict]:
    ql = q.lower().strip()
    out = []
    if kind == "hotel":
        for h in DEMO.hotels.values():
            if not h.get("rooms") or (city and h["city"] != city) or (ql and ql not in h["name"].lower() and ql not in h["tessera_id"].lower()):
                continue
            out.append({"id": h["tessera_id"], "name": h["name"], "city_name": catalog.city_name(h["city"]), "area": h.get("neighbourhood"),
                        "n_suppliers": len(h["suppliers"]), "n_offers": h.get("n_offers", 0)})
        out.sort(key=lambda r: (-r["n_suppliers"], -r["n_offers"], r["name"]))
    else:
        for p in DEMO.state["products"]:
            if ql and ql not in p["label"].lower() and ql not in p["product_id"].lower():
                continue
            out.append({"id": p["product_id"], "name": p["label"], "city_name": catalog.activity_city(p),
                        "n_suppliers": len({u["supplier"] for o in p["options"] for u in o["units"]}), "n_offers": p["n_listings"]})
        out.sort(key=lambda r: (-r["n_suppliers"], r["name"]))
    return out[:limit]
