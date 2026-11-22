"""Clean Feed API: the read model API buyers get, next to what suppliers actually send.

TBO sells through two channels: agents on the B2B portal and API customers. Both should receive the same
de-duplicated shelf. `hotel_offers` is that shelf as an API response: one hotel, its physical rooms, and per room
one offer per commercial slot (board x refundability), with ranked fallbacks if the chosen supplier fails at booking.

`supplier_payloads` shows the same hotel as each supplier delivers it. The field layouts are illustrative of the
formats bed banks and wholesalers use (caps codes, Spanish keys, terse keys); every value comes from the synthetic
supplier feed unchanged.
"""
from __future__ import annotations

import json
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


def _slot_offer(slot: dict, nights: int, strategy: str) -> dict:
    sel = off.select(slot["offers"], DEMO.p_success, strategy)
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
            "offers": [_slot_offer(s, nights, strategy) for s in slots],
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


# ---------------------------------------------------------------- what suppliers send
def _rates_by_record(h: dict) -> dict:
    by = {}
    for g in h.get("rooms") or []:
        for s in g["slots"]:
            for o in s["offers"]:
                by.setdefault(o["record_id"], []).append(o)
    for rs in by.values():
        rs.sort(key=lambda o: o["offer_id"])
    return by


def _shape(code: str, r: dict, rates: list[dict], nights: int) -> dict:
    """One supplier's payload in its own field vocabulary. Values are the raw feed values."""
    p = lambda o: int(o["price"] * nights)  # noqa: E731
    if code == "S1":
        return {"hotelCode": r["record_id"], "hotelName": r["name"], "address": r.get("address"), "phone": r.get("phone"),
                "geo": {"lat": r.get("lat"), "lng": r.get("lng")}, "starRating": r.get("stars"),
                "rates": [{"roomName": o["room_name"], "board": o["board_raw"], "cancellation": o["cancellation_raw"],
                           "price": {"amount": p(o), "currency": "INR"}, "rateKey": o["rate_code"]} for o in rates]}
    if code == "S2":
        return {"HTL_ID": r["record_id"], "HTL_NAME": r["name"], "ADDR": r.get("address"), "TEL": r.get("phone"),
                "LAT": r.get("lat"), "LON": r.get("lng"), "CAT": f"{r.get('stars')}*" if r.get("stars") else None,
                "RATES": [{"RM": o["room_name"], "BRD": o["board_raw"], "CXL": o["cancellation_raw"], "AMT": p(o),
                           "CUR": "INR", "RATE_KEY": o["rate_code"]} for o in rates]}
    if code == "S3":
        return {"codigo": r["record_id"], "nombre": r["name"], "direccion": r.get("address"), "telefono": r.get("phone"),
                "coordenadas": f"{r.get('lat')},{r.get('lng')}", "categoria": r.get("stars"),
                "tarifas": [{"habitacion": o["room_name"], "regimen": o["board_raw"], "cancelacion": o["cancellation_raw"],
                             "precio": p(o), "moneda": "INR", "clave": o["rate_code"]} for o in rates]}
    if code == "S4":
        return {"property": {"id": r["record_id"], "marketingName": r["name"], "rating": r.get("stars"),
                             "location": {"address": r.get("address"), "latitude": r.get("lat"), "longitude": r.get("lng")},
                             "contact": r.get("phone")},
                "offers": [{"roomDescription": o["room_name"], "inclusions": o["board_raw"], "policy": o["cancellation_raw"],
                            "total": p(o), "code": o["rate_code"]} for o in rates]}
    if code == "S5":
        return {"id": r["record_id"], "n": r["name"], "a": r.get("address"), "ph": r.get("phone"), "lt": r.get("lat"),
                "lg": r.get("lng"), "s": r.get("stars"),
                "r": [{"rn": o["room_name"], "b": o["board_raw"], "c": o["cancellation_raw"], "p": p(o), "k": o["rate_code"]}
                      for o in rates]}
    return {"hotel_id": r["record_id"], "hotel_name": r["name"], "address": r.get("address"), "phone": r.get("phone"),
            "lat": r.get("lat"), "lng": r.get("lng"), "stars": r.get("stars"),
            "rates": [{"room": o["room_name"], "meal_plan": o["board_raw"], "cancel_policy": o["cancellation_raw"],
                       "price_inr": p(o), "rate_id": o["rate_code"]} for o in rates]}


def supplier_payloads(tid: str, nights: int = 3) -> dict:
    h = _hotel(tid)
    by = _rates_by_record(h)
    out = []
    vocab_board, vocab_cxl = set(), set()
    for m in h["members"]:
        r = DEMO.rec_by_id.get(m)
        if r is None:
            continue
        rates = by.get(m, [])
        vocab_board |= {o["board_raw"] for o in rates}
        vocab_cxl |= {o["cancellation_raw"] for o in rates}
        payload = _shape(r["supplier"], r, rates, nights)
        out.append({"supplier": r["supplier"], "supplier_name": config.SUPPLIERS[r["supplier"]]["name"],
                    "n_rates": len(rates), "bytes": len(json.dumps(payload, ensure_ascii=False).encode()),
                    "payload": payload})
    out.sort(key=lambda x: x["supplier"])
    clean = hotel_offers(tid, nights)
    return {"tessera_id": tid, "name": h["name"], "suppliers": out,
            "stats": {"payloads": len(out), "rates": sum(x["n_rates"] for x in out),
                      "board_vocabulary": len(vocab_board), "cancellation_vocabulary": len(vocab_cxl),
                      "raw_bytes": sum(x["bytes"] for x in out),
                      "clean_bytes": len(json.dumps(clean, ensure_ascii=False).encode()),
                      "clean_rooms": len(clean["rooms"]),
                      "clean_offers": sum(len(r["offers"]) for r in clean["rooms"])}}
