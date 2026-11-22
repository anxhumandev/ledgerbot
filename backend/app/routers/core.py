"""Health, world summary, cost meter, sightseeing products and pipeline metrics."""
from __future__ import annotations

from fastapi import APIRouter

from app import config
from app.demo import DEMO
from app.pipeline import adjudicator
from app.pipeline.cost import METER
from app.services import views

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": DEMO.ready, "error": DEMO.error, "llm": adjudicator.status(),
            "world": DEMO.state.get("world") if DEMO.ready else None, "alpha": getattr(DEMO, "alpha", None)}


@router.get("/world/summary")
def summary():
    return views.summary()


@router.get("/cost")
def cost():
    return METER.snapshot()


@router.get("/activities")
def activities():
    return views.activities()


@router.get("/metrics")
def metrics():
    s = DEMO.state
    return {"blocking": s["blocking"], "evals": s["evals"], "consistency": s["consistency"], "routes": s["routes"],
            "room_eval": s["room_eval"], "offer_eval": s["offer_eval"], "activity_eval": s["activity_eval"],
            "dup_stats": s["dup_stats"], "trust": s["trust"], "ranking_ndcg": DEMO.ranking["ndcg"],
            "risk": {k: v for k, v in s["risk"].items() if k != "curve"}, "curve": s["risk"]["curve"],
            "config": {"alpha": DEMO.alpha, "delta": config.RISK_DELTA, "beta": config.DEFAULT_BETA}}
