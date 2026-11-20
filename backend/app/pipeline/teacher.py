"""Teach the offline parser from at most 300 unresolved room strings."""
from __future__ import annotations

from typing import Literal

import orjson
from pydantic import BaseModel

from app import config
from app.pipeline.cost import METER
from app.pipeline.normalize import (
    BED_PHRASES, BOARD_PHRASES, CLASS_PHRASES, VIEW_PHRASES, fold, learned_dictionary, parse_room,
)


class Entry(BaseModel):
    token: str
    field: Literal["class", "bed", "view", "board", "extra"]
    value: str


class Proposals(BaseModel):
    entries: list[Entry]


VOCAB = {"class": sorted(set(CLASS_PHRASES.values())), "bed": sorted(set(BED_PHRASES.values())),
         "view": sorted(set(VIEW_PHRASES.values())), "board": sorted(set(BOARD_PHRASES.values()))}


def examples():
    seen = set()
    for filename in ("rooms_raw.json", "offers_raw.json"):
        for room in orjson.loads((config.WORLD_DIR / filename).read_bytes()):
            name = room["room_name"]
            if name in seen:
                continue
            seen.add(name)
            parsed = parse_room(name)
            if parsed["needs_llm_parse"]:
                yield {"name": name, "unknown": parsed["unknown_tokens"]}


def teach():
    from itertools import islice

    if not config.LLM_ENABLED:
        print("Room dictionary teacher offline. Set ANTHROPIC_API_KEY and LLM_ENABLED=true to run it.")
        return
    pending = list(islice(examples(), 300))
    if not pending:
        print("All sampled room strings parse with the existing rules.")
        return

    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    dictionary = dict(learned_dictionary())
    before = len(dictionary)
    path = config.CACHE_DIR / "dictionary_learned.json"
    path.parent.mkdir(exist_ok=True, parents=True)
    for start in range(0, len(pending), 25):
        batch = pending[start:start + 25]
        allowed = {t for row in batch for t in row["unknown"]}
        prompt = ("Propose reusable dictionary entries for individual unknown tokens. Only propose confident "
                  "translations. For class, bed, view and board use one of these exact canonical values: "
                  + orjson.dumps(VOCAB).decode() + ". Use extra for other amenities. "
                  + orjson.dumps(batch).decode())
        result = client.messages.parse(model=config.TEACHER_MODEL, max_tokens=3000,
                                       messages=[{"role": "user", "content": prompt}], output_format=Proposals)
        METER.record(config.TEACHER_MODEL, result.usage.input_tokens, result.usage.output_tokens)
        for entry in result.parsed_output.entries if result.parsed_output else []:
            token, value = fold(entry.token).strip(), entry.value.strip()
            if token in allowed and value and (entry.field == "extra" or value in VOCAB[entry.field]):
                dictionary.setdefault(token, {"field": entry.field, "value": value})
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(orjson.dumps(dictionary, option=orjson.OPT_SORT_KEYS))
        tmp.replace(path)
        learned_dictionary.cache_clear()
    print(f"Added {len(dictionary) - before} dictionary entries from {len(pending)} room strings.")
