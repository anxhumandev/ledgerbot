"""Scene 08A: LedgerBot vs LLM-only benchmark on identical pair sets."""
from __future__ import annotations

import random
import time

import numpy as np
import orjson

from app import config
from app.demo import DEMO
from app.eval import baseline_llm
from app.eval.metrics import decision_prf, percentiles
from app.pipeline.cost import price_inr
from app.pipeline.features import pair_features

_CACHE: dict = {}


def _truth():
    if "truth" not in _CACHE:
        _CACHE["truth"] = orjson.loads((config.WORLD_DIR / "truth.json").read_bytes())
    return _CACHE["truth"]


def _rec(rid):
    r = DEMO.rec_by_id[rid]
    return {"record_id": rid, "supplier": r["supplier"], "name": r["name"], "address": r.get("address"), "phone": r.get("phone"),
            "stars": r.get("stars"), "lat": r.get("lat"), "lng": r.get("lng"), "true_hotel": _truth()["hotel_of_record"][rid]}


def build_sets() -> dict:
    """Deterministic evaluation sets shared by both systems (test split only)."""
    if baseline_llm.SETS_PATH.exists():
        cached = orjson.loads(baseline_llm.SETS_PATH.read_bytes())
        if cached.get("build") == DEMO.state["built_at"] and cached.get("version") == 2 and cached.get("world_digest") == DEMO.state.get("world_digest"):
            return cached
    t = _truth()
    st = DEMO.state
    rid = [n["record_id"] for n in st["norms"]]
    rng = random.Random(config.SEED + 404)
    test = [k for k, (i, j) in enumerate(st["pairs"])
            if t["splits"].get(t["hotel_of_record"][rid[i]]) == "test" and t["splits"].get(t["hotel_of_record"][rid[j]]) == "test"]
    lab = {k: int(t["hotel_of_record"][rid[st["pairs"][k][0]]] == t["hotel_of_record"][rid[st["pairs"][k][1]]]) for k in test}
    negs = sorted([k for k in test if lab[k] == 0], key=lambda k: -st["p"][k])
    hard = negs[:160]
    positives = [k for k in test if lab[k] == 1]
    pos = rng.sample(positives, min(160, len(positives)))
    remaining = negs[len(hard):]
    rest = rng.sample(remaining, min(400 - len(hard) - len(pos), len(remaining)))
    hotel = []
    for k in hard + pos + rest:
        i, j = st["pairs"][k]
        hotel.append({"pair_id": f"{rid[i]}|{rid[j]}", "a": _rec(rid[i]), "b": _rec(rid[j]), "label": lab[k],
                      "kind": "hard_negative" if k in hard else ("positive" if lab[k] else "negative")})
    # room-variant set: offer pairs within test hotels
    offers = orjson.loads((config.WORLD_DIR / "offers_raw.json").read_bytes())
    by_room = {}
    for o in offers:
        h = t["hotel_of_record"][o["record_id"]]
        if t["splits"].get(h) != "test":
            continue
        by_room.setdefault(t["room_of_offer"][o["offer_id"]], []).append(o)
    rooms = list(by_room.items())
    rng.shuffle(rooms)
    same_offer, diff_offer, diff_room = [], [], []
    terms = t["offer_terms"]
    for room_id, os_ in rooms:
        for a in os_:
            for b in os_:
                if a["offer_id"] >= b["offer_id"] or a["supplier"] == b["supplier"]:
                    continue
                ta, tb = terms[a["offer_id"]], terms[b["offer_id"]]
                if (ta["board"], ta["refundable"]) == (tb["board"], tb["refundable"]):
                    if len(same_offer) < 50:
                        same_offer.append((a, b))
                elif len(diff_offer) < 100:
                    diff_offer.append((a, b))
    hotel_rooms = {}
    for room_id, os_ in rooms:
        hotel_rooms.setdefault(room_id.rsplit("-R", 1)[0], []).append((room_id, os_))
    for lst in hotel_rooms.values():
        for i, (_, first) in enumerate(lst):
            for _, second in lst[i + 1:]:
                match = next(((a, b) for a in first for b in second
                              if a["supplier"] != b["supplier"] and terms[a["offer_id"]]["board"] == terms[b["offer_id"]]["board"]), None)
                if match:
                    diff_room.append(match)
    rng.shuffle(diff_room)
    diff_room = diff_room[:50]
    room = []
    for kind, lst, y in (("same_offer", same_offer, 1), ("same_room_diff_offer", diff_offer, 0), ("different_room", diff_room, 0)):
        for a, b in lst:
            room.append({"pair_id": f"{a['offer_id']}|{b['offer_id']}", "label": y, "kind": kind,
                         "a": {k: a[k] for k in ("offer_id", "supplier", "room_name", "board_raw", "cancellation_raw", "price_inr")},
                         "b": {k: b[k] for k in ("offer_id", "supplier", "room_name", "board_raw", "cancellation_raw", "price_inr")}})
    sets = {"hotel": hotel, "room": room, "version": 2, "build": st["built_at"], "world_digest": st.get("world_digest")}
    baseline_llm.SETS_PATH.write_bytes(orjson.dumps(sets))
    return sets


