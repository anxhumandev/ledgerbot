"""Deterministic synthetic multi-supplier world for Tessera.

    python -m data.generate            # writes backend/data/world/*.json|parquet + photos
    python -m data.generate --sample   # print a few noisy supplier records per supplier

Ground truth lives in truth.json and is only consumed by the pipeline through the
labelled sample (labels_sample.json). Evaluation is free to use all of it.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import random
import string
import sys
import time
from collections import defaultdict
from itertools import combinations

import numpy as np
import orjson
import pandas as pd

from app import config
from data import photos as ph
from data.tables import (ACTIVITIES, ACTIVITY_TITLES, AMENITIES, BRANDS, CITIES, CLASS_BY_TIER, CLASS_PRICE,
                         CLASS_SIZE, CURATED_DUBAI, INDEP_ADJ, INDEP_ARABIC, INDEP_NOUN, INDEP_TYPE, NB_PRICE,
                         PERSONAS, SHOWCASE, STAR_BASE_PRICE, VIEW_PRICE, VIEWS_BY_NB)

SEED = config.SEED
SUPPLIERS = ["S1", "S2", "S3", "S4", "S5"]
COVERAGE = {"S1": 0.42, "S2": 0.85, "S3": 0.68, "S4": 0.85, "S5": 0.82}
CITY_SIZES_LARGE = {"abu_dhabi": 560, "singapore": 560, "bangkok": 560, "bali": 560}
N_DUBAI = 250
MAPPING_ERROR_RATE = 0.015
N_TRAIN_LABELS = 800
N_CAL_LABELS_MAX = 7000


def R(tag: str) -> random.Random:
    return random.Random(f"{SEED}:{tag}")


def write_json(name: str, obj) -> None:
    (config.WORLD_DIR / name).write_bytes(orjson.dumps(obj, option=orjson.OPT_INDENT_2 if name == "personas.json" else 0))


def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lng2) - np.radians(lng1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def offset_m(lat, lng, dx_m, dy_m):
    return lat + dy_m / 111_320.0, lng + dx_m / (111_320.0 * math.cos(math.radians(lat)))


# =============================================================================== canonical hotels
def brand_stars(rng, brand):
    if brand is None:
        return rng.choices([2, 3, 4, 5], [0.15, 0.38, 0.3, 0.17])[0]
    tier = BRANDS[brand][1]
    return {"lux": 5, "up": 5 if rng.random() < 0.55 else 4,
            "mid": 4 if rng.random() < 0.65 else 3, "eco": 3 if rng.random() < 0.75 else 2}[tier]


def tier_of(brand, stars):
    if brand:
        return BRANDS[brand][1]
    return {2: "eco", 3: "eco", 4: "mid", 5: "up"}[stars]


def make_phone(rng, city):
    c = CITIES[city]
    digits = rng.choice(c["phone_lead"]) + "".join(rng.choice(string.digits) for _ in range(c["phone_digits"] - 1))
    return c["phone_prefix"] + digits


SIG_DROP = {"hotel", "resort", "spa", "&", "and", "apartments", "suites", "villas", "boutique", "the", "-"}


def name_signature(name: str, city: str) -> str:
    toks = [t for t in name.lower().split() if t not in SIG_DROP and t not in CITIES[city]["name"].lower().split()]
    return "sig:" + city + ":" + " ".join(sorted(toks))


def gen_name(rng, city, nb, used):
    cname = CITIES[city]["name"]
    landmarks = CITIES[city].get("landmarks", {}).get(nb, [nb])
    brands = list(BRANDS)
    for _ in range(200):
        if rng.random() < 0.62:
            b = rng.choice(brands)
            if b in ("W", "Atlantis", "Armani", "Bulgari", "One&Only", "Burj"):
                continue
            pat = rng.random()
            if pat < 0.35:
                name = f"{b} {cname} {nb}"
            elif pat < 0.6:
                name = f"{b} {nb}"
            elif pat < 0.85:
                name = f"{b} {cname} {rng.choice(landmarks)}"
            else:
                name = f"{b} {rng.choice(landmarks)}"
            brand = b
        else:
            pat = rng.random()
            if pat < 0.45:
                name = f"{rng.choice(INDEP_ADJ)} {rng.choice(INDEP_NOUN)} {rng.choice(INDEP_TYPE)}"
            elif pat < 0.75:
                name = f"Al {rng.choice(INDEP_ARABIC)} {rng.choice(INDEP_TYPE)}"
            else:
                name = f"{rng.choice(INDEP_ADJ)} {rng.choice(landmarks)} {rng.choice(INDEP_TYPE)}"
            if city == "bali" and rng.random() < 0.5:
                name = name.replace("Hotel Apartments", "Villas").replace("Hotel", "Resort & Spa")
            brand = None
        name = " ".join(name.split())
        sig = name_signature(name, city)
        if name not in used and sig not in used:
            used.add(name)
            used.add(sig)
            return name, brand
    raise RuntimeError("name space exhausted")


def gen_rooms(rng, hotel):
    tier, nb = hotel["tier"], hotel["neighbourhood"]
    classes = CLASS_BY_TIER[tier]
    views = VIEWS_BY_NB.get(nb, ["City", "Garden", "Pool", "None"])
    large_bed = {"lux": "King", "up": "King", "mid": rng.choice(["King", "Queen"]), "eco": rng.choice(["Double", "Queen"])}[tier]
    n = rng.randint(3, 8)
    combos, seen = [], set()
    tries = 0
    while len(combos) < n and tries < 200:
        tries += 1
        idx = min(len(classes) - 1, int(abs(rng.gauss(0, len(classes) / 2.2))))
        cls = classes[idx] if len(combos) > 1 else classes[min(len(combos), len(classes) - 1)]
        if cls == "Villa" and nb not in ("Palm Jumeirah", "Jumeirah", "Seminyak", "Ubud", "Nusa Dua", "Canggu", "Sentosa", "Saadiyat Island"):
            continue
        bed = large_bed if (cls in ("Junior Suite", "Suite", "Villa") or rng.random() < 0.65) else "Twin"
        view = views[0] if rng.random() < 0.45 else rng.choice(views)
        key = (cls, bed, view, False)
        if key in seen:
            continue
        seen.add(key)
        combos.append(key)
    if rng.random() < 0.3:
        key = (classes[0], large_bed, "None" if "None" in views else views[-1], True)
        if key not in seen:
            combos.append(key)
    combos.sort(key=lambda k: (CLASS_PRICE[k[0]], k[1], k[2]))
    rooms = []
    for k, (cls, bed, view, acc) in enumerate(combos):
        rooms.append({
            "room_id": f"{hotel['hotel_id']}-R{k + 1}", "class": cls, "bed": bed, "view": view,
            "size_sqm": int(CLASS_SIZE[cls] * rng.uniform(0.9, 1.25)),
            "max_occupancy": 4 if cls == "Villa" else (3 if cls in ("Suite", "Junior Suite") else 2),
            "accessible": acc,
            "price_factor": round(CLASS_PRICE[cls] * VIEW_PRICE[view] * (0.97 if acc else 1.0), 3),
        })
    return rooms


def gen_canonical(world_kind: str):
    rng = R("hotels")
    hotels, used = [], set()
    hid = 0

    def add(name, brand, city, nb, stars, lat, lng, showcase=False):
        nonlocal hid
        hid += 1
        c = CITIES[city]
        streets = c.get("streets", {}).get(nb, [f"{nb} Road", f"{nb} Avenue", "Main Street"])
        h = {
            "hotel_id": f"H{hid:04d}", "name": name, "brand": brand,
            "chain": BRANDS[brand][0] if brand else None, "stars": stars,
            "tier": tier_of(brand, stars), "lat": round(lat, 6), "lng": round(lng, 6),
            "address": f"{rng.randint(1, 400)} {rng.choice(streets)}, {nb}, {c['name']}",
            "phone": make_phone(rng, city), "city": city, "neighbourhood": nb,
            "amenities": AMENITIES[stars][:], "showcase": showcase,
            "review_score": round(min(9.8, max(6.0, rng.gauss(6.6 + 0.62 * stars, 0.45))), 1),
            "popularity": round(float(np.exp(rng.gauss(0, 0.8))) * (1.5 if showcase else 1.0), 3),
            "platinum": rng.random() < 0.15,
        }
        base = STAR_BASE_PRICE[stars] * NB_PRICE.get(nb, 1.0) * rng.uniform(0.85, 1.2)
        if city != "dubai":
            base *= {"abu_dhabi": 0.95, "singapore": 1.15, "bangkok": 0.55, "bali": 0.6}[city]
        if name in ("Atlantis The Royal", "Burj Al Arab Jumeirah", "One&Only The Palm", "Armani Hotel Dubai"):
            base *= 2.2
        h["base_price"] = round(base, -1)
        h["rooms"] = gen_rooms(rng, h)
        hotels.append(h)
        used.add(name)
        used.add(name_signature(name, city))
        return h

    for (name, brand, nb, stars, lat, lng) in CURATED_DUBAI:
        add(name, brand, "dubai", nb, stars, lat, lng, showcase=name in SHOWCASE)
    nbs = list(CITIES["dubai"]["neighbourhoods"].items())
    while len(hotels) < N_DUBAI:
        nb, (la0, la1, lo0, lo1) = rng.choice(nbs)
        name, brand = gen_name(rng, "dubai", nb, used)
        add(name, brand, "dubai", nb, brand_stars(rng, brand), rng.uniform(la0, la1), rng.uniform(lo0, lo1))
    if world_kind == "large":
        for city, n in CITY_SIZES_LARGE.items():
            nbs = list(CITIES[city]["neighbourhoods"].items())
            for _ in range(n):
                nb, (la0, la1, lo0, lo1) = rng.choice(nbs)
                name, brand = gen_name(rng, city, nb, used)
                add(name, brand, city, nb, brand_stars(rng, brand), rng.uniform(la0, la1), rng.uniform(lo0, lo1))
    return hotels


# =============================================================================== noise operators
ABBR_S2 = {"HOTEL": "HTL", "APARTMENTS": "APTS", "RESORT": "RST", "DUBAI": "DXB", "INTERNATIONAL": "INTL",
           "BEACH": "BCH", "SUITES": "STES", "RESIDENCE": "RES", "PALM JUMEIRAH": "PALM JUM", "DOWNTOWN": "DWTN",
           "BUSINESS BAY": "BUS BAY", "CITY CENTRE": "CTY CTR", "JUMEIRAH BEACH RESIDENCE": "JBR"}
TRANSLIT = {"Jumeirah": "Jumeira", "Deira": "Diera", "Movenpick": "Mövenpick", "Meridien": "Méridien",
            "Saadiyat": "Saadiyaat", "Sukhumvit": "Sukhumwit", "Seminyak": "Seminyak", "A'Salam": "Asalam"}
KEYBOARD = "qwertyuiopasdfghjklzxcvbnm"


def op_drop_hotel(n, rng, p):
    if rng.random() < p:
        for w in (" Hotel & Spa", " Hotel", " Resort & Spa", " Resort", "Hotel "):
            if w in n:
                return n.replace(w, " " if w.endswith(" ") else "", 1).strip()
    return n


def op_city_suffix(n, rng, p, city):
    cname = CITIES[city]["name"]
    if rng.random() < p:
        if cname in n:
            return " ".join(n.replace(cname, "").split())
        return n + rng.choice([f" {cname}", f" - {cname}", f", {cname}", f" {CITIES[city]['code']}"])
    return n


def op_reorder(n, rng, p, city):
    cname = CITIES[city]["name"]
    if rng.random() < p and n.startswith(cname + " "):
        rest = n[len(cname) + 1:]
        for w in (" Hotel & Suites", " Hotel"):
            rest = rest.replace(w, "")
        return f"{rest} {cname}"
    return n


def op_amp(n, rng, p, to="and"):
    if rng.random() < p:
        if "&" in n:
            return n.replace("&", to if to != "and" else "and").replace("  ", " ")
        if " and " in n:
            return n.replace(" and ", " & ")
    return n


def op_translit(n, rng, p):
    for a, b in TRANSLIT.items():
        if a in n and rng.random() < p:
            n = n.replace(a, b)
    return n


def op_typos(n, rng, rate):
    out = []
    for ch in n:
        if ch.isalpha() and rng.random() < rate:
            k = rng.random()
            if k < 0.35:
                out.append(rng.choice(KEYBOARD))
            elif k < 0.6:
                continue
            elif k < 0.8:
                out.append(ch + ch)
            else:
                out.append(ch)
                out.append(rng.choice(KEYBOARD))
        else:
            out.append(ch)
    return "".join(out)


def op_drop_word(n, rng, p, brand):
    words = n.split()
    if rng.random() < p and len(words) > 3:
        cands = [i for i, w in enumerate(words) if not (brand and w in brand.split()) and i > 0]
        if cands:
            del words[rng.choice(cands)]
    return " ".join(words)


def render_name(h, sup, rng):
    n, city = h["name"], h["city"]
    if sup == "S1":
        return n
    if sup == "S2":
        n = op_drop_hotel(n, rng, 0.25)
        n = op_reorder(n, rng, 0.15, city)
        n = n.upper().replace("&", "AND" if rng.random() < 0.5 else "&")
        for a, b in ABBR_S2.items():
            if a in n and rng.random() < 0.7:
                n = n.replace(a, b)
        if CITIES[city]["name"].upper() not in n and CITIES[city]["code"] not in n and rng.random() < 0.55:
            n += rng.choice([f" {CITIES[city]['code']}", f" - {CITIES[city]['name'].upper()}"])
        return " ".join(n.split())
    if sup == "S3":
        n = op_translit(n, rng, 0.4)
        n = op_amp(n, rng, 0.5, to="y")
        if not n.startswith("Hotel") and rng.random() < 0.45:
            n = "Hotel " + op_drop_hotel(n, rng, 1.0)
        n = op_city_suffix(n, rng, 0.35, city)
        return " ".join(n.split())
    if sup == "S4":
        r = rng.random()
        if r < 0.3 and not n.startswith("The "):
            n = "The " + n
        r = rng.random()
        if h["chain"] and r < 0.35:
            art = "an" if h["chain"][0] in "AEIOU" else "a"
            n = f"{n}, {art} {h['chain']} Hotel"
        elif r < 0.5:
            n = f"{n} – Luxury Collection"
        elif r < 0.65:
            n = op_city_suffix(n, rng, 1.0, city)
        return n
    if sup == "S5":
        n = op_drop_word(n, rng, 0.2, h["brand"])
        n = op_translit(n, rng, 0.3)
        n = op_amp(n, rng, 0.5)
        n = op_city_suffix(n, rng, 0.3, city)
        n = op_typos(n, rng, 0.02)
        if rng.random() < 0.3:
            n = n.lower()
        return " ".join(n.split())
    if sup == "S6":
        n = op_amp(n, rng, 0.7)
        n = op_drop_hotel(n, rng, 0.2)
        if rng.random() < 0.5:
            n = n + f", {CITIES[city]['name']}" if CITIES[city]["name"] not in n else n
        if rng.random() < 0.3:
            n = n.replace("Hotel", "Htl").replace("Apartments", "Apts")
        r = rng.random()
        if r < 0.2:
            n = n.lower()
        elif r < 0.35:
            n = n.title()
        return " ".join(n.split())
    return n


STYLE = {
    "S1": {"sigma": 15, "gross": 0.0, "phone_missing": 0.01, "addr_missing": 0.02, "star_err": 0.01},
    "S2": {"sigma": 60, "gross": 0.02, "phone_missing": 0.05, "addr_missing": 0.10, "star_err": 0.05},
    "S3": {"sigma": 40, "gross": 0.0, "phone_missing": 0.05, "addr_missing": 0.08, "star_err": 0.05},
    "S4": {"sigma": 25, "gross": 0.0, "phone_missing": 0.03, "addr_missing": 0.05, "star_err": 0.03},
    "S5": {"sigma": 120, "gross": 0.005, "phone_missing": 0.15, "addr_missing": 0.18, "star_err": 0.06},
    "S6": {"sigma": 80, "gross": 0.005, "phone_missing": 0.06, "addr_missing": 0.10, "star_err": 0.05},
}
PHONE_FMT = {"S1": ["e164s"], "S2": ["0dash", "00"], "S3": ["e164s", "00"], "S4": ["e164s", "paren"],
             "S5": ["0dash", "plain", "e164"], "S6": ["e164", "0dash"]}


def render_phone(e164: str, sup, rng):
    fmt = rng.choice(PHONE_FMT[sup])
    cc_len = 4 if e164.startswith("+62") else 3 if e164.startswith(("+97", "+65", "+66")) else 3
    cc, rest = e164[1:cc_len + 1], e164[cc_len + 1:]
    if e164.startswith("+65"):
        cc, rest = "65", e164[3:]
    elif e164.startswith("+971"):
        cc, rest = "971", e164[4:]
    elif e164.startswith("+66"):
        cc, rest = "66", e164[3:]
    elif e164.startswith("+62"):
        cc, rest = "62", e164[3:]
    if fmt == "e164":
        return e164
    if fmt == "e164s":
        return f"+{cc} {rest[0]} {rest[1:4]} {rest[4:]}" if len(rest) > 6 else f"+{cc} {rest}"
    if fmt == "0dash":
        return f"0{rest[0]}-{rest[1:]}" if cc != "65" else rest
    if fmt == "00":
        return f"00{cc}{rest}"
    if fmt == "paren":
        return f"(0{rest[0]}) {rest[1:4]} {rest[4:]}" if cc != "65" else f"+65 {rest}"
    return rest


def render_address(addr: str, sup, rng):
    a = addr
    if sup in ("S2", "S5"):
        a = a.replace("Road", "Rd").replace("Street", "St").replace("Boulevard", "Blvd")
        a = a.upper() if sup == "S2" else a
    if sup == "S3":
        a = a.replace("Dubai", "Dubái").replace("Rd", "Carretera") if rng.random() < 0.3 else a
    if sup in ("S5", "S6") and rng.random() < 0.3:
        parts = a.split(", ")
        a = ", ".join(parts[:-1])  # drop city
    return a


# =============================================================================== rooms
CLASS_ABBR = {"Standard": "STD", "Superior": "SUP", "Deluxe": "DLX", "Premier": "PREM", "Executive": "EXEC",
              "Junior Suite": "JR STE", "Suite": "STE", "Villa": "VILLA"}
BED_S2 = {"King": ["DBL", "KG", "K"], "Queen": ["DBL", "QN"], "Double": ["DBL"], "Twin": ["TWN", "TWIN"]}
VIEW_ABBR = {"Sea": "SV", "City": "CV", "Burj": "BV", "Marina": "MV", "Garden": "GV", "Pool": "PV", "None": ""}
CLASS_ES = {"Standard": "Estándar", "Superior": "Superior", "Deluxe": "Deluxe", "Premier": "Premier",
            "Executive": "Ejecutiva", "Junior Suite": "Junior Suite", "Suite": "Suite", "Villa": "Villa"}
BED_ES = {"King": ["Doble cama King", "Doble King"], "Queen": ["Doble cama Queen"], "Double": ["Doble"],
          "Twin": ["Twin", "Dos camas"]}
VIEW_ES = {"Sea": "Vista Mar", "City": "Vista Ciudad", "Burj": "Vista Burj Khalifa", "Marina": "Vista Marina",
           "Garden": "Vista Jardín", "Pool": "Vista Piscina", "None": ""}
VIEW_S4 = {"Sea": ["Ocean View", "Sea View"], "Burj": ["Burj Khalifa View", "Fountain View"],
           "Marina": ["Marina View"], "City": ["City View", "Skyline View"], "Garden": ["Garden View"],
           "Pool": ["Pool View"], "None": [""]}
S4_EXTRAS = ["with Club Access", "with Balcony", "with Lounge Access", "", "", "", ""]
BOARD_VOCAB = {
    "S1": {"RO": "Room Only", "BB": "Bed & Breakfast", "HB": "Half Board", "FB": "Full Board", "AI": "All Inclusive"},
    "S2": {"RO": "RO", "BB": "BB", "HB": "HB", "FB": "FB", "AI": "AI"},
    "S3": {"RO": "SA", "BB": "AD", "HB": "MP", "FB": "PC", "AI": "TI"},
    "S4": {"RO": "Room only", "BB": "Breakfast included", "HB": "Half board (breakfast & dinner)",
           "FB": "Full board", "AI": "All-inclusive"},
    "S5": {"RO": ["ROOM ONLY", "RO", "No meals"], "BB": ["BREAKFAST", "BB", "B&B"], "HB": ["HB", "HALF BOARD"],
           "FB": ["FB", "FULL BOARD"], "AI": ["AI", "ALL INC"]},
    "S6": {"RO": "Room Only", "BB": "B&B", "HB": "HB", "FB": "FB", "AI": "AI"},
}


def board_raw(sup, board, rng):
    v = BOARD_VOCAB[sup][board]
    return rng.choice(v) if isinstance(v, list) else v


def cancel_raw(sup, refundable, hours, rng):
    if not refundable:
        return {"S1": "Non-refundable", "S2": "NRF", "S3": "No reembolsable", "S4": "Non-refundable",
                "S5": rng.choice(["NON REF", "NRF", "non refundable"]), "S6": "Non Refundable"}[sup]
    if sup == "S1":
        return f"Free cancellation until {hours}h before check-in"
    if sup == "S2":
        return f"CXL {hours}H"
    if sup == "S3":
        return f"Cancelación gratuita hasta {hours}h antes"
    if sup == "S4":
        return f"Free cancellation until {hours // 24} days before arrival" if hours >= 48 else f"Free cancellation until {hours}h"
    if sup == "S5":
        return rng.choice([f"Free cxl {hours} hrs", f"FREE CANCEL {hours}H", f"refundable ({hours}h)"])
    return f"Free cancellation {hours}h"


def room_base_name(room, sup, rng):
    cls, bed, view, acc = room["class"], room["bed"], room["view"], room["accessible"]
    suite = cls in ("Junior Suite", "Suite", "Villa")
    if sup == "S5":
        sub = rng.choice(["S1", "S2", "S6"])
        name = room_base_name(dict(room, bed=bed if rng.random() > 0.3 else None), sub, rng)
        return name.lower() if rng.random() < 0.25 else name
    if sup == "S1":
        b = f" {bed}" if bed else ""
        n = f"{cls}{b}" if suite else f"{cls}{b} Room"
        if view != "None":
            n += f" – {view} View" if view != "Burj" else " – Burj Khalifa View"
        if acc:
            n += " (Accessible)"
        return n
    if sup == "S2":
        parts = [CLASS_ABBR[cls]]
        if bed:
            parts.append(rng.choice(BED_S2[bed]))
        if VIEW_ABBR[view]:
            parts.append(VIEW_ABBR[view])
        if acc:
            parts.append(rng.choice(["ACC", "HCP"]))
        return " ".join(parts)
    if sup == "S3":
        if rng.random() < 0.3:  # English-mix
            return room_base_name(room, "S1", rng)
        v = VIEW_ES[view]
        if suite:
            n = f"{CLASS_ES[cls]} {v}".strip()
        else:
            b = rng.choice(BED_ES[bed]) if bed else ""
            n = f"Habitación {b} {CLASS_ES[cls]} {v}".strip()
        if acc:
            n += " adaptada"
        return " ".join(n.split())
    if sup == "S4":
        v = rng.choice(VIEW_S4[view])
        ex = rng.choice(S4_EXTRAS)
        b = bed or ""
        n = f"{'Accessible ' if acc else ''}{cls} {v} {b} {ex}"
        return " ".join(n.split())
    if sup == "S6":
        c = {"Deluxe": "Dlx", "Superior": "Sup", "Standard": "Std", "Executive": "Exec",
             "Junior Suite": "Jr Suite"}.get(cls, cls) if rng.random() < 0.7 else cls
        n = f"{c} {bed or ''} {'Rm' if not suite else ''}"
        if view != "None":
            n += f" {view} {'Vw' if rng.random() < 0.6 else 'View'}"
        if acc:
            n += " Accessible"
        return " ".join(n.split())
    return cls


def offer_room_name(base, sup, board, refundable, rng):
    if sup == "S2":
        return f"{base} {board}{'' if refundable else ' NRF'}"
    if sup == "S3":
        return f"{base} – {BOARD_VOCAB['S3'][board]}"
    if sup == "S5" and rng.random() < 0.3:
        return f"{base} {board}"
    return base


SUPPLIER_ID_FMT = {
    "S1": lambda rng: f"DC-{rng.randint(100000, 999999)}",
    "S2": lambda rng: f"GB{rng.randint(1000000, 9999999)}",
    "S3": lambda rng: f"IB-{rng.choice(['DXB', 'AUH', 'SIN', 'BKK', 'DPS'])}-{rng.randint(10000, 99999)}",
    "S4": lambda rng: f"LUX/{rng.randint(1000, 9999)}",
    "S5": lambda rng: f"RS_{rng.randint(1000, 9999)}_{rng.choice('abcdefgh')}",
    "S6": lambda rng: f"NB-{rng.randint(100000, 999999)}",
}
TAKE_MARKUP = {"S1": 1.00, "S2": 0.94, "S3": 0.985, "S4": 1.06, "S5": 0.95, "S6": 0.975}
BOARD_UPLIFT = {"RO": 1.0, "BB": 1.12, "HB": 1.28, "FB": 1.42, "AI": 1.62}
CANCEL_HOURS = {"S1": [48], "S2": [72, 48], "S3": [48], "S4": [168, 72], "S5": [24, 48], "S6": [48, 72]}
OFFER_COMBOS = [(("RO", False), 0.6), (("BB", True), 0.75), (("RO", True), 0.35), (("BB", False), 0.3),
                (("HB", True), 0.18), (("FB", True), 0.06), (("AI", True), 0.08)]


class IdGen:
    def __init__(self):
        self.used = set()

    def make(self, sup, rng):
        while True:
            x = SUPPLIER_ID_FMT[sup](rng)
            if x not in self.used:
                self.used.add(x)
                return x


def make_record(h, sup, rng, ids: IdGen, photos_by_hotel, with_offers: bool, truth, name_override=None):
    st = STYLE[sup]
    lat, lng = h["lat"], h["lng"]
    if rng.random() < st["gross"]:
        ang, dist = rng.random() * 2 * math.pi, rng.uniform(1000, 3000)
        lat, lng = offset_m(lat, lng, dist * math.cos(ang), dist * math.sin(ang))
    lat, lng = offset_m(lat, lng, rng.gauss(0, st["sigma"]), rng.gauss(0, st["sigma"]))
    stars = h["stars"]
    if rng.random() < st["star_err"]:
        stars = max(1, min(5, stars + rng.choice([-1, 1])))
    rid = ids.make(sup, rng)
    rec = {
        "record_id": rid, "supplier": sup,
        "name": name_override or render_name(h, sup, rng),
        "address": None if rng.random() < st["addr_missing"] else render_address(h["address"], sup, rng),
        "phone": None if rng.random() < st["phone_missing"] else render_phone(h["phone"], sup, rng),
        "lat": round(lat, 6), "lng": round(lng, 6), "stars": stars,
        "city": {"S2": CITIES[h["city"]]["code"], "S3": CITIES[h["city"]]["name"].replace("Dubai", "Dubái")}.get(sup, CITIES[h["city"]]["name"]),
        "photos": [],
        "review_score": round(min(10, h["review_score"] + rng.gauss(0, 0.15)), 1) if sup in ("S1", "S3", "S4") else None,
        "platinum": bool(h.get("platinum")) and sup == "S1",
    }
    truth["hotel_of_record"][rid] = h["hotel_id"]
    # photos (showcase only): each supplier carries 55-90% of base images as degraded variants
    for base in photos_by_hotel.get(h["hotel_id"], []):
        if rng.random() < rng.uniform(0.55, 0.9):
            rec["photos"].append({"base": base, "sup": sup})
    # rooms
    rooms_out, offers_out = [], []
    p_room = {"S1": 0.95, "S4": 0.9}.get(sup, 0.75)
    for k, room in enumerate(h["rooms"]):
        forced = h["showcase"] and k < 3
        if not forced and rng.random() > p_room:
            continue
        srid = f"{rid}:{rng.randint(1000, 9999)}"
        while srid in truth["room_of_supplier_room"]:
            srid = f"{rid}:{rng.randint(1000, 9999)}"
        base_name = room_base_name(room, sup, rng)
        rooms_out.append({"supplier_room_id": srid, "record_id": rid, "supplier": sup, "room_name": base_name})
        truth["room_of_supplier_room"][srid] = room["room_id"]
        if not with_offers:
            continue
        combos = [c for c, p in OFFER_COMBOS if rng.random() < p]
        if h["showcase"] and k < 3:
            combos = list(dict.fromkeys([("BB", True), ("RO", False)] + combos))
        if not combos:
            combos = [("RO", False)]
        combos = combos[:4]
        for board, refundable in combos:
            if board == "AI" and h["neighbourhood"] not in ("Palm Jumeirah", "Jumeirah", "JBR"):
                board = "HB"
            hours = rng.choice(CANCEL_HOURS[sup])
            price = (h["base_price"] * room["price_factor"] * TAKE_MARKUP[sup] * BOARD_UPLIFT[board]
                     * (1.08 if refundable else 1.0) * rng.uniform(0.95, 1.05))
            oid = f"O{len(truth['room_of_offer']) + 1:07d}"
            payment = "pay_later" if (refundable and sup in ("S1", "S4", "S6") and rng.random() < 0.5) else "prepay"
            offers_out.append({
                "offer_id": oid, "supplier": sup, "record_id": rid, "supplier_room_id": srid,
                "room_name": offer_room_name(base_name, sup, board, refundable, rng),
                "board_raw": board_raw(sup, board, rng),
                "cancellation_raw": cancel_raw(sup, refundable, hours, rng),
                "payment": payment, "price_inr": int(round(price, -1)), "currency": "INR",
                "rate_code": f"{sup}|{hashlib.md5(oid.encode()).hexdigest()[:8].upper()}|{board}{'' if refundable else '|NRF'}",
                "occupancy": 2, "nights": 1,
            })
            truth["room_of_offer"][oid] = room["room_id"]
            truth["offer_terms"][oid] = {"board": board, "refundable": refundable, "free_cancel_hours": hours if refundable else 0}
    return rec, rooms_out, offers_out


# =============================================================================== photos
def gen_photos(hotels):
    rng = R("photos")
    config.IMG_BASE_DIR.mkdir(parents=True, exist_ok=True)
    config.IMG_VAR_DIR.mkdir(parents=True, exist_ok=True)
    by_hotel = {}
    for h in hotels:
        if not h["showcase"]:
            continue
        n = rng.randint(12, 16)
        lst = []
        for k in range(n):
            tag = ph.TAGS[k % len(ph.TAGS)]
            fname = f"{h['hotel_id']}_{k:02d}_{tag}.jpg"
            path = config.IMG_BASE_DIR / fname
            if not path.exists():
                ph.save_jpeg(ph.make_base_image(f"{SEED}:{h['hotel_id']}:{k}", tag), path, 88)
            lst.append({"file": fname, "tag": tag})
        by_hotel[h["hotel_id"]] = lst
        h["photos"] = [f"/img/base/{x['file']}" for x in lst]
    return by_hotel


def materialize_variants(records):
    """Write supplier-degraded variants for photos referenced by records."""
    from PIL import Image
    cache = {}
    for rec in records:
        out = []
        for i, p in enumerate(rec["photos"]):
            base = p["base"]
            rng = random.Random(f"{SEED}:var:{rec['record_id']}:{base['file']}")
            vname = f"{rec['supplier']}_{rec['record_id'].replace('/', '_')}_{i:02d}_{base['tag']}.jpg"
            vpath = config.IMG_VAR_DIR / vname
            if base["file"] not in cache:
                cache[base["file"]] = Image.open(config.IMG_BASE_DIR / base["file"]).convert("RGB")
            img, q = ph.make_variant(cache[base["file"]], rng, config.SUPPLIERS[rec["supplier"]]["name"])
            if not vpath.exists():
                ph.save_jpeg(img, vpath, q)
            out.append({"url": f"/img/var/{vname}", "w": img.width, "h": img.height, "base": base["file"]})
        rec["photos"] = out


# =============================================================================== activities
def gen_activities(truth):
    rng = R("activities")
    listings = []
    styles = {"S1": 0, "S3": 1, "S5": 2}
    meal_word = {"desert_safari": ("BBQ Dinner", "cena barbacoa", "BBQ DINNER"),
                 "desert_safari_morning": ("Breakfast", "desayuno", "BREAKFAST")}
    for p in ACTIVITIES:
        for sup, si in styles.items():
            if rng.random() > 0.9:
                continue
            chosen = [o for o in p["options"] if rng.random() < 0.75] or [p["options"][0]]
            for o in chosen:
                base = ACTIVITY_TITLES[p["id"]][si]
                mw = meal_word.get(p["attraction"], ("Dinner", "cena", "DINNER"))
                parts = []
                slot = o.get("slot")
                if si == 0:
                    if o.get("private"):
                        base = "Private " + base
                    if slot in ("prime", "non-prime", "sunset"):
                        parts.append({"prime": "– Prime Time", "non-prime": "– Non-Prime Hours", "sunset": "– Sunset Slot"}[slot])
                    if "meal" in o:
                        parts.append(f"with {mw[0]}" if o["meal"] else f"(No {mw[0].split()[-1]})")
                    if o.get("quad"):
                        parts.append("+ Quad Bike")
                    if o.get("edge"):
                        parts.append("+ Sky Edge Walk")
                    if o.get("transfer"):
                        parts.append("with Hotel Transfer")
                    if o.get("language") == "ES":
                        parts.append("(Spanish-speaking guide)")
                elif si == 1:
                    if o.get("private"):
                        parts.append("privado")
                    if slot in ("prime", "non-prime", "sunset"):
                        parts.append({"prime": "– horario prime", "non-prime": "– horario no prime", "sunset": "– atardecer"}[slot])
                    if "meal" in o:
                        parts.append(f"con {mw[1]}" if o["meal"] else f"sin {mw[1].split()[0]}")
                    if o.get("quad"):
                        parts.append("+ quad")
                    if o.get("edge"):
                        parts.append("+ Sky Edge")
                    if o.get("transfer"):
                        parts.append("+ traslado")
                    if o.get("language") == "ES":
                        parts.append("(guía en español)")
                    elif o.get("language") == "EN":
                        parts.append("(guía en inglés)")
                else:
                    if o.get("private"):
                        parts.append("PVT")
                    if slot in ("prime", "non-prime", "sunset"):
                        parts.append({"prime": "PRIME", "non-prime": "NON PRIME", "sunset": "SUNSET"}[slot])
                    if "meal" in o:
                        parts.append(f"+{mw[2]}" if o["meal"] else f"NO {mw[2].split()[-1]}")
                    if o.get("quad"):
                        parts.append("+QUAD")
                    if o.get("edge"):
                        parts.append("+EDGE")
                    if o.get("transfer"):
                        parts.append("W/ TRF")
                    if o.get("language") == "ES":
                        parts.append("ES GUIDE")
                title = " ".join([base] + parts)
                dur = p["duration"]
                if si == 0:
                    dtext = f"{dur // 60}h" + (f" {dur % 60}m" if dur % 60 else "") if dur >= 60 else f"{dur} min"
                elif si == 1:
                    dtext = f"{dur} minutos"
                else:
                    dtext = "half day" if 200 <= dur <= 300 else "full day" if dur >= 480 else f"{round(dur / 60, 1)} hrs"
                lang = o.get("language", "EN")
                lang_txt = {0: {"EN": "English", "ES": "Spanish"}, 1: {"EN": "Inglés", "ES": "Español"}, 2: {"EN": "EN", "ES": "ES"}}[si][lang]
                mk = {"S1": 1.0, "S3": 0.98, "S5": 0.94}[sup] * rng.uniform(0.96, 1.04)
                add = (1.25 if o.get("slot") == "prime" else 1.0) * (1.0 + 0.18 * bool(o.get("transfer"))) \
                    * (1.0 + 0.3 * bool(o.get("meal"))) * (2.6 if o.get("private") else 1.0) * (1.0 + 0.4 * bool(o.get("quad")))
                adult = int(round(p["price"] * mk * add, -1))
                lid = f"{sup}-A{len(listings) + 1:04d}"
                listings.append({
                    "listing_id": lid, "supplier": sup, "title": title, "duration": dtext, "language": lang_txt,
                    "meeting_point": p["meeting"] if not o.get("transfer") else ("Hotel pickup" if si == 0 else "Recogida en hotel" if si == 1 else "HTL PICKUP"),
                    "inclusions": ", ".join(x for x in [
                        "Entry ticket" if si != 1 else "Entrada",
                        ("Hotel transfer" if si != 1 else "Traslado") if o.get("transfer") else None,
                        (mw[0] if si != 1 else mw[1]) if o.get("meal") else None] if x),
                    "prices": {"adult": adult, "child": int(round(adult * 0.75, -1)), "infant": 0},
                    "city": "Dubai",
                })
                truth["activity_of_listing"][lid] = {"product_id": p["id"], "option": {k: v for k, v in o.items()}}
    return listings


# =============================================================================== labels
def plausible_pairs(records, splits, truth, hmap, split):
    """Every plausible cross-supplier pair between hotels of one split: same city and <=1.2 km apart,
    or same brand, or similar names (token-set >= 60), plus all true pairs. Mirrors what blocking proposes."""
    from rapidfuzz import fuzz, process
    by_city = defaultdict(list)
    for r in records:
        h = hmap[truth["hotel_of_record"][r["record_id"]]]
        if splits[h["hotel_id"]] == split:
            by_city[h["city"]].append(r)
    out = []
    for city, recs in by_city.items():
        names = [r["name"].lower() for r in recs]
        sim = process.cdist(names, names, scorer=fuzz.token_set_ratio, workers=1)
        lat = np.array([r["lat"] for r in recs]); lng = np.array([r["lng"] for r in recs])
        hid = [truth["hotel_of_record"][r["record_id"]] for r in recs]
        brand = [hmap[h]["brand"] for h in hid]
        for i in range(len(recs)):
            d = haversine_m(lat[i], lng[i], lat, lng)
            for j in range(i + 1, len(recs)):
                if recs[i]["supplier"] == recs[j]["supplier"]:
                    continue
                y = int(hid[i] == hid[j])
                same_brand = bool(brand[i]) and brand[i] == brand[j]
                if y or d[j] <= 1200 or same_brand or sim[i, j] >= 60:
                    out.append((recs[i]["record_id"], recs[j]["record_id"], y, float(sim[i, j]), float(d[j]), same_brand))
    return out


def gen_labels(hotels, records, splits, truth):
    rng = R("labels")
    hmap = {h["hotel_id"]: h for h in hotels}
    labels = []
    # train: 800 = 600 LLM-teacher labelled (3% noise injected) + 200 human gold, ~45% positive.
    # Negatives are drawn from the plausible pool, weighted toward look-alikes (similar name / same brand / close).
    pool = plausible_pairs(records, splits, truth, hmap, "train")
    pos = [t for t in pool if t[2] == 1]
    neg = [(a, b, (0.15 + (sim / 100) ** 4 + (0.6 if sb else 0) + 0.4 * math.exp(-d / 300)))
           for a, b, y, sim, d, sb in pool if y == 0]
    tr_pos = rng.sample(pos, min(len(pos), int(N_TRAIN_LABELS * 0.45)))
    tr_neg = _weighted_sample(rng, neg, N_TRAIN_LABELS - len(tr_pos))
    train = [(t[0], t[1], 1) for t in tr_pos] + [(t[0], t[1], 0) for t in tr_neg]
    rng.shuffle(train)
    for k, (a, b, y) in enumerate(train):
        src = "teacher" if k < 600 else "gold"
        yy = (1 - y) if (src == "teacher" and rng.random() < 0.03) else y
        labels.append({"a": a, "b": b, "label": yy, "split": "train", "source": src})
    # calibration: gold "mapping audit" of every plausible pair between calibration hotels, so the audit is
    # exchangeable with the blocked candidates the system will see (a Learn-then-Test requirement).
    for a, b, y, *_ in plausible_pairs(records, splits, truth, hmap, "cal"):
        labels.append({"a": a, "b": b, "label": y, "split": "cal", "source": "gold_audit"})
    return labels


def _weighted_sample(rng, items, k):
    if k >= len(items):
        return list(items)
    keys = [(rng.random() ** (1.0 / max(1e-6, it[2])), it) for it in items]
    keys.sort(key=lambda t: -t[0])
    return [it for _, it in keys[:k]]


# =============================================================================== logs
def gen_relevance(hotels, offers, truth):
    """True (hidden) graded relevance per persona x Dubai hotel."""
    rng = R("relevance")
    dubai = [h for h in hotels if h["city"] == "dubai"]
    rel = {}
    for p in PERSONAS:
        util = {}
        for h in dubai:
            has_suite = any(r["class"] in ("Junior Suite", "Suite", "Villa") for r in h["rooms"])
            price = h["base_price"]
            u = (-0.9 * abs(h["stars"] - p["stars"]) + 1.3 * (h["neighbourhood"] in p["areas"])
                 - p["price_sens"] * max(0.0, math.log(price / p["budget"]))
                 - 0.25 * p["price_sens"] * math.log(price / 5000)
                 + p["review"] * (h["review_score"] - 8.0) + p["suite"] * has_suite
                 + 0.3 * p["refundable"] + rng.gauss(0, 0.35))
            util[h["hotel_id"]] = u
        vals = np.array(list(util.values()))
        q = np.quantile(vals, [0.45, 0.72, 0.88, 0.96])
        rel[p["id"]] = {hid: int(np.searchsorted(q, u)) for hid, u in util.items()}
    truth["relevance"] = rel
    return rel


def gen_search_logs(hotels, rel, listing_ref):
    rng = np.random.default_rng(SEED + 7)
    dubai = [h for h in hotels if h["city"] == "dubai"]
    ids = np.array([h["hotel_id"] for h in dubai])
    pop = np.array([h["popularity"] * (1 + 0.15 * h["stars"]) for h in dubai])
    nb = np.array([h["neighbourhood"] for h in dubai])
    pweights = np.array([0.24, 0.16, 0.18, 0.16, 0.14, 0.12])
    click_p = np.array([0.04, 0.12, 0.3, 0.55, 0.8])
    rows = []
    for s in range(20000):
        pi = rng.choice(len(PERSONAS), p=pweights)
        p = PERSONAS[pi]
        in_area = np.where(np.isin(nb, p["areas"]))[0]
        others = np.where(~np.isin(nb, p["areas"]))[0]
        k_in = min(len(in_area), 8)
        cand = np.concatenate([rng.choice(in_area, k_in, replace=False), rng.choice(others, 20 - k_in, replace=False)])
        randomized = rng.random() < 0.05
        if randomized:
            order = rng.permutation(cand)
        else:
            score = np.log(pop[cand]) + rng.normal(0, 0.6, len(cand))
            order = cand[np.argsort(-score)]
        exam = 1.0 / np.arange(1, 21) ** 0.9
        for r, idx in enumerate(order):
            g = rel[p["id"]][ids[idx]]
            c = rng.random() < exam[r] * click_p[g]
            b = c and rng.random() < 0.18 + 0.1 * g
            rows.append((s, p["id"], randomized, r + 1, listing_ref[ids[idx]], int(c), int(b)))
    return pd.DataFrame(rows, columns=["session_id", "persona", "randomized", "position", "listing_id", "click", "book"])


def gen_booking_history():
    rng = np.random.default_rng(SEED + 11)
    rows = []
    for sup in SUPPLIERS:
        prof = config.SUPPLIERS[sup]["profile"]
        for day in range(30):
            n = int(rng.integers(90, 150))
            conf = rng.random(n) < prof["confirm"]
            jump = (rng.random(n) < prof["price_jump"]) & conf
            lat = rng.lognormal(math.log(prof["latency"]), 0.35, n)
            for i in range(n):
                rows.append((day, sup, "dubai", bool(conf[i]), bool(jump[i]), round(float(lat[i]), 3)))
    return pd.DataFrame(rows, columns=["day", "supplier", "city", "confirmed", "price_jump", "latency_s"])


# =============================================================================== main
def generate(world_kind: str | None = None):
    t0 = time.time()
    world_kind = world_kind or config.WORLD
    config.ensure_dirs()
    truth = {"hotel_of_record": {}, "room_of_supplier_room": {}, "room_of_offer": {}, "offer_terms": {},
             "mapping_errors": [], "intra_dups": [], "activity_of_listing": {}, "world": world_kind}
    hotels = gen_canonical(world_kind)
    photos_by_hotel = gen_photos(hotels)
    print(f"  canonical hotels: {len(hotels)} (dubai {sum(h['city'] == 'dubai' for h in hotels)})  [{time.time() - t0:.1f}s]")

    rng = R("coverage")
    ids = IdGen()
    records, rooms_raw, offers_raw = [], [], []
    for h in hotels:
        sups = []
        for s in SUPPLIERS:
            p = COVERAGE[s]
            if s == "S4" and h["stars"] < 4:
                continue
            if rng.random() < p:
                sups.append(s)
        if h["showcase"]:
            sups = SUPPLIERS[:] if h["stars"] >= 4 else [s for s in SUPPLIERS if s != "S4"]
        while len(sups) < 2:
            extra = rng.choice([s for s in SUPPLIERS if s not in sups and not (s == "S4" and h["stars"] < 4)])
            sups.append(extra)
        sups = sorted(sups)[:5]
        for s in sups:
            rec, rr, oo = make_record(h, s, R(f"rec:{h['hotel_id']}:{s}"), ids, photos_by_hotel, h["city"] == "dubai", truth)
            records.append(rec)
            rooms_raw += rr
            offers_raw += oo
            # intra-supplier duplicates (MAP_OVERLAP style)
            if s in ("S2", "S5") and rng.random() < 0.02 and not h["showcase"]:
                rec2, rr2, oo2 = make_record(h, s, R(f"dup:{h['hotel_id']}:{s}"), ids, photos_by_hotel, h["city"] == "dubai", truth)
                records.append(rec2)
                rooms_raw += rr2
                offers_raw += oo2
                truth["intra_dups"].append([rec["record_id"], rec2["record_id"]])

    # raw-feed mapping errors: offer attached to the wrong supplier room
    rng_m = R("maperr")
    rooms_by_rec = defaultdict(list)
    for r in rooms_raw:
        rooms_by_rec[r["record_id"]].append(r["supplier_room_id"])
    for o in offers_raw:
        sib = rooms_by_rec[o["record_id"]]
        if len(sib) > 1 and rng_m.random() < MAPPING_ERROR_RATE:
            wrong = rng_m.choice([x for x in sib if x != o["supplier_room_id"]])
            o["supplier_room_id"] = wrong
            truth["mapping_errors"].append(o["offer_id"])
    print(f"  supplier records: {len(records)}  rooms: {len(rooms_raw)}  offers: {len(offers_raw)}  "
          f"intra-dups: {len(truth['intra_dups'])}  mapping errors: {len(truth['mapping_errors'])}  [{time.time() - t0:.1f}s]")

    # NovaBeds (S6): ~30% of existing hotels + new hotels only it carries
    rng6 = R("novabeds")
    nova_records, nova_rooms, nova_offers = [], [], []
    new_hotels = []
    extra_used = {h["name"] for h in hotels}
    n_new = max(8, int(0.03 * len(hotels)))
    hid_next = len(hotels)
    for k in range(n_new):
        city = "dubai" if k < max(4, n_new // 6) or world_kind != "large" else rng6.choice(list(CITY_SIZES_LARGE))
        nb, (la0, la1, lo0, lo1) = rng6.choice(list(CITIES[city]["neighbourhoods"].items()))
        name, brand = gen_name(rng6, city, nb, extra_used)
        hid_next += 1
        stars = brand_stars(rng6, brand)
        h = {"hotel_id": f"H{hid_next:04d}", "name": name, "brand": brand, "chain": BRANDS[brand][0] if brand else None,
             "stars": stars, "tier": tier_of(brand, stars), "lat": round(rng6.uniform(la0, la1), 6),
             "lng": round(rng6.uniform(lo0, lo1), 6), "address": f"{rng6.randint(1, 300)} {nb} Road, {nb}, {CITIES[city]['name']}",
             "phone": make_phone(rng6, city), "city": city, "neighbourhood": nb, "amenities": AMENITIES[stars][:],
             "showcase": False, "review_score": 8.0, "popularity": 1.0, "platinum": False,
             "base_price": STAR_BASE_PRICE[stars], "new_in_s6": True}
        h["rooms"] = gen_rooms(rng6, h)
        new_hotels.append(h)
    for h in hotels + new_hotels:
        if h.get("new_in_s6") or rng6.random() < 0.3:
            rec, rr, oo = make_record(h, "S6", R(f"rec:{h['hotel_id']}:S6"), ids, photos_by_hotel, h["city"] == "dubai", truth)
            nova_records.append(rec)
            nova_rooms += rr
            nova_offers += oo
    print(f"  NovaBeds feed: {len(nova_records)} hotels ({len(new_hotels)} brand-new), {len(nova_rooms)} rooms")

    materialize_variants(records + nova_records)
    print(f"  photo variants written  [{time.time() - t0:.1f}s]")

    # splits by canonical cluster
    rng_s = R("splits")
    all_h = hotels + new_hotels
    splits = {}
    for h in all_h:
        x = rng_s.random()
        splits[h["hotel_id"]] = "train" if x < 0.5 else ("cal" if x < 0.75 else "test")
    truth["splits"] = splits
    labels = gen_labels(hotels, records, splits, truth)
    print(f"  labels: train {sum(l['split'] == 'train' for l in labels)}  cal {sum(l['split'] == 'cal' for l in labels)}")

    activities = gen_activities(truth)
    rel = gen_relevance(hotels, offers_raw, truth)
    # search logs reference the listing id the platform showed (a supplier record id), never canonical ids
    prio = {"S1": 0, "S4": 1, "S3": 2, "S2": 3, "S5": 4}
    listing_ref = {}
    for r in records:
        hid = truth["hotel_of_record"][r["record_id"]]
        cur = listing_ref.get(hid)
        if cur is None or prio[r["supplier"]] < prio[cur[0]]:
            listing_ref[hid] = (r["supplier"], r["record_id"])
    logs = gen_search_logs(hotels, rel, {k: v[1] for k, v in listing_ref.items()})
    hist = gen_booking_history()

    truth["canonical_hotels"] = all_h
    truth["canonical_activities"] = ACTIVITIES

    write_json("hotels_raw.json", records)
    write_json("rooms_raw.json", rooms_raw)
    write_json("offers_raw.json", offers_raw)
    write_json("activities_raw.json", activities)
    write_json("truth.json", truth)
    write_json("labels_sample.json", labels)
    write_json("novabeds_feed.json", {"supplier": "S6", "name": "NovaBeds", "hotels": nova_records,
                                      "rooms": nova_rooms, "offers": nova_offers})
    write_json("personas.json", PERSONAS)
    logs.to_parquet(config.WORLD_DIR / "search_logs.parquet", index=False)
    hist.to_parquet(config.WORLD_DIR / "booking_history.parquet", index=False)
    print(f"World '{world_kind}' written to {config.WORLD_DIR}  [{time.time() - t0:.1f}s]")


def print_sample():
    recs = orjson.loads((config.WORLD_DIR / "hotels_raw.json").read_bytes())
    truth = orjson.loads((config.WORLD_DIR / "truth.json").read_bytes())
    rooms = orjson.loads((config.WORLD_DIR / "rooms_raw.json").read_bytes())
    offers = orjson.loads((config.WORLD_DIR / "offers_raw.json").read_bytes())
    canon = {h["hotel_id"]: h for h in truth["canonical_hotels"]}
    target = next(h for h in canon.values() if h["name"] == "Atlantis The Palm")
    print(f"\n=== Canonical: {target['name']} ({target['hotel_id']}) {target['phone']} {target['address']}")
    for r in recs:
        if truth["hotel_of_record"][r["record_id"]] == target["hotel_id"]:
            print(f"  {r['supplier']} {r['record_id']:<16} {r['name']:<48} {str(r['phone']):<18} {r['stars']}★ "
                  f"({r['lat']:.4f},{r['lng']:.4f}) photos={len(r['photos'])}")
            for rm in [x for x in rooms if x["record_id"] == r["record_id"]][:3]:
                print(f"      room: {rm['room_name']}")
            for o in [x for x in offers if x["record_id"] == r["record_id"]][:3]:
                print(f"      offer: {o['room_name']:<44} {o['board_raw']:<22} {o['cancellation_raw']:<40} ₹{o['price_inr']}")
    print("\n=== Random noisy names per supplier")
    rng = random.Random(1)
    for s in ["S1", "S2", "S3", "S4", "S5"]:
        rs = [r for r in recs if r["supplier"] == s]
        for r in rng.sample(rs, 4):
            print(f"  {s} {r['name']:<55} <- {canon[truth['hotel_of_record'][r['record_id']]]['name']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--world", default=None)
    a = ap.parse_args()
    if a.sample:
        print_sample()
    else:
        generate(a.world)
        print_sample()
