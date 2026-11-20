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
    if ans is None:
        raise ValueError("Baseline returned no structured decision")
    return ({"same": bool(ans.same), "confidence": int(ans.confidence)},
            dt, resp.usage.input_tokens, resp.usage.output_tokens)


def run() -> dict:
    import anthropic
    from app.pipeline.cost import price_inr
    if not config.ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY not set: the baseline is never faked. Add a key to .env and re-run.")
    from app.demo import DEMO
    from app.services.arena import build_sets

    DEMO.load()
    sets = build_sets()
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prev = load_results() or {}
    same_model = prev.get("model") == config.BASELINE_MODEL
    results = {"hotel": {}, "room": {}}
    for kind, saved in results.items():
        requested = {row["pair_id"]: row for row in sets[kind]}
        for row in prev.get(kind, []) if same_model else []:
            reference = requested.get(row["pair_id"])
            if reference and all(row.get(k) == v for k, v in reference.items()):
                saved[row["pair_id"]] = row

    def checkpoint():
        hotel = [results["hotel"][x["pair_id"]] for x in sets["hotel"] if x["pair_id"] in results["hotel"]]
        room = [results["room"][x["pair_id"]] for x in sets["room"] if x["pair_id"] in results["room"]]
        res = {"run_at": time.strftime("%Y-%m-%d %H:%M"), "model": config.BASELINE_MODEL,
               "world_digest": DEMO.state.get("world_digest"), "hotel": hotel, "room": room,
               "complete": all(len(results[k]) == len(sets[k]) for k in results),
               "summary": summarize(hotel, room)}
        tmp = RESULTS_PATH.with_suffix(".tmp")
        tmp.write_bytes(orjson.dumps(res))
        tmp.replace(RESULTS_PATH)
        return res

    for kind, saved in results.items():
        for item in sets[kind]:
            if item["pair_id"] in saved:
                continue
            if kind == "hotel":
                prompt = ("Are these the same hotel? Answer JSON {same: bool, confidence: 0-100}."
                          f"\n\nListing A:\n{_fmt(item['a'])}\n\nListing B:\n{_fmt(item['b'])}")
            else:
                def fmt_offer(record):
                    return (f"room '{record['room_name']}', board '{record['board_raw']}', "
                            f"cancellation '{record['cancellation_raw']}', "
                            f"occupancy {record.get('occupancy', 'unspecified')}, nights {record.get('nights', 'unspecified')}")
                prompt = ("Two supplier rate offers for the same hotel. Are these the same bookable room offer "
                          "(same room, board, cancellation terms, occupancy and nights)? "
                          f"Answer JSON {{same: bool, confidence: 0-100}}.\n\nA: {fmt_offer(item['a'])}"
                          f"\nB: {fmt_offer(item['b'])}")
            try:
                ans, dt, i, o = _ask(client, prompt)
            except Exception as exc:
                checkpoint()
                raise SystemExit(f"Baseline stopped on {kind} pair {item['pair_id']} ({type(exc).__name__}); "
                                 "rerun to resume.") from exc
            saved[item["pair_id"]] = {**item, **ans, "latency_s": dt, "input_tokens": i, "output_tokens": o,
                                      "cost_inr": price_inr(config.BASELINE_MODEL, i, o)}
            checkpoint()
    res = checkpoint()
    print(f"baseline written: {len(res['hotel'])} hotel pairs, {len(res['room'])} room pairs -> {RESULTS_PATH}")
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
            if len(xs) >= 10:
                bins.append({"confidence": (lo + 5) / 100, "accuracy": float(np.mean([x["same"] == bool(x["label"]) for x in xs])), "n": len(xs)})
        out["reliability"] = bins
    if room:
        out["room_prf"] = decision_prf([x["same"] for x in room], [x["label"] for x in room])
    return out


if __name__ == "__main__":
    run()
