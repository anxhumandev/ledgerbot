"""LLM adjudicator for the uncertain band only. Batched (10 pairs/call), cached by pair hash.

If LLM_ENABLED is false or no key is configured, uncertain pairs route straight to human review.
"""
from __future__ import annotations

import hashlib
import threading
import time
from typing import Literal

import orjson
from pydantic import BaseModel, Field

from app import config
from app.pipeline.cost import METER

CACHE_PATH = config.CACHE_DIR / "adjudicator.json"
_LOCK = threading.Lock()
BATCH = 10

SYSTEM = (
    "You are a hotel content-mapping specialist for a B2B travel marketplace. For each pair of supplier "
    "listings decide whether they describe the SAME physical property. Different buildings of the same brand, "
    "sister properties and sub-brands (e.g. 'The Palm' vs 'The Royal', 'Garden Inn' vs the main brand) are "
    "DIFFERENT. Spelling noise, abbreviations, city suffixes, marketing suffixes, phone formats and small "
    "coordinate offsets do not make listings different. Answer 'unsure' when the evidence genuinely conflicts. "
    "Keep each reason under 20 words."
)


class Verdict(BaseModel):
    pair_id: str
    verdict: Literal["same", "different", "unsure"]
    reason: str = Field(description="At most 20 words")


class Verdicts(BaseModel):
    results: list[Verdict]


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return orjson.loads(CACHE_PATH.read_bytes())
        except Exception:
            return {}
    return {}


_CACHE = _load_cache()


def pair_hash(a: dict, b: dict) -> str:
    keys = ("name", "address", "phone", "lat", "lng", "stars")
    blob = orjson.dumps([{k: a.get(k) for k in keys}, {k: b.get(k) for k in keys}], option=orjson.OPT_SORT_KEYS)
    return hashlib.sha1(blob).hexdigest()[:16]


def _render(item: dict) -> str:
    a, b = item["a"], item["b"]

    def rec(r):
        return (f"name: {r.get('name')} | address: {r.get('address') or '—'} | phone: {r.get('phone') or '—'} | "
                f"stars: {r.get('stars')} | lat,lng: {r.get('lat')},{r.get('lng')}")
    diffs = []
    for k in ("name", "address", "phone", "stars"):
        if (a.get(k) or "") != (b.get(k) or ""):
            diffs.append(k)
    return f"pair_id: {item['pair_id']}\n  A: {rec(a)}\n  B: {rec(b)}\n  differing fields: {', '.join(diffs) or 'none'}"


def _call(batch: list[dict]) -> list[dict]:
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prompt = "Decide each pair. Return one result per pair_id.\n\n" + "\n\n".join(_render(x) for x in batch)
    t0 = time.time()
    resp = client.messages.parse(
        model=config.ADJUDICATOR_MODEL, max_tokens=4000, system=SYSTEM,
        messages=[{"role": "user", "content": prompt}], output_format=Verdicts,
    )
    dt = time.time() - t0
    METER.record(config.ADJUDICATOR_MODEL, resp.usage.input_tokens, resp.usage.output_tokens, pairs=len(batch))
    parsed = resp.parsed_output
    out = {v.pair_id: v for v in (parsed.results if parsed else [])}
    res = []
    for x in batch:
        v = out.get(x["pair_id"])
        res.append({"pair_id": x["pair_id"], "verdict": v.verdict if v else "unsure",
                    "reason": (v.reason if v else "no answer returned")[:160], "latency_s": dt / len(batch),
                    "model": config.ADJUDICATOR_MODEL})
    return res


def _route(item: dict, v: dict) -> dict:
    """'unsure' or a contradiction with a strong feature -> human review."""
    out = dict(v)
    if v["verdict"] == "unsure":
        out["route"] = "review"
    elif v["verdict"] == "same" and item.get("subbrand_conflict"):
        out["route"] = "review"
        out["reason"] = v["reason"] + " (contradicts sub-brand conflict → review)"
    else:
        out["route"] = "llm"
    return out


def adjudicate(items: list[dict], allow_calls: bool | None = None) -> dict[str, dict]:
    """Returns {pair_id: {verdict, reason, route}}. Missing => not adjudicated (LLM offline)."""
    allow = config.LLM_ENABLED if allow_calls is None else (allow_calls and config.LLM_ENABLED)
    results, todo = {}, []
    for it in items:
        h = pair_hash(it["a"], it["b"])
        it["_h"] = h
        if h in _CACHE:
            v = dict(_CACHE[h], pair_id=it["pair_id"])
            METER.cache_hit()
            results[it["pair_id"]] = _route(it, v)
        else:
            todo.append(it)
    if allow and todo:
        for s in range(0, len(todo), BATCH):
            batch = todo[s:s + BATCH]
            try:
                vs = _call(batch)
            except Exception as e:  # network/API failure -> review, never crash the demo
                print(f"  adjudicator call failed: {type(e).__name__}: {e}")
                break
            for it, v in zip(batch, vs):
                with _LOCK:
                    _CACHE[it["_h"]] = {k: v[k] for k in ("verdict", "reason", "latency_s", "model")}
                results[it["pair_id"]] = _route(it, v)
        with _LOCK:
            CACHE_PATH.write_bytes(orjson.dumps(_CACHE))
    return results


def status() -> dict:
    return {"enabled": config.LLM_ENABLED, "model": config.ADJUDICATOR_MODEL, "cached": len(_CACHE),
            "reason": None if config.LLM_ENABLED else ("LLM_ENABLED=false" if config.ANTHROPIC_API_KEY else "no ANTHROPIC_API_KEY")}
