"""Normalization: hotel names, phones, addresses, room names (EN/ES/abbrev), offer terms, activities."""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import orjson

from app import config
from data.tables import BRANDS

# ------------------------------------------------------------------ text helpers
def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


_PUNCT = re.compile(r"[^a-z0-9& ]+")

NAME_ABBR = {
    "htl": "hotel", "dxb": "dubai", "auh": "abu dhabi", "sin": "singapore", "bkk": "bangkok", "dps": "bali",
    "apts": "apartments", "apt": "apartments", "rst": "resort", "bch": "beach", "stes": "suites", "intl": "international",
    "jum": "jumeirah", "dwtn": "downtown", "ctr": "centre", "center": "centre", "cty": "city", "res": "residence",
    "jbr": "jumeirah beach residence", "jumeira": "jumeirah", "diera": "deira", "asalam": "a salam", "a'salam": "a salam",
    "saadiyaat": "saadiyat", "sukhumwit": "sukhumvit", "bus": "business", "mövenpick": "movenpick", "&": "and",
    "y": "and", "st": "street", "rd": "road", "blvd": "boulevard", "dubái": "dubai",
}
CITY_TOKENS = {"dubai", "abu", "dhabi", "singapore", "bangkok", "bali", "uae"}
GENERIC = {"hotel", "the", "resort", "spa", "and", "by", "a", "an", "of", "at", "luxury", "collection",
           "suites", "hotels", "apartments", "&", "-", "residence", "residences", "beach", "inn", "boutique"}
MARKETING = [re.compile(p) for p in [
    r",\s*an? [a-z0-9 &'.-]+ hotel$", r"\s*[–-]\s*luxury collection$", r"\s+luxury collection$",
]]

_brand_norm = sorted(((fold(b).replace("&", " and ").replace("-", " "), b) for b in BRANDS), key=lambda t: -len(t[0]))
_brand_norm = [(" ".join(n.split()), b) for n, b in _brand_norm]


def clean_name(name: str) -> str:
    s = fold(name).strip()
    for pat in MARKETING:
        s = pat.sub("", s)
    s = s.replace("–", " ").replace("-", " ").replace("'", "").replace(",", " ")
    s = s.replace("&", " & ")
    s = _PUNCT.sub(" ", s)
    toks = []
    for t in s.split():
        e = NAME_ABBR.get(t, t)
        toks.extend(e.split())
    return " ".join(toks)


def extract_brand(name_norm: str) -> str | None:
    """Brand = earliest-positioned brand mention (exact, or typo-tolerant for long brand names).
    Earliest wins so 'Movenpick ... Jumeirah Beach' is Movenpick, not Jumeirah."""
    from rapidfuzz import fuzz
    toks = name_norm.split()
    if toks and toks[0] == "w":
        return "W"
    best = None  # (pos, -len, -score, brand)
    for n, b in _brand_norm:
        if b == "W":
            continue
        bt = n.split()
        k = len(bt)
        for i in range(0, len(toks) - k + 1):
            win = toks[i:i + k]
            if win == bt:
                sc = 100.0
            elif len(n) >= 6:
                sc = fuzz.ratio(" ".join(win), n)
                if sc < 86:
                    continue
            else:
                continue
            cand = (i, -len(n), -sc, b)
            if best is None or cand < best:
                best = cand
            break
    return best[3] if best else None


def strip_brand_tokens(toks: list[str], brand: str) -> list[str]:
    from rapidfuzz import fuzz
    bt = fold(brand).replace("&", " and ").replace("-", " ").split()
    k = len(bt)
    for i in range(len(toks) - k + 1):
        if toks[i:i + k] == bt or fuzz.ratio(" ".join(toks[i:i + k]), " ".join(bt)) >= 86:
            return toks[:i] + toks[i + k:]
    return toks


def core_tokens(name_norm: str, brand: str | None) -> list[str]:
    toks = name_norm.split()
    if brand:
        toks = strip_brand_tokens(toks, brand)
    return [t for t in toks if t not in CITY_TOKENS and t not in GENERIC]


