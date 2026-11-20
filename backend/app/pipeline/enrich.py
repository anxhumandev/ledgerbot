"""M4: golden records, room groups, offer slots, activities, truth discovery, photo dedup."""
from __future__ import annotations

import re
import time
from collections import Counter, defaultdict

import numpy as np
import orjson

from app import config
from app.eval import metrics as M
from app.pipeline import activities as act
from app.pipeline import content, offers as off, rooms
from app.pipeline.normalize import parse_room, room_identity
from data.tables import CITIES

SUP_PRIORITY = ["S1", "S4", "S3", "S6", "S2", "S5"]


def load_json(name):
    return orjson.loads((config.WORLD_DIR / name).read_bytes())


def golden_name(recs: list[dict]) -> str:
    by = {r["supplier"]: r for r in recs}
    for s in SUP_PRIORITY:
        if s in by:
            n = by[s]["name"]
            n = re.sub(r",\s*an? [^,]+ Hotel$", "", n)
            n = re.sub(r"\s*[–-]\s*Luxury Collection$", "", n)
            if s == "S4" and n.startswith("The ") and not any(r["name"].startswith("The ") for r in recs if r["supplier"] != "S4"):
                n = n[4:]
            if n.isupper() or n.islower():
                n = n.title()
            return n
    return recs[0]["name"]


def neighbourhood_of(city: str, lat: float, lng: float) -> str:
    best, bd = None, 1e9
    for nb, (la0, la1, lo0, lo1) in CITIES.get(city, {}).get("neighbourhoods", {}).items():
        d = (lat - (la0 + la1) / 2) ** 2 + ((lng - (lo0 + lo1) / 2) * 0.9) ** 2
        if la0 <= lat <= la1 and lo0 <= lng <= lo1:
            d *= 0.1
        if d < bd:
            best, bd = nb, d
    return best or CITIES.get(city, {}).get("name", city)


def tessera_ids(groups, norms_by_id):
    keyed = sorted(groups, key=lambda g: (norms_by_id[min(g)]["city"] != "dubai", norms_by_id[min(g)]["city"], min(g)))
    return {f"TS-{k + 1:05d}": sorted(g) for k, g in enumerate(keyed)}


