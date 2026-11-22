"""Running business-impact ledger for the top bar.

Every figure says how it was made:
- "measured": counted from the pipeline output on this world (and from live actions this session).
- "simulated": comes from the booking simulator or the A/B replay (Scenes 06 and 10).
- "assumption": a measured count multiplied by a stated assumption from config (e.g. minutes of manual mapping).
Nothing here is a fixed number; the ledger grows as the demo runs (onboarding, review decisions, sabotage, replay).
"""
from __future__ import annotations

from app import config
from app.demo import DEMO
from app.services import analyst


def snapshot() -> dict:
    s = DEMO.state["summary"]
    oe = DEMO.state["offer_eval"]
    onb = (DEMO.onboarding or {}).get("counters") or {}
    merged_live = int(onb.get("auto_merge", 0)) + int(onb.get("llm", 0))
    mapped_live = merged_live + int(onb.get("new_cluster", 0))

    records = int(s["all_raw_records"]) + mapped_live
    hotels = int(s["all_hotels"]) + int(onb.get("new_cluster", 0))
    duplicates = records - hotels
    hours = records * config.MANUAL_MAPPING_MIN_PER_RECORD / 60.0
    rv = analyst.stats()

    items = [
        {"key": "duplicates", "label": "Duplicate supplier listings removed", "value": duplicates, "unit": "count",
         "kind": "measured", "how": f"{records:,} supplier records → {hotels:,} real hotels"},
        {"key": "rooms", "label": "Room names → real rooms (Dubai)", "value": int(s["dubai_room_names"]), "unit": "count",
         "to": int(s["dubai_room_groups"]), "kind": "measured", "how": "rooms matched on class, bed, view, occupancy"},
        {"key": "wrong_room", "label": "Wrong-room rates caught (Dubai)", "value": int(oe["raw_wrong_room"]) - int(oe["tessera_wrong_room"]),
         "unit": "count", "kind": "measured",
         "how": f"{oe['raw_wrong_room']} feed mis-mappings on the raw shelf vs {oe['tessera_wrong_room']} left after LedgerBot"},
        {"key": "hours", "label": "Manual mapping hours saved", "value": hours, "unit": "hours", "kind": "assumption",
         "how": f"{records:,} records mapped by the pipeline × {config.MANUAL_MAPPING_MIN_PER_RECORD:g} min each by hand "
                f"(only {DEMO.state['routes'].get('review', 0):,} candidate pairs needed a person)"},
    ]
    if mapped_live:
        items.append({"key": "onboarded", "label": "NovaBeds records mapped live", "value": mapped_live, "unit": "count",
                      "kind": "measured", "how": f"{merged_live} merged into existing hotels, {onb.get('new_cluster', 0)} new"})
    if rv["reviewed"]:
        items.append({"key": "reviews", "label": "Human review decisions", "value": rv["reviewed"], "unit": "count",
                      "kind": "measured", "how": f"median {rv['median_seconds']} s per decision; each one becomes a training label"})
    from app.services.simulator import SIM
    toast = SIM.last_toast or {}
    if toast.get("switched"):
        items.append({"key": "failures_day", "label": "Failed bookings avoided per day", "value": toast["failures_avoided_per_day"],
                      "unit": "count", "kind": "simulated",
                      "how": f"{toast['switched']} offer slots moved away from {toast['from_name']}"})
    rp = getattr(DEMO, "last_replay", None)
    if rp:
        raw, tess = rp["arms"]["raw"], rp["arms"]["tessera"]
        items += [
            {"key": "gp_lift", "label": "Gross profit per search", "value": rp["lift_gp_per_search"], "unit": "pct",
             "kind": "simulated", "how": f"{rp['n']:,} replayed searches, raw shelf vs LedgerBot"},
            {"key": "failed", "label": "Failed bookings avoided (replay)", "value": raw["failed"] - tess["failed"],
             "unit": "count", "kind": "simulated", "how": f"{raw['failed']} → {tess['failed']}"},
            {"key": "wrong_room_replay", "label": "Wrong-room incidents avoided (replay)",
             "value": raw["wrong_room"] - tess["wrong_room"], "unit": "count", "kind": "simulated",
             "how": f"{raw['wrong_room']} → {tess['wrong_room']}"},
            {"key": "annual", "label": "Annualised at TBO scale (illustrative)", "value": rp["annualized_inr_illustrative"],
             "unit": "inr", "kind": "simulated", "how": rp["formula"]},
        ]
    by = {i["key"]: i for i in items}
    headline = by.get("gp_lift") or by.get("failures_day") or by["wrong_room"]
    return {"items": items, "pill": [by["duplicates"], by["hours"], headline]}