def offer_index() -> dict:
    if "offer_idx" not in _CACHE:
        idx = {}
        for tid, h in DEMO.base_hotels.items():
            for gi, g in enumerate(h.get("rooms") or []):
                for s in g["slots"]:
                    for o in s["offers"]:
                        idx[o["offer_id"]] = (tid, gi, s["board"], s["refundable"])
        _CACHE["offer_idx"] = idx
    return _CACHE["offer_idx"]


def tessera_hotel_decision(a: str, b: str) -> dict:
    k = DEMO.pair_index.get((a, b), DEMO.pair_index.get((b, a)))
    if k is None:
        return {"answer": "different", "p": None, "route": "blocked"}
    raw = float(DEMO.state["raw"][k])
    p = float(DEMO.state["p"][k])
    band = DEMO.band_of(raw)
    llm = DEMO.state["llm"].get(f"{a}|{b}") or DEMO.state["llm"].get(f"{b}|{a}")
    if band == "auto_merge":
        return {"answer": "same", "p": p, "route": "auto"}
    if band == "auto_reject":
        return {"answer": "different", "p": p, "route": "auto"}
    if llm and llm["route"] == "llm":
        return {"answer": llm["verdict"], "p": p, "route": "llm"}
    return {"answer": "abstain", "p": p, "route": "review"}


def tessera_room_decision(oa: str, ob: str) -> dict:
    idx = offer_index()
    A, B = idx.get(oa), idx.get(ob)
    if not A or not B:
        return {"answer": "abstain"}
    same_room = A[:2] == B[:2]
    same_terms = A[2:] == B[2:]
    if same_room and same_terms:
        return {"answer": "same", "detail": "same room, same terms"}
    if same_room:
        return {"answer": "different", "detail": "same room, different offer"}
    return {"answer": "different", "detail": "different room"}


def tessera_latency() -> dict:
    if "lat" not in _CACHE:
        st = DEMO.state
        rng = np.random.default_rng(1)
        ks = rng.choice(len(st["pairs"]), 400, replace=False)
        ts = []
        for k in ks:
            i, j = st["pairs"][k]
            t0 = time.perf_counter()
            x = np.array(pair_features(st["norms"][i], st["norms"][j], float(st["emb"][i] @ st["emb"][j]),
                                       st["index"].hashes.get(st["norms"][i]["record_id"]), st["index"].hashes.get(st["norms"][j]["record_id"])),
                         dtype=np.float32).reshape(1, -1)
            DEMO.matcher.predict(x)
            ts.append((time.perf_counter() - t0) * 1000)
        _CACHE["lat"] = percentiles(ts)
    return _CACHE["lat"]