def enrich(state: dict) -> dict:
    t0 = time.time()
    truth = load_json("truth.json")
    rooms_raw = load_json("rooms_raw.json")
    offers_raw = load_json("offers_raw.json")
    listings = load_json("activities_raw.json")
    norms_by_id = {n["record_id"]: n for n in state["norms"]}
    recs_by_id = {r["record_id"]: r for r in state["recs"]}
    alias = state["alias"]

    clusters = tessera_ids(state["groups"], norms_by_id)
    record_cluster = {r: tid for tid, ms in clusters.items() for r in ms}

    # ---- truth discovery over all multi-record clusters (primary records only)
    cl_lists = [[norms_by_id[r] for r in ms if r not in alias] for ms in clusters.values()]
    trust, consensus = content.truth_discovery(cl_lists)

    # ---- golden records
    hotels = {}
    for (tid, ms), cons in zip(clusters.items(), consensus):
        prim = [r for r in ms if r not in alias]
        recs = [recs_by_id[r] for r in prim]
        n0 = norms_by_id[prim[0]]
        lat, lng = cons.get("coords", (n0["lat"], n0["lng"]))
        city = n0["city"]
        phone = cons.get("phone")
        addr_src = None
        if cons.get("address"):
            for r in prim:
                if content._addr_key(norms_by_id[r]) == cons["address"]:
                    addr_src = recs_by_id[r]["address"]
                    break
        hotels[tid] = {
            "tessera_id": tid, "name": golden_name(recs), "brand": Counter(norms_by_id[r]["brand"] for r in prim).most_common(1)[0][0],
            "stars": cons.get("stars") or n0["stars"], "city": city, "neighbourhood": neighbourhood_of(city, lat, lng),
            "lat": lat, "lng": lng, "phone": phone, "address": addr_src,
            "members": ms, "suppliers": sorted({norms_by_id[r]["supplier"] for r in prim}), "n_records": len(ms),
            "dups": [r for r in ms if r in alias],
        }
    print(f"  golden records: {len(hotels)}  learned trust: { {k: round(v, 3) for k, v in trust.items()} }  [{time.time() - t0:.1f}s]")

    # ---- rooms + offers (Dubai: the detailed world)
    rooms_by_rec = defaultdict(list)
    for r in rooms_raw:
        rooms_by_rec[r["record_id"]].append(r)
    offers_by_rec = defaultdict(list)
    for o in offers_raw:
        offers_by_rec[o["record_id"]].append(o)
    phash = orjson.loads((config.CACHE_DIR / "phash.json").read_bytes()) if (config.CACHE_DIR / "phash.json").exists() else {}
    room_true = truth["room_of_supplier_room"]
    offer_true = truth["room_of_offer"]
    room_pairs_pred, room_pairs_true = set(), set()
    n_offers = tess_incidents = raw_incidents = 0
    sup_room_names, n_groups, n_sup_rooms = set(), 0, 0
    for tid, h in hotels.items():
        if h["city"] != "dubai":
            continue
        prim = [r for r in h["members"] if r not in alias]
        srooms = [sr for r in prim for sr in rooms_by_rec[r]]
        groups = rooms.match_rooms(srooms)
        n_groups += len(groups)
        n_sup_rooms += len(srooms)
        g_of = {}
        for gi, g in enumerate(groups):
            for m in g["members"]:
                g_of[m["supplier_room_id"]] = gi
                sup_room_names.add((m["supplier"], m["room_name"]))
        # room-level evaluation (pairs of supplier rooms within this hotel)
        ids = [sr["supplier_room_id"] for sr in srooms]
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                if g_of[a] == g_of[b]:
                    room_pairs_pred.add((a, b))
                if room_true.get(a) == room_true.get(b):
                    room_pairs_true.add((a, b))
        # offers -> room groups via the offer's own room text (fixes raw-feed mis-mapping)
        ident_of = {}
        for sr in srooms:
            ident_of[(sr["record_id"], tuple(sorted(room_identity(parse_room(sr["room_name"])).items())))] = sr["supplier_room_id"]
        group_true = {}
        for gi, g in enumerate(groups):
            tr = Counter(room_true.get(m["supplier_room_id"]) for m in g["members"]).most_common(1)[0][0]
            group_true[gi] = tr
        slots = defaultdict(list)
        for r in prim:
            for o in offers_by_rec[r]:
                no = off.normalize_offer(o)
                key = (r, tuple(sorted(room_identity(parse_room(o["room_name"])).items())))
                srid = ident_of.get(key, o["supplier_room_id"])
                gi = g_of.get(srid, g_of.get(o["supplier_room_id"]))
                if gi is None:
                    continue
                no["group"] = gi
                no["raw_room_name"] = next((sr["room_name"] for sr in srooms if sr["supplier_room_id"] == o["supplier_room_id"]), o["room_name"])
                slots[off.slot_key(gi, no)].append(no)
                n_offers += 1
                tess_incidents += group_true[gi] != offer_true[o["offer_id"]]
                raw_incidents += room_true.get(o["supplier_room_id"]) != offer_true[o["offer_id"]]
        for gi, g in enumerate(groups):
            g["slots"] = []
            for key, offs in slots.items():
                if key[0] != gi:
                    continue
                hours = max((o["cancel_hours"] for o in offs), default=0)
                g["slots"].append({"key": [key[1], key[2], key[3], key[4]], "board": key[1], "refundable": key[2],
                                   "label": off.slot_label(key[1], key[2], hours or None), "offers": offs})
            g["slots"].sort(key=lambda s: (["RO", "BB", "HB", "FB", "AI"].index(s["board"]), not s["refundable"]))
        h["rooms"] = groups
        h["n_offers"] = sum(len(s["offers"]) for g in groups for s in g["slots"])
        recs = [recs_by_id[r] for r in prim]
        h["photos"] = content.dedup_photos(recs, phash) if any(r.get("photos") for r in recs) else None
    content.save_sharpness()
    tp = len(room_pairs_pred & room_pairs_true)
    room_eval = M.prf(tp, len(room_pairs_pred) - tp, len(room_pairs_true) - tp)
    print(f"  Dubai rooms: {n_sup_rooms} supplier rooms ({len(sup_room_names)} distinct names) -> {n_groups} room groups · room-pair F1 {room_eval['f1']:.4f} "
          f"(P {room_eval['precision']:.4f} R {room_eval['recall']:.4f}) · offers {n_offers} · wrong-room: raw {raw_incidents} vs tessera {tess_incidents}  [{time.time() - t0:.1f}s]")

    # ---- activities
    products = act.build_products(listings)
    act_eval = act.evaluate(products, truth["activity_of_listing"])
    print(f"  activities: {len(listings)} listings -> {len(products)} products · product F1 {act_eval['product']['f1']:.3f} · option F1 {act_eval['option']['f1']:.3f}")

    dubai = [h for h in hotels.values() if h["city"] == "dubai"]
    dubai_recs = sum(h["n_records"] for h in dubai)
    showcase = {}
    for h in dubai:
        if h["name"] in ("Atlantis The Palm", "Atlantis The Royal"):
            showcase[h["name"]] = h["tessera_id"]
    state.update({
        "hotels": hotels, "record_cluster": record_cluster, "trust": trust, "products": products,
        "room_eval": room_eval, "activity_eval": act_eval,
        "offer_eval": {"offers": n_offers, "raw_wrong_room": raw_incidents, "tessera_wrong_room": tess_incidents,
                       "raw_rate": raw_incidents / max(1, n_offers), "tessera_rate": tess_incidents / max(1, n_offers)},
        "summary": {
            "dubai_raw_records": dubai_recs, "dubai_hotels": len(dubai), "dubai_room_names": n_sup_rooms, "dubai_distinct_room_strings": len(sup_room_names),
            "dubai_room_groups": n_groups, "dubai_offers": n_offers, "violations": state["consistency"]["total_violations"],
            "all_raw_records": len(state["norms"]), "all_hotels": len(hotels), "activities_listings": len(listings),
            "activity_products": len(products),
        },
        "showcase": showcase,
    })
    return state
