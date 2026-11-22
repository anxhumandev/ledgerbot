"""Central configuration. Everything tunable lives here; secrets come from .env only."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
load_dotenv(ROOT_DIR / ".env")

DATA_DIR = BACKEND_DIR / "data"
WORLD_DIR = DATA_DIR / "world"
CACHE_DIR = DATA_DIR / "cache"
FRONTEND_PUBLIC = ROOT_DIR / "frontend" / "public"
IMG_BASE_DIR = FRONTEND_PUBLIC / "img" / "base"
IMG_VAR_DIR = FRONTEND_PUBLIC / "img" / "var"

SEED = int(os.getenv("SEED", "42"))
# "demo" = Dubai only; "large" = Dubai + 4 more cities. The risk dial needs the large
# world's calibration volume to certify alpha < 1% (use WORLD=large for recording).
WORLD = os.getenv("WORLD", "demo").lower()

# ---------------------------------------------------------------- LLM
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() == "true" and bool(ANTHROPIC_API_KEY)
ADJUDICATOR_MODEL = os.getenv("ADJUDICATOR_MODEL", "claude-haiku-5-5")
BASELINE_MODEL = os.getenv("BASELINE_MODEL", "claude-opus-5-5")
TEACHER_MODEL = os.getenv("TEACHER_MODEL", "claude-opus-5-5")

# Simulated LLM-only baseline (no API key). ASSUMPTIONS, not measurements: the share of each pair
# kind a zero-shot pairwise LLM gets wrong. Which pairs err is chosen by observable difficulty
# (name similarity, distance), so the errors land on realistic cases. Every screen that shows these
# results labels them "simulated"; a real `make baseline` run replaces them.
SIM_BASELINE = {
    "hotel_hard_negative_false_merge": 0.20,  # sister / same-brand nearby properties called "same"
    "hotel_negative_false_merge": 0.01,       # ordinary non-matches called "same"
    "hotel_positive_miss": 0.06,              # noisy true matches called "different"
    "room_diff_terms_false_merge": 0.30,      # same room, different board/cancellation called "same offer"
    "room_diff_room_false_merge": 0.08,       # different physical rooms called "same offer"
    "room_same_offer_miss": 0.10,             # identical offers in different wording called "different"
    "latency_median_s": 1.6,                  # per pair, one call per pair
    "latency_sigma": 0.45,                    # lognormal spread
    "seed": 7,
}

# USD per million tokens. Source: Anthropic model pricing table (cached 2026-10-06),
# first-party API rates. Update here if pricing changes.
LLM_PRICING_USD_PER_MTOK = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50},
    "claude-opus-5-5": {"input": 4.00, "output": 20.00},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00},
}
USD_TO_INR = float(os.getenv("USD_TO_INR", "84.0"))

# ---------------------------------------------------------------- Suppliers
SUPPLIERS = {
    "S1": {"name": "DirectConnect", "persona": "TBO direct contracts", "color": "#014C8E",
           "take_rate": 0.12, "profile": {"confirm": 0.993, "price_jump": 0.005, "latency": 1.2}},
    "S2": {"name": "GlobalBeds", "persona": "Big bed bank", "color": "#8A6D3B",
           "take_rate": 0.09, "profile": {"confirm": 0.975, "price_jump": 0.04, "latency": 2.8}},
    "S3": {"name": "IberiaBeds", "persona": "Spanish wholesaler", "color": "#A23B72",
           "take_rate": 0.095, "profile": {"confirm": 0.986, "price_jump": 0.015, "latency": 1.9}},
    "S4": {"name": "LuxeCollection", "persona": "Luxury specialist", "color": "#2F7F86",
           "take_rate": 0.10, "profile": {"confirm": 0.990, "price_jump": 0.01, "latency": 1.5}},
    "S5": {"name": "RapidStay", "persona": "Aggregator of aggregators", "color": "#6B7A2E",
           "take_rate": 0.08, "profile": {"confirm": 0.958, "price_jump": 0.06, "latency": 3.9}},
    "S6": {"name": "NovaBeds", "persona": "New supplier (live onboarding)", "color": "#E8590C",
           "take_rate": 0.09, "profile": {"confirm": 0.980, "price_jump": 0.025, "latency": 2.2}},
}
ACTIVE_SUPPLIERS = ["S1", "S2", "S3", "S4", "S5"]

# ---------------------------------------------------------------- Offer selection (EV)
FAILURE_COST_INR = float(os.getenv("FAILURE_COST_INR", "2500"))
# P(book) = sigmoid(a - b*(price_rel - 1) + c*refundable + d*pay_later), price_rel = price / slot min
PBOOK = {"a": -1.0, "b": 6.0, "c": 0.35, "d": 0.15}
PRICE_JUMP_COST_INR = 900.0  # agent credit when price changes at booking

# ---------------------------------------------------------------- Risk control
RISK_DELTA = 0.05
RISK_ALPHA_GRID = [0.001, 0.0025, 0.005, 0.01, 0.02, 0.05]
DEFAULT_ALPHA = 0.01
DEFAULT_BETA = 0.01  # max share of true matches lost to auto-reject (1% keeps a thin review band at alpha = 1%)
REVIEW_MINUTES_PER_PAIR = 1.5
REVIEW_COST_INR_PER_HOUR = 450.0
PAIRS_PER_MONTH = 1_200_000  # illustrative volume for the ops-cost stat

# ---------------------------------------------------------------- Ranking
RANK_WEIGHTS = {"margin": 0.25, "platinum": 0.15, "risk": 0.4}
KENDALL_GUARDRAIL = 0.8

# ---------------------------------------------------------------- Simulation
BOOKINGS_PER_SEC = 15
REPLAY_N = 50_000
TBO_ANNUAL_HOTEL_GTV_INR = 31_500 * 1e7  # ₹31,500 Cr (TBO Q2 FY27 results)
TBO_GROSS_MARGIN = 0.06
ONBOARD_PACE_MS = int(os.getenv("ONBOARD_PACE_MS", "40"))
PUBLIC_HOST = os.getenv("PUBLIC_HOST", "")
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "5174"))


def ensure_dirs() -> None:
    for d in (WORLD_DIR, CACHE_DIR, IMG_BASE_DIR, IMG_VAR_DIR):
        d.mkdir(parents=True, exist_ok=True)
