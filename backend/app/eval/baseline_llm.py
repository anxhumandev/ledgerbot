"""LLM-only baseline (placeholder until M10)."""
from __future__ import annotations

from app import config

RESULTS_PATH = config.CACHE_DIR / "baseline_results.json"


def baseline_cost_per_pair() -> tuple[float, bool]:
    return 0.0, False