CITY_ALIASES = {"dubai": "dubai", "dxb": "dubai", "dubái": "dubai", "abu dhabi": "abu_dhabi", "auh": "abu_dhabi",
                "abu dabi": "abu_dhabi", "singapore": "singapore", "sin": "singapore", "singapur": "singapore",
                "bangkok": "bangkok", "bkk": "bangkok", "bali": "bali", "dps": "bali"}
COUNTRY_CODE = {"dubai": "971", "abu_dhabi": "971", "singapore": "65", "bangkok": "66", "bali": "62"}


def canon_city(raw: str | None) -> str:
    return CITY_ALIASES.get(fold(raw or "").strip(), fold(raw or "").strip().replace(" ", "_"))


def normalize_phone(raw: str | None, city: str) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    cc = COUNTRY_CODE.get(city, "")
    if raw.strip().startswith("+"):
        return "+" + digits
    if digits.startswith("00"):
        return "+" + digits[2:]
    if digits.startswith("0"):
        return f"+{cc}{digits[1:]}"
    if cc and digits.startswith(cc) and len(digits) > 9:
        return "+" + digits
    return f"+{cc}{digits}"


def address_tokens(addr: str | None) -> set[str]:
    if not addr:
        return set()
    s = _PUNCT.sub(" ", fold(addr).replace(",", " "))
    out = set()
    for t in s.split():
        t = NAME_ABBR.get(t, t)
        if t not in CITY_TOKENS and len(t) > 1:
            out.update(t.split())
    out.discard("carretera")
    return out


def normalize_hotel(rec: dict) -> dict:
    city = canon_city(rec.get("city"))
    nn = clean_name(rec["name"])
    brand = extract_brand(nn)
    core = core_tokens(nn, brand)
    match_name = " ".join(([fold(brand)] if brand else []) + core)
    return {
        "match_name": match_name,
        "record_id": rec["record_id"], "supplier": rec["supplier"], "raw_name": rec["name"],
        "name_norm": nn, "brand": brand, "core_name": " ".join(core), "core_tokens": core,
        "city": city, "lat": rec.get("lat"), "lng": rec.get("lng"), "stars": rec.get("stars"),
        "phone": normalize_phone(rec.get("phone"), city), "phone_raw": rec.get("phone"),
        "address": rec.get("address"), "addr_tokens": address_tokens(rec.get("address")),
        "photos": rec.get("photos", []),
        "missing": int(rec.get("phone") is None) + int(rec.get("address") is None),
    }


