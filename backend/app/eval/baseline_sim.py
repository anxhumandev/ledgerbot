"""Simulated LLM-only baseline, for demos without an API key.

    python -m app.eval.baseline_sim      # writes cache/baseline_results.json with "simulated": true

The answers are drawn from the stated error rates in config.SIM_BASELINE (assumptions, not measurements).
Which pairs are answered wrongly is decided by observable difficulty, so the mistakes fall on realistic cases:
the most similar-looking sister hotels get merged, the noisiest true matches get missed, and room pairs that
differ only in board or cancellation terms get merged. F1, consistency violations, the largest wrong cluster and
the reliability diagram are then computed from those answers by the same code as a real run.

Every screen labels these results "simulated". A real `make baseline` run overwrites the file and never reuses
simulated rows.
"""
from __future__ import annotations

import math
import random
import time

import numpy as np
import orjson
from rapidfuzz import fuzz

from app import config
from app.eval import baseline_llm
from app.pipeline.cost import price_inr


def _km(a: dict, b: dict) -> float:
    if None in (a.get("lat"), a.get("lng"), b.get("lat"), b.get("lng")):
        return 5.0
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lng"], b["lat"], b["lng"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _look_alike(x: dict) -> float:
    """How alike the two listings look to a reader: name similarity, minus a little for distance."""
    a, b = x["a"], x["b"]
    if "room_name" in a:
        return fuzz.token_set_ratio(a["room_name"], b["room_name"]) / 100
    return fuzz.token_set_ratio(a["name"] or "", b["name"] or "") / 100 - min(_km(a, b), 5.0) / 25


def _wrong_ids(items: list[dict], rate: float, hardest_first: bool) -> set[str]:
    """The round(rate * n) pairs that are hardest: most alike for non-matches, least alike for matches."""
    n = round(rate * len(items))
    ranked = sorted(items, key=_look_alike, reverse=hardest_first)
    return {x["pair_id"] for x in ranked[:n]}


def run() -> dict:
    from app.demo import DEMO
    from app.services.arena import build_sets

    p = config.SIM_BASELINE
    DEMO.load()
    sets = build_sets()
    rng = random.Random(p["seed"])
    nrng = np.random.default_rng(p["seed"])

    hotel, room = sets["hotel"], sets["room"]
    by_kind = lambda lst, k: [x for x in lst if x["kind"] == k]  # noqa: E731
    wrong = set()
    wrong |= _wrong_ids(by_kind(hotel, "hard_negative"), p["hotel_hard_negative_false_merge"], hardest_first=True)
    wrong |= _wrong_ids(by_kind(hotel, "negative"), p["hotel_negative_false_merge"], hardest_first=True)
    wrong |= _wrong_ids(by_kind(hotel, "positive"), p["hotel_positive_miss"], hardest_first=False)
    wrong |= _wrong_ids(by_kind(room, "same_room_diff_offer"), p["room_diff_terms_false_merge"], hardest_first=True)
    wrong |= _wrong_ids(by_kind(room, "different_room"), p["room_diff_room_false_merge"], hardest_first=True)
    wrong |= _wrong_ids(by_kind(room, "same_offer"), p["room_same_offer_miss"], hardest_first=False)

    cost = price_inr(config.BASELINE_MODEL, baseline_llm.EST_INPUT_TOKENS, baseline_llm.EST_OUTPUT_TOKENS)

    def answer(x: dict) -> dict:
        err = x["pair_id"] in wrong
        same = bool(x["label"]) != err
        # zero-shot LLMs state high confidence whether or not they are right
        conf = rng.randint(80, 97) if err else rng.randint(85, 100)
        lat = float(nrng.lognormal(math.log(p["latency_median_s"]), p["latency_sigma"]))
        return {**x, "same": same, "confidence": conf, "latency_s": lat,
                "input_tokens": baseline_llm.EST_INPUT_TOKENS, "output_tokens": baseline_llm.EST_OUTPUT_TOKENS, "cost_inr": cost}

    h = [answer(x) for x in hotel]
    r = [answer(x) for x in room]
    res = {"run_at": time.strftime("%Y-%m-%d %H:%M"), "model": config.BASELINE_MODEL, "simulated": True,
           "profile": {k: v for k, v in p.items() if k != "seed"},
           "world_digest": DEMO.state.get("world_digest"), "hotel": h, "room": r, "complete": True,
           "summary": baseline_llm.summarize(h, r)}
    baseline_llm.RESULTS_PATH.write_bytes(orjson.dumps(res))
    s = res["summary"]
    print(f"SIMULATED baseline written ({len(h)} hotel + {len(r)} room pairs) -> {baseline_llm.RESULTS_PATH}\n"
          f"  hotel F1 {s['hotel_prf']['f1']:.3f} · room F1 {s['room_prf']['f1']:.3f} · "
          f"consistency violations {s['consistency_violations']} · largest wrong cluster {s['largest_wrong_cluster']}")
    return res


if __name__ == "__main__":
    run()
