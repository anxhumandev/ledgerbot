"""LLM-only baseline: a frontier model asked zero-shot, one pair per call. Run once, cached, never faked.

    python -m app.eval.baseline_llm          # needs ANTHROPIC_API_KEY; writes cache/baseline_results.json
"""
from __future__ import annotations

import time

import orjson
from pydantic import BaseModel, Field

from app import config

RESULTS_PATH = config.CACHE_DIR / "baseline_results.json"
SETS_PATH = config.CACHE_DIR / "arena_sets.json"
EST_INPUT_TOKENS, EST_OUTPUT_TOKENS = 260, 30


class PairAnswer(BaseModel):
    same: bool
    confidence: int = Field(ge=0, le=100, description="0-100")


def load_results() -> dict | None:
    if RESULTS_PATH.exists():
        try:
            return orjson.loads(RESULTS_PATH.read_bytes())
        except Exception:
            return None
    return None


def baseline_cost_per_pair() -> tuple[float, bool]:
    """(INR per pair, measured?)"""
    r = load_results()
    if r and r.get("summary", {}).get("hotel_cost_per_pair_inr") is not None:
        return float(r["summary"]["hotel_cost_per_pair_inr"]), True
    from app.pipeline.cost import price_inr
    return price_inr(config.BASELINE_MODEL, EST_INPUT_TOKENS, EST_OUTPUT_TOKENS), False


def _fmt(r: dict) -> str:
    return (f"name: {r.get('name')}\naddress: {r.get('address') or '—'}\nphone: {r.get('phone') or '—'}\n"
            f"stars: {r.get('stars')}\nlat,lng: {r.get('lat')},{r.get('lng')}")


def _ask(client, prompt: str) -> tuple[dict, float, int, int]:
    t0 = time.time()
    resp = client.messages.parse(model=config.BASELINE_MODEL, max_tokens=2000,
                                 messages=[{"role": "user", "content": prompt}], output_format=PairAnswer)
    dt = time.time() - t0
    ans = resp.parsed_output
    return ({"same": bool(ans.same), "confidence": int(ans.confidence)} if ans else {"same": False, "confidence": 0},
            dt, resp.usage.input_tokens, resp.usage.output_tokens)


def run() -> dict:
    import anthropic
    from app.pipeline.cost import price_inr
    if not config.ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY not set: the baseline is never faked. Add a key to .env and re-run.")
    sets = orjson.loads(SETS_PATH.read_bytes())
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prev = load_results() or {}
    done_h = {x["pair_id"]: x for x in prev.get("hotel", [])}
    done_r = {x["pair_id"]: x for x in prev.get("room", [])}
    hotel, room = [], []
    for k, it in enumerate(sets["hotel"]):
        if it["pair_id"] in done_h:
            hotel.append(done_h[it["pair_id"]])
            continue
        prompt = ("Are these the same hotel? Answer JSON {same: bool, confidence: 0-100}.\n\nListing A:\n"
                  f"{_fmt(it['a'])}\n\nListing B:\n{_fmt(it['b'])}")
        try:
            ans, dt, i, o = _ask(client, prompt)
        except Exception as e:
            print(f"  call failed ({type(e).__name__}); stopping, partial results kept")
            break
        hotel.append({**it, **ans, "latency_s": dt, "input_tokens": i, "output_tokens": o, "cost_inr": price_inr(config.BASELINE_MODEL, i, o)})
        if k % 20 == 0:
            print(f"  hotel pairs {k + 1}/{len(sets['hotel'])}")
    for k, it in enumerate(sets["room"]):
        if it["pair_id"] in done_r:
            room.append(done_r[it["pair_id"]])
            continue
        prompt = ("Two supplier rate offers for the same hotel. Are these the same bookable room offer, i.e. should "
                  "they be merged into one listing? Answer JSON {same: bool, confidence: 0-100}.\n\n"
                  f"Offer A: room '{it['a']['room_name']}', board '{it['a']['board_raw']}', cancellation '{it['a']['cancellation_raw']}'\n"
                  f"Offer B: room '{it['b']['room_name']}', board '{it['b']['board_raw']}', cancellation '{it['b']['cancellation_raw']}'")
        try:
            ans, dt, i, o = _ask(client, prompt)
        except Exception as e:
            print(f"  call failed ({type(e).__name__}); stopping, partial results kept")
            break
        room.append({**it, **ans, "latency_s": dt, "input_tokens": i, "output_tokens": o, "cost_inr": price_inr(config.BASELINE_MODEL, i, o)})
    res = {"run_at": time.strftime("%Y-%m-%d %H:%M"), "model": config.BASELINE_MODEL, "hotel": hotel, "room": room,
           "summary": summarize(hotel, room)}
    RESULTS_PATH.write_bytes(orjson.dumps(res))
    print(f"baseline written: {len(hotel)} hotel pairs, {len(room)} room pairs -> {RESULTS_PATH}")
    return res


def summarize(hotel: list[dict], room: list[dict]) -> dict:
    import numpy as np

    from app.eval.metrics import decision_prf, percentiles
    out = {}
    if hotel:
        out["hotel_prf"] = decision_prf([x["same"] for x in hotel], [x["label"] for x in hotel])
        out["hotel_cost_per_pair_inr"] = float(np.mean([x["cost_inr"] for x in hotel]))
        out["hotel_latency"] = percentiles([x["latency_s"] for x in hotel])
        # transitive closure of "same" answers
        parent = {}

        def f(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for x in hotel:
            f(x["a"]["record_id"]), f(x["b"]["record_id"])
            if x["same"]:
                parent[f(x["a"]["record_id"])] = f(x["b"]["record_id"])
        comp = {}
        for r in parent:
            comp.setdefault(f(r), []).append(r)
        sup = {x["a"]["record_id"]: x["a"]["supplier"] for x in hotel} | {x["b"]["record_id"]: x["b"]["supplier"] for x in hotel}
        hot = {x["a"]["record_id"]: x["a"]["true_hotel"] for x in hotel} | {x["b"]["record_id"]: x["b"]["true_hotel"] for x in hotel}
        trans = sum(1 for x in hotel if not x["same"] and f(x["a"]["record_id"]) == f(x["b"]["record_id"]))
        excl = sum(len(v) - len({sup[m] for m in v}) for v in comp.values())
        wrong = [len(v) for v in comp.values() if len({hot[m] for m in v}) > 1]
        out.update({"transitivity_violations": trans, "supplier_exclusivity_violations": excl,
                    "consistency_violations": trans + excl, "largest_wrong_cluster": max(wrong, default=0)})
        # reliability diagram: stated confidence vs accuracy
        bins = []
        for lo in range(50, 100, 10):
            xs = [x for x in hotel if lo <= x["confidence"] < lo + 10 or (lo == 90 and x["confidence"] == 100)]
            if xs:
                bins.append({"confidence": (lo + 5) / 100, "accuracy": float(np.mean([x["same"] == bool(x["label"]) for x in xs])), "n": len(xs)})
        out["reliability"] = bins
    if room:
        out["room_prf"] = decision_prf([x["same"] for x in room], [x["label"] for x in room])
    return out


if __name__ == "__main__":
    run()