# ------------------------------------------------------------------ room parser
CLASS_PHRASES = {
    "junior suite": "Junior Suite", "jr suite": "Junior Suite", "jr ste": "Junior Suite", "jr. suite": "Junior Suite",
    "junior ste": "Junior Suite", "suite": "Suite", "ste": "Suite", "villa": "Villa",
    "deluxe": "Deluxe", "dlx": "Deluxe", "de luxe": "Deluxe", "superior": "Superior", "sup": "Superior",
    "standard": "Standard", "std": "Standard", "estandar": "Standard", "classic": "Standard",
    "premier": "Premier", "prem": "Premier", "premium": "Premier", "executive": "Executive", "exec": "Executive",
    "ejecutiva": "Executive", "ejecutivo": "Executive",
}
BED_PHRASES = {
    "cama king": "King", "king": "King", "kg": "King", "k": "King", "queen": "Queen", "cama queen": "Queen",
    "qn": "Queen", "q": "Queen", "double": "Double", "dbl": "Double", "doble": "Double",
    "twin": "Twin", "twn": "Twin", "dos camas": "Twin", "2 camas": "Twin", "two beds": "Twin",
}
VIEW_PHRASES = {
    "sea view": "Sea", "ocean view": "Sea", "vista mar": "Sea", "vista al mar": "Sea", "sv": "Sea", "sea vw": "Sea",
    "city view": "City", "skyline view": "City", "vista ciudad": "City", "cv": "City", "city vw": "City",
    "burj khalifa view": "Burj", "burj view": "Burj", "fountain view": "Burj", "vista burj khalifa": "Burj",
    "vista burj": "Burj", "bv": "Burj", "burj vw": "Burj",
    "marina view": "Marina", "vista marina": "Marina", "vista al puerto": "Marina", "mv": "Marina", "marina vw": "Marina",
    "garden view": "Garden", "vista jardin": "Garden", "gv": "Garden", "garden vw": "Garden",
    "pool view": "Pool", "vista piscina": "Pool", "pv": "Pool", "pool vw": "Pool",
}
BOARD_PHRASES = {
    "bed and breakfast": "BB", "bed & breakfast": "BB", "b&b": "BB", "b and b": "BB", "bb": "BB", "ad": "BB",
    "breakfast included": "BB", "breakfast": "BB", "desayuno": "BB", "alojamiento y desayuno": "BB",
    "room only": "RO", "ro": "RO", "sa": "RO", "solo alojamiento": "RO", "no meals": "RO",
    "half board": "HB", "hb": "HB", "mp": "HB", "media pension": "HB",
    "full board": "FB", "fb": "FB", "pc": "FB", "pension completa": "FB",
    "all inclusive": "AI", "all-inclusive": "AI", "all inc": "AI", "ai": "AI", "ti": "AI", "todo incluido": "AI",
}
REFUND_PHRASES = {"non refundable": False, "non-refundable": False, "nonrefundable": False, "non ref": False,
                  "nrf": False, "no reembolsable": False, "refundable": True, "reembolsable": True}
ACCESS_PHRASES = {"accessible": True, "acc": True, "hcp": True, "adaptada": True, "wheelchair": True,
                  "accesible": True}
SMOKE_PHRASES = {"non smoking": False, "nonsmoking": False, "no fumadores": False, "smoking": True}
EXTRA_PHRASES = {"club access": "club access", "lounge access": "lounge access", "balcony": "balcony",
                 "club": "club access", "terrace": "terrace", "connecting": "connecting", "family": "family",
                 "ocean front": "ocean front", "high floor": "high floor", "panoramic": "panoramic"}
NOISE = {"room", "rm", "habitacion", "with", "con", "view", "vw", "vista", "the", "and", "de", "cama", "a", "y",
         "bed", "beds", "one", "bedroom", "1", "with", "al", "en"}


@lru_cache(maxsize=1)
def learned_dictionary() -> dict:
    p = config.CACHE_DIR / "dictionary_learned.json"
    if p.exists():
        try:
            return orjson.loads(p.read_bytes())
        except Exception:
            return {}
    return {}


def _room_tokens(text: str) -> str:
    s = fold(text)
    s = s.replace("–", " ").replace("—", " ").replace("(", " ").replace(")", " ").replace("/", " ").replace(",", " ")
    s = re.sub(r"\s-\s|\s-|-\s", " ", s)
    s = s.replace("+", " ")
    return " " + " ".join(s.split()) + " "


def _take(s: str, phrases: dict):
    """Find longest phrase matches; returns (values in order, remaining string)."""
    found = []
    for ph in sorted(phrases, key=len, reverse=True):
        pat = f" {ph} "
        while pat in s:
            idx = s.index(pat)
            found.append((idx, phrases[ph]))
            s = s[:idx] + " " + s[idx + len(pat):]
            s = " " + s.strip() + " "
    found.sort()
    return [v for _, v in found], s


