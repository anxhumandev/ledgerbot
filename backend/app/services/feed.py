"""Clean Feed API: the read model API buyers get, next to what suppliers actually send.

TBO sells through two channels: agents on the B2B portal and API customers. Both should receive the same
de-duplicated shelf. `hotel_offers` is that shelf as an API response: one hotel, its physical rooms, and per room
one offer per commercial slot (board x refundability), with ranked fallbacks if the chosen supplier fails at booking.

"""
from __future__ import annotations

import time

from app import config
from app.demo import DEMO
from app.pipeline import offers as off

API_VERSION = "v1"


def _hotel(tid: str) -> dict:
    h = DEMO.hotels.get(tid)
    if h is None:
        raise KeyError(tid)
    return h


def _slot_offer(slot: dict, nights: int, strategy: str) -> dict | None:
    from app.services import offers_svc
    if strategy == "cheapest":
        sel = off.select(slot["offers"], DEMO.p_success, strategy)
        ranked = sel["ranked"]
    else:  # same rules as the portal: comparable group, paused suppliers excluded, competitiveness cap
        sel = offers_svc.select(slot["offers"])
        if not sel["winner"]:
            return None
        sel["why"] = "; ".join(sel["reasons"])
        ranked = [o for o in sel["rows"] if o["eligible"]]
        sel["ranked"] = ranked
    w = sel["winner"]
    hrs = w.get("cancel_hours")
    return {
        "offer_id": w["offer_id"],
        "board": w["board"],
        "board_label": off.BOARD_LABEL.get(w["board"], w["board"]),
        "refundable": bool(w["refundable"]),
        "free_cancellation_until_hours_before": hrs if w["refundable"] else None,
        "payment": w["payment"],
        "price": {"amount": int(w["price"] * nights), "currency": "INR", "nights": nights},
        "booking_token": w["rate_code"],
        "confirm_probability": round(float(w["p_success"]), 4),
        "why": sel["why"],
        "fallbacks": [o["rate_code"] for o in sel["ranked"][1:4]],
        "competing_supplier_offers": len(sel["ranked"]),
    }


def hotel_offers(tid: str, nights: int = 3, strategy: str = "expected_value") -> dict:
    t0 = time.perf_counter()
    h = _hotel(tid)
    rooms = []
    n_rates = 0
    for gi, g in enumerate(h.get("rooms") or []):
        if not g["slots"]:
            continue
        n_rates += sum(len(s["offers"]) for s in g["slots"])
        ident = g["ident"]
        slots = sorted(g["slots"], key=lambda s: (s["board"] != "RO", not s["refundable"]))
        rooms.append({
            "room_id": f"{tid}-R{gi:02d}",
            "name": g["name"],
            "identity": {"class": ident.get("class"), "bed": ident.get("bed"), "view": ident.get("view"),
                         "max_occupancy": ident.get("occupancy"), "accessible": bool(ident.get("accessible"))},
            "match_tier": g["tier"].lower(),
            "supplier_room_names": len(g["members"]),
            "offers": [o for o in (_slot_offer(s, nights, strategy) for s in slots) if o],
        })
    rooms.sort(key=lambda r: min(o["price"]["amount"] for o in r["offers"]))
    members = [m for m in h["members"] if m in DEMO.rec_by_id]
    body = {
        "hotel": {
            "ledger_id": tid, "name": h["name"], "brand": h.get("brand"), "stars": h.get("stars"),
            "address": h.get("address"), "phone": h.get("phone"),
            "geo": {"lat": round(h["lat"], 6), "lng": round(h["lng"], 6)},
            "city": h["city"].title(), "neighbourhood": h.get("neighbourhood"),
        },
        "rooms": rooms,
        "meta": {
            "api_version": API_VERSION,
            "source_supplier_records": len(members),
            "source_supplier_rates": n_rates,
            "suppliers": len(h["suppliers"]),
            "offer_selection": strategy,
            "mapping_alpha": DEMO.alpha,
        },
    }
    body["meta"]["server_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return body


def search(area: str = "marina", nights: int = 3) -> dict:
    from app.services.views import AREA_NB
    t0 = time.perf_counter()
    nbs = AREA_NB.get(area, ["Dubai Marina"])
    out = []
    n_rates = n_records = 0
    for h in DEMO.hotels.values():
        if h["city"] != "dubai" or h.get("neighbourhood") not in nbs or not h.get("rooms"):
            continue
        prices = [min(o["price"] for o in s["offers"]) for g in h["rooms"] for s in g["slots"] if s["offers"]]
        if not prices:
            continue
        n_rates += sum(len(s["offers"]) for g in h["rooms"] for s in g["slots"])
        n_records += sum(1 for m in h["members"] if m in DEMO.rec_by_id)
        out.append({"ledger_id": h["tessera_id"], "name": h["name"], "stars": h.get("stars"),
                    "from_price": {"amount": int(min(prices) * nights), "currency": "INR"},
                    "rooms": sum(1 for g in h["rooms"] if g["slots"]), "suppliers": len(h["suppliers"])})
    out.sort(key=lambda x: (-x["suppliers"], x["name"]))
    return {"results": out, "meta": {"api_version": API_VERSION, "area": nbs[0], "nights": nights,
                                     "source_supplier_records": n_records, "source_supplier_rates": n_rates,
                                     "server_ms": round((time.perf_counter() - t0) * 1000, 2)}}
