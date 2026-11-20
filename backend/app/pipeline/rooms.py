"""Room layer: match supplier rooms inside a hotel cluster on room-identity attributes only."""
from __future__ import annotations

from itertools import combinations

from app.pipeline.normalize import canonical_room_name, parse_room, room_identity

W = {"class": 3.0, "bed": 2.0, "view": 2.0, "accessible": 2.0}
CORE = ("class", "bed", "view")
LARGE_BEDS = {"King", "Queen", "Double"}


def attr_score(a: dict, b: dict) -> tuple[float, bool, int]:
    """(score, conflict, n_missing). Missing values are neutral; conflicts are strongly negative."""
    s, conflict, missing = 0.0, False, 0
    for k in ("class", "bed", "view"):
        va, vb = a.get(k), b.get(k)
        if va is None or vb is None:
            missing += 1
            continue
        if va == vb:
            s += W[k]
        elif k == "bed" and "Double" in (va, vb) and {va, vb} <= LARGE_BEDS:
            s += 1.0  # "DBL" is bed-bank speak for any large bed: compatible, weaker evidence
        else:
            s -= 5.0
            conflict = True
    if bool(a.get("accessible")) == bool(b.get("accessible")):
        s += W["accessible"] * 0.5
    else:
        s -= 5.0
        conflict = True
    return s, conflict, missing


def merge_identity(members: list[dict]) -> dict:
    out = {}
    for k in ("class", "bed", "view", "accessible", "occupancy"):
        vals = [m[k] for m in members if m.get(k) is not None]
        if k == "bed":
            specific = [v for v in vals if v != "Double"]
            vals = specific or vals
        out[k] = max(set(vals), key=vals.count) if vals else None
    out["accessible"] = bool(out.get("accessible"))
    return out


def match_rooms(supplier_rooms: list[dict]) -> list[dict]:
    """supplier_rooms: [{supplier_room_id, supplier, room_name}]. Returns room groups."""
    items = []
    for r in supplier_rooms:
        parsed = parse_room(r["room_name"])
        items.append({**r, "parsed": parsed, "ident": room_identity(parsed)})
    groups = [{"members": [it], "suppliers": {it["supplier"]}} for it in items]

    def compatible(g1, g2):
        if g1.get("frozen") or g2.get("frozen") or (g1["suppliers"] & g2["suppliers"]):
            return None
        tot = 0.0
        for a in g1["members"]:
            for b in g2["members"]:
                s, conflict, _ = attr_score(a["ident"], b["ident"])
                if conflict:
                    return None
                tot = min(tot, s) if tot else s
        return tot

    # greedy agglomeration on complete (fully-specified) rooms first, then attach partial ones
    changed = True
    while changed:
        changed = False
        best = None
        for i, j in combinations(range(len(groups)), 2):
            s = compatible(groups[i], groups[j])
            if s is None or s < 5.0:
                continue
            # an incomplete room must be unambiguous: only one compatible group may exist
            if best is None or s > best[0]:
                best = (s, i, j)
        if best:
            _, i, j = best
            gi, gj = groups[i], groups[j]
            partial = [g for g in (gi, gj) if any(m["ident"].get(k) is None for m in g["members"] for k in CORE)]
            if partial:
                p = partial[0]
                rivals = [g for g in groups if g is not p and (compatible(p, g) or -1) >= 5.0]
                if len(rivals) > 1:
                    # incomplete room fits several real rooms: keep it apart, flag it for review
                    p["ambiguous"] = p["frozen"] = True
                    changed = True
                    continue
            gi["members"] += gj["members"]
            gi["suppliers"] |= gj["suppliers"]
            groups.pop(j)
            changed = True
    out = []
    for g in groups:
        ident = merge_identity([m["ident"] for m in g["members"]])
        complete = all(all(m["ident"].get(k) is not None for k in CORE) for m in g["members"])
        out.append({
            "ident": ident, "name": canonical_room_name(ident),
            "tier": "Primary" if complete else "Secondary",
            "ambiguous": bool(g.get("ambiguous")),
            "members": [{"supplier_room_id": m["supplier_room_id"], "supplier": m["supplier"], "room_name": m["room_name"],
                         "parsed": {k: m["parsed"].get(k) for k in ("class", "bed", "view", "accessible", "board", "refundable", "extras")}}
                        for m in g["members"]],
            "suppliers": sorted({m["supplier"] for m in g["members"]}),
        })
    out.sort(key=lambda g: (-len(g["suppliers"]), g["name"]))
    return out
