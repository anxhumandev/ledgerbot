"""Token + rupee cost meter for every LLM call LedgerBot makes."""
from __future__ import annotations

import threading

import orjson

from app import config

_LOCK = threading.Lock()
_PATH = config.CACHE_DIR / "cost_ledger.json"


def price_inr(model: str, input_tokens: int, output_tokens: int) -> float:
    pr = config.LLM_PRICING_USD_PER_MTOK.get(model, {"input": 0.0, "output": 0.0})
    usd = input_tokens / 1e6 * pr["input"] + output_tokens / 1e6 * pr["output"]
    return usd * config.USD_TO_INR


class CostMeter:
    def __init__(self):
        self.reset()
        if _PATH.exists():
            try:
                d = orjson.loads(_PATH.read_bytes())
                self.lifetime = d.get("lifetime", self.lifetime)
            except Exception:
                pass

    def reset(self):
        self.session = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "inr": 0.0, "pairs_processed": 0,
                        "llm_pairs": 0, "cache_hits": 0}
        self.lifetime = getattr(self, "lifetime", {"calls": 0, "input_tokens": 0, "output_tokens": 0, "inr": 0.0})

    def record(self, model: str, input_tokens: int, output_tokens: int, pairs: int = 0) -> float:
        inr = price_inr(model, input_tokens, output_tokens)
        with _LOCK:
            for d in (self.session, self.lifetime):
                d["calls"] += 1
                d["input_tokens"] += input_tokens
                d["output_tokens"] += output_tokens
                d["inr"] += inr
            self.session["llm_pairs"] += pairs
            try:
                _PATH.write_bytes(orjson.dumps({"lifetime": self.lifetime}))
            except Exception:
                pass
        return inr

    def add_pairs(self, n: int):
        with _LOCK:
            self.session["pairs_processed"] += n

    def cache_hit(self, n: int = 1):
        with _LOCK:
            self.session["cache_hits"] += n

    def snapshot(self) -> dict:
        from app.eval.baseline_llm import baseline_cost_per_pair
        per_pair, measured = baseline_cost_per_pair()
        n = self.session["pairs_processed"]
        return {
            "tessera_llm_spend_inr": round(self.session["inr"], 4),
            "llm_only_counterfactual_inr": round(n * per_pair, 2),
            "counterfactual_estimated": not measured,
            "pairs_processed": n, "llm_pairs": self.session["llm_pairs"], "calls": self.session["calls"],
            "cache_hits": self.session["cache_hits"], "lifetime_inr": round(self.lifetime["inr"], 4),
            "llm_enabled": config.LLM_ENABLED,
        }


METER = CostMeter()