def parse_room(text: str) -> dict:
    s = _room_tokens(text)
    learned = learned_dictionary()
    out = {"class": None, "bed": None, "bed_count": None, "view": None, "occupancy": None, "accessible": False,
           "smoking": None, "extras": [], "board": None, "refundable": None, "needs_llm_parse": False}
    refs, s = _take(s, REFUND_PHRASES)
    if refs:
        out["refundable"] = refs[0]
    boards, s = _take(s, BOARD_PHRASES)
    if boards:
        out["board"] = boards[-1]
    views, s = _take(s, VIEW_PHRASES)
    if views:
        out["view"] = views[0]
    classes, s = _take(s, CLASS_PHRASES)
    if classes:
        # "Junior Suite" wins over generic, otherwise first
        out["class"] = "Junior Suite" if "Junior Suite" in classes else ("Villa" if "Villa" in classes else classes[0])
    beds, s = _take(s, BED_PHRASES)
    if beds:
        if "King" in beds:
            out["bed"] = "King"
        elif "Queen" in beds:
            out["bed"] = "Queen"
        elif "Twin" in beds:
            out["bed"] = "Twin"
        else:
            out["bed"] = "Double"
        out["bed_count"] = 2 if out["bed"] == "Twin" else 1
    acc, s = _take(s, ACCESS_PHRASES)
    out["accessible"] = bool(acc)
    smoke, s = _take(s, SMOKE_PHRASES)
    if smoke:
        out["smoking"] = smoke[0]
    extras, s = _take(s, EXTRA_PHRASES)
    out["extras"] = sorted(set(extras))
    unknown = [t for t in s.split() if t not in NOISE and not t.isdigit()]
    still = []
    for t in unknown:
        if t in learned:
            ent = learned[t]
            f, v = ent.get("field"), ent.get("value")
            if f in ("class", "bed", "view", "board") and not out.get(f):
                out[f] = v
                continue
            if f == "extra":
                out["extras"].append(v)
                continue
        still.append(t)
    out["extras"] += [t for t in still]
    out["unknown_tokens"] = still
    out["needs_llm_parse"] = len(still) > 2
    if out["class"] is None and out["bed"] is not None:
        out["class"] = "Standard" if not still else None
    cls = out["class"]
    out["occupancy"] = 4 if cls == "Villa" else (3 if cls in ("Suite", "Junior Suite") else 2)
    return out


def room_identity(parsed: dict) -> dict:
    """Only these attributes decide room identity. Board and refundability never do."""
    return {k: parsed.get(k) for k in ("class", "bed", "view", "occupancy", "accessible")}


def canonical_room_name(ident: dict) -> str:
    parts = [ident.get("class") or "Room"]
    if ident.get("bed"):
        parts.append(ident["bed"])
    name = " ".join(parts)
    if ident.get("view") and ident["view"] != "None":
        name += f" · {ident['view']} View" if ident["view"] != "Burj" else " · Burj View"
    if ident.get("accessible"):
        name += " · Accessible"
    return name


# ------------------------------------------------------------------ offer terms
def parse_board(raw: str | None) -> str | None:
    if not raw:
        return None
    vals, _ = _take(_room_tokens(raw.replace("(", " ").replace(")", " ")), BOARD_PHRASES)
    if not vals:
        return None
    for code in ("AI", "FB", "HB", "BB", "RO"):
        if code in vals:
            return code
    return vals[0]


def parse_cancellation(raw: str | None) -> tuple[bool | None, int]:
    if not raw:
        return None, 0
    s = fold(raw)
    if re.search(r"\bnrf\b|non[\s-]?ref|no reembolsable|nonrefundable", s):
        return False, 0
    m = re.search(r"(\d+)\s*(h|hrs|hours|hour|horas)\b", s)
    if m:
        return True, int(m.group(1))
    m = re.search(r"(\d+)\s*(days|day|dias)", s)
    if m:
        return True, int(m.group(1)) * 24
    if "refundable" in s or "free" in s or "gratuita" in s or "cxl" in s:
        return True, 24
    return None, 0


BOARD_LABEL = {"RO": "Room only", "BB": "Breakfast", "HB": "Half board", "FB": "Full board", "AI": "All inclusive"}


