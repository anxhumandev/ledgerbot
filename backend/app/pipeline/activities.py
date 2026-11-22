"""Activities: Product -> Option -> Unit (OCTO). A different attraction or access tier is a different
product; itinerary, inclusions, private vs group, language, time slot, duration or (when the feed provides it)
cancellation terms make a different option.

Duration is compared as an interval (normalize.duration_range): listings join an option only if their duration
intervals overlap, so "10h", "600 minutos" and "full day" can be one option while "2h" and "4h" cannot."""
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
    """Exact-match attributes of an option. Duration is matched separately by interval (see _split_by_duration)."""
    c = p.get("cancellation")
    cancel = (c["refundable"], c["free_cancel_hours"]) if c else None
    return (p["time_slot"], p["transfer_included"], p["meal_included"], p["private"], p["language"], tuple(p["addons"]), cancel)


def _split_by_duration(items: list[dict]) -> list[list[dict]]:
    """Group listings whose duration intervals share a common overlap. Precise durations seed the groups (narrowest
    first); vague ones join the group they overlap most; listings without a duration join the largest group."""
    known = sorted((it for it in items if it["parsed"].get("duration_range")),
                   key=lambda it: (it["parsed"]["duration_range"][1] - it["parsed"]["duration_range"][0], it["parsed"]["duration_range"][0]))
    groups: list[dict] = []
    for it in known:
        lo, hi = it["parsed"]["duration_range"]
        best, best_overlap = None, 0
        for g in groups:
            ov = min(hi, g["hi"]) - max(lo, g["lo"])
            if ov > best_overlap:
                best, best_overlap = g, ov
        if best is None:
            groups.append({"lo": lo, "hi": hi, "items": [it]})
        else:
            best["lo"], best["hi"] = max(lo, best["lo"]), min(hi, best["hi"])
            best["items"].append(it)
    unknown = [it for it in items if not it["parsed"].get("duration_range")]
    if unknown:
        if groups:
            max(groups, key=lambda g: len(g["items"]))["items"].extend(unknown)
        else:
            groups.append({"lo": None, "hi": None, "items": unknown})
    return [g["items"] for g in groups]


def _duration_text(units: list[dict]) -> str:
    mins = sorted({u["duration_min"] for u in units if u.get("duration_min")})
    if not mins:
        return ""
    fmt = lambda m: f"{m // 60} h{f' {m % 60} min' if m % 60 else ''}" if m >= 60 else f"{m} min"  # noqa: E731
    return fmt(mins[0]) if len(mins) == 1 else f"{fmt(mins[0])}–{fmt(mins[-1])}"


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


def _cancel_text(c: dict | None) -> str:
    if not c:
        return ""
    return f"Free cancellation {c['free_cancel_hours']} h" if c["refundable"] else "Non-refundable"


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
        for k, all_items in prod["options"].items():
            for items in _split_by_duration(all_items):
                units = [{"supplier": it["listing"]["supplier"], "listing_id": it["listing"]["listing_id"],
                          "title": it["listing"]["title"], "duration": it["listing"]["duration"],
                          "duration_min": it["parsed"]["duration_min"], "prices": it["listing"]["prices"]} for it in items]
                ranges = [it["parsed"]["duration_range"] for it in items if it["parsed"].get("duration_range")]
                options.append({"label": option_label(items[0]["parsed"]), "key": list(k[:6]), "units": units,
                                "suppliers": sorted({u["supplier"] for u in units}),
                                "duration_window": [max(r[0] for r in ranges), min(r[1] for r in ranges)] if ranges else None,
                                "cancellation": items[0]["parsed"].get("cancellation"),
                                "best_adult": min(u["prices"]["adult"] for u in units)})
        # options that differ only by duration or cancellation get it in their label
        labels = [o["label"] for o in options]
        for o in options:
            if labels.count(o["label"]) > 1:
                extra = [x for x in (_duration_text(o["units"]), _cancel_text(o["cancellation"])) if x]
                if extra:
                    o["label"] += " · " + " · ".join(extra)
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
