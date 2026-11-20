"""Activities: Product -> Option -> Unit (OCTO). A different attraction or access tier is a different
product; itinerary, inclusions, private vs group, language or time slot make a different option."""
from __future__ import annotations

from collections import defaultdict

from app.pipeline.normalize import parse_activity

ATTRACTION_LABEL = {
    "burj_khalifa": "Burj Khalifa: At the Top", "desert_safari": "Evening Desert Safari", "dhow_marina": "Dhow Cruise · Dubai Marina",
    "dhow_creek": "Dhow Cruise · Dubai Creek", "museum_future": "Museum of the Future", "dubai_frame": "Dubai Frame",
    "aquaventure": "Aquaventure Waterpark", "abu_dhabi_tour": "Abu Dhabi City Tour", "img_worlds": "IMG Worlds of Adventure",
    "miracle_garden": "Dubai Miracle Garden", "global_village": "Global Village", "dubai_aquarium": "Dubai Aquarium & Underwater Zoo",
    "view_palm": "The View at The Palm", "sky_views": "Sky Views Dubai", "motiongate": "Motiongate Dubai", "legoland": "Legoland Dubai",
    "ski_dubai": "Ski Dubai", "dubai_city_tour": "Dubai Half-Day City Tour", "hot_air_balloon": "Hot Air Balloon",
    "dolphinarium": "Dubai Dolphinarium", "wild_wadi": "Wild Wadi Waterpark", "deep_dive": "Deep Dive Dubai",
    "yacht_marina": "Private Yacht · Dubai Marina", "seaplane": "Seaplane Tour", "ferrari_world": "Ferrari World Abu Dhabi",
    "warner_world": "Warner Bros. World Abu Dhabi", "sharjah_tour": "Sharjah Heritage Tour", "old_dubai_walk": "Old Dubai Walking Tour",
    "desert_safari_morning": "Morning Desert Safari",
}


def option_key(p: dict) -> tuple:
    return (p["time_slot"], p["transfer_included"], p["meal_included"], p["private"], p["language"], tuple(p["addons"]))


def option_label(p: dict) -> str:
    parts = []
    if p["time_slot"]:
        parts.append({"prime": "Prime time", "non-prime": "Non-prime", "sunset": "Sunset"}.get(p["time_slot"], p["time_slot"]))
    parts.append("Private" if p["private"] else "Shared")
    if p["meal_included"]:
        parts.append("Meal included")
    if p["transfer_included"]:
        parts.append("Hotel transfer")
    if p["language"] != "EN":
        parts.append(f"{p['language']} guide")
    parts += [a.title() for a in p["addons"]]
    return " · ".join(parts)


def build_products(listings: list[dict]) -> list[dict]:
    prods: dict[tuple, dict] = {}
    for l in listings:
        p = parse_activity(l)
        key = (p["core_attraction"] or f"unmatched:{l['listing_id']}", p["access_tier"])
        prod = prods.setdefault(key, {"attraction": key[0], "tier": key[1], "options": defaultdict(list)})
        prod["options"][option_key(p)].append({"listing": l, "parsed": p})
    out = []
    for (attr, tier), prod in prods.items():
        label = ATTRACTION_LABEL.get(attr, attr)
        if tier:
            label += f" · Level {tier}" if tier == "148" else f" · Levels {tier}"
        options = []
        for k, items in prod["options"].items():
            units = [{"supplier": it["listing"]["supplier"], "listing_id": it["listing"]["listing_id"],
                      "title": it["listing"]["title"], "duration": it["listing"]["duration"],
                      "duration_min": it["parsed"]["duration_min"], "prices": it["listing"]["prices"]} for it in items]
            options.append({"label": option_label(items[0]["parsed"]), "key": list(k), "units": units,
                            "suppliers": sorted({u["supplier"] for u in units}),
                            "best_adult": min(u["prices"]["adult"] for u in units)})
        options.sort(key=lambda o: (-len(o["suppliers"]), o["label"]))
        out.append({"product_id": f"AP-{len(out) + 1:03d}", "attraction": attr, "tier": tier, "label": label,
                    "options": options, "n_listings": sum(len(o["units"]) for o in options)})
    out.sort(key=lambda p: p["label"])
    return out


def evaluate(products: list[dict], truth_map: dict) -> dict:
    """Product purity/completeness and option purity vs ground truth."""
    lp = {}
    lo = {}
    for p in products:
        for oi, o in enumerate(p["options"]):
            for u in o["units"]:
                lp[u["listing_id"]] = p["product_id"]
                lo[u["listing_id"]] = (p["product_id"], oi)

    def pair_prf(pred: dict, true: dict):
        ids = sorted(pred)
        tp = fp = fn = 0
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                ps, ts = pred[a] == pred[b], true[a] == true[b]
                tp += ps and ts
                fp += ps and not ts
                fn += ts and not ps
        p = tp / (tp + fp) if tp + fp else 1.0
        r = tp / (tp + fn) if tp + fn else 1.0
        return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0}
    true_p = {k: v["product_id"] for k, v in truth_map.items() if k in lp}
    true_o = {k: (v["product_id"], tuple(sorted(v["option"].items()))) for k, v in truth_map.items() if k in lo}
    return {"product": pair_prf(lp, true_p), "option": pair_prf(lo, true_o)}