# ------------------------------------------------------------------ activity parser
ATTRACTIONS = [
    ("burj_khalifa", ["burj khalifa"]), ("desert_safari_morning", ["morning desert safari", "safari matinal", "morning safari"]),
    ("desert_safari", ["desert safari", "safari por el desierto"]), ("dhow_marina", ["dhow cruise at dubai marina", "dhow por dubai marina", "marina dhow", "dhow cruise dubai marina"]),
    ("dhow_creek", ["creek dhow", "dhow cruise on dubai creek", "creek de dubai", "dhow por el creek"]),
    ("museum_future", ["museum of the future", "museo del futuro", "museum of future"]),
    ("dubai_frame", ["dubai frame"]), ("aquaventure", ["aquaventure"]),
    ("abu_dhabi_tour", ["abu dhabi full day tour", "abu dhabi city tour", "excursion a abu dabi", "grand mosque"]),
    ("img_worlds", ["img worlds"]), ("miracle_garden", ["miracle garden"]), ("global_village", ["global village"]),
    ("dubai_aquarium", ["dubai aquarium", "acuario de dubai"]), ("view_palm", ["the view at the palm", "the view palm"]),
    ("sky_views", ["sky views"]), ("motiongate", ["motiongate"]), ("legoland", ["legoland"]),
    ("ski_dubai", ["ski dubai", "snow park"]), ("dubai_city_tour", ["half day city tour", "city tour half day", "tour de medio dia", "dubai half day city tour"]),
    ("hot_air_balloon", ["hot air balloon", "globo"]), ("dolphinarium", ["dolphinarium", "delfinario", "dolphin show"]),
    ("wild_wadi", ["wild wadi"]), ("deep_dive", ["deep dive"]), ("yacht_marina", ["yacht"]), ("seaplane", ["seaplane", "hidroavion"]),
    ("ferrari_world", ["ferrari world"]), ("warner_world", ["warner bros"]), ("sharjah_tour", ["sharjah"]),
    ("old_dubai_walk", ["old dubai", "dubai antiguo"]),
]


def parse_duration(text: str | None) -> int | None:
    if not text:
        return None
    s = fold(text)
    if "half day" in s or "medio dia" in s:
        return 240
    if "full day" in s or "dia completo" in s:
        return 480
    h = re.search(r"(\d+(?:\.\d+)?)\s*(h|hrs|hours|horas)\b", s)
    m = re.search(r"(\d+)\s*(m|min|mins|minutes|minutos)\b", s)
    total = 0.0
    if h:
        total += float(h.group(1)) * 60
    if m:
        total += float(m.group(1))
    return int(total) if total else None


def parse_activity(listing: dict) -> dict:
    title = fold(listing.get("title", "")).replace("–", " ")
    t = " " + re.sub(r"[^a-z0-9+/ ]", " ", title) + " "
    t = " ".join(t.split())
    attraction = None
    for key, pats in ATTRACTIONS:
        if any(p in t for p in pats):
            attraction = key
            break
    tier = None
    if attraction == "burj_khalifa":
        tier = "148" if ("148" in t or " sky " in f" {t} ") else "124/125"
    slot = None
    if "non prime" in t or "no prime" in t:
        slot = "non-prime"
    elif "prime" in t:
        slot = "prime"
    elif "sunset" in t or "atardecer" in t:
        slot = "sunset"
    transfer = any(k in t for k in ["transfer", "traslado", "w/ trf", "trf", "pickup", "pick up"])
    no_meal = any(k in t for k in ["no dinner", "sin cena", "no breakfast", "sin desayuno", "(no "])
    meal = (not no_meal) and any(k in t for k in ["dinner", "cena", "bbq", "barbacoa", "lunch", "breakfast", "desayuno", "buffet"])
    private = any(k in f" {t} " for k in [" private ", " privado ", " pvt "])
    lang_raw = fold(listing.get("language", ""))
    language = "ES" if (lang_raw in ("es", "spanish", "espanol") or "spanish" in t or "en espanol" in t or "es guide" in t) else "EN"
    addons = sorted([a for a, keys in {"quad": ["quad"], "edge": ["edge"]}.items() if any(k in t for k in keys)])
    return {"core_attraction": attraction, "access_tier": tier, "time_slot": slot,
            "duration_min": parse_duration(listing.get("duration")), "transfer_included": transfer,
            "meal_included": meal, "private": private, "language": language, "addons": addons}