def benchmark() -> dict:
    sets = build_sets()
    base = baseline_llm.load_results()
    hd = [tessera_hotel_decision(x["a"]["record_id"], x["b"]["record_id"]) for x in sets["hotel"]]
    decided = [(d, x) for d, x in zip(hd, sets["hotel"]) if d["answer"] != "abstain"]
    t_hotel = decision_prf([d["answer"] == "same" for d, _ in decided], [x["label"] for _, x in decided])
    rd = [tessera_room_decision(x["a"]["offer_id"], x["b"]["offer_id"]) for x in sets["room"]]
    t_room = decision_prf([d["answer"] == "same" for d in rd], [x["label"] for x in sets["room"]])
    # LedgerBot calibration on held-out test pairs
    st = DEMO.state
    pt = DEMO.matcher.calibrate(st["test_raw"])
    rel = []
    for lo in np.arange(0.5, 1.0, 0.1):
        m = (np.maximum(pt, 1 - pt) >= lo) & (np.maximum(pt, 1 - pt) < lo + 0.1 + (1e-9 if lo >= 0.9 else 0))
        if m.sum() >= 20:  # tiny bins are noise, not calibration evidence
            acc = float(np.mean((pt[m] >= 0.5) == (st["test_y"][m] == 1)))
            rel.append({"confidence": float(lo + 0.05), "accuracy": acc, "n": int(m.sum())})
    uncertain_share = float((st["band"] == 1).mean())
    per_pair_llm = price_inr(config.ADJUDICATOR_MODEL, 900, 120) / 10  # batched 10 per call (estimate)
    usage = st.get("adjudication_usage")
    tess_cost = uncertain_share * per_pair_llm * 1000
    if usage is not None:
        tess_cost = usage["inr"] * 1000 / max(1, len(st["pairs"]))
    largest_wrong = 0
    t = _truth()["hotel_of_record"]
    for g in st["groups"]:
        if len({t[m] for m in g}) > 1:
            largest_wrong = max(largest_wrong, len(g))
    out = {
        "tessera": {
            "hotel_f1": t_hotel["f1"], "hotel_precision": t_hotel["precision"], "hotel_recall": t_hotel["recall"],
            "hotel_coverage": len(decided) / len(sets["hotel"]), "abstained": len(sets["hotel"]) - len(decided),
            "room_f1": t_room["f1"], "consistency_violations": st["consistency"]["total_violations"],
            "largest_wrong_cluster": largest_wrong, "cost_per_1000_inr": tess_cost, "cost_estimated": usage is None,
            "latency_ms": tessera_latency(), "reliability": rel, "guarantee": DEMO.current_risk,
            "global_f1": st["evals"]["test_pairwise"]["f1"],
        },
        "baseline": None, "n_hotel": len(sets["hotel"]), "n_room": len(sets["room"]),
        "baseline_model": config.BASELINE_MODEL,
    }
    if base and all({p["pair_id"] for p in base.get(kind, [])} == {p["pair_id"] for p in sets[kind]} for kind in ("hotel", "room")):
        s = base["summary"]
        out["baseline"] = {"run_at": base["run_at"], "model": base["model"], "n_hotel": len(base["hotel"]), "n_room": len(base["room"]),
                           "hotel_f1": s.get("hotel_prf", {}).get("f1"), "room_f1": s.get("room_prf", {}).get("f1"),
                           "consistency_violations": s.get("consistency_violations"), "largest_wrong_cluster": s.get("largest_wrong_cluster"),
                           "cost_per_1000_inr": (s.get("hotel_cost_per_pair_inr") or 0) * 1000,
                           "latency_s": s.get("hotel_latency"), "reliability": s.get("reliability")}
    return out


def corner_cases(limit: int = 12) -> list[dict]:
    base = baseline_llm.load_results()
    if not base:
        return []
    out = []
    for x in base.get("hotel", []):
        td = tessera_hotel_decision(x["a"]["record_id"], x["b"]["record_id"])
        if x["same"] != bool(x["label"]) and td["answer"] in ("same", "different") and (td["answer"] == "same") == bool(x["label"]):
            out.append({"kind": "hotel", "a": x["a"], "b": x["b"], "truth": "same" if x["label"] else "different",
                        "llm": {"same": x["same"], "confidence": x["confidence"]}, "tessera": td})
    for x in base.get("room", []):
        td = tessera_room_decision(x["a"]["offer_id"], x["b"]["offer_id"])
        if x["same"] != bool(x["label"]) and (td["answer"] == "same") == bool(x["label"]):
            out.append({"kind": "room", "a": x["a"], "b": x["b"], "truth": x["kind"],
                        "llm": {"same": x["same"], "confidence": x["confidence"]}, "tessera": td})
    out.sort(key=lambda c: (c["kind"] != "room", -c["llm"]["confidence"]))
    return out[:limit]
