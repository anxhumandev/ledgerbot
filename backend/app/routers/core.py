"""Health, demo reset, world summary, cost, listings, clusters, activities, metrics."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

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


@router.post("/demo/reset")
async def reset():
    from app.services.live import ONBOARDER
    from app.services.simulator import REPLAY, SIM
    from app.services.vote import VOTE
    ONBOARDER.cancel()
    REPLAY.stop()
    SIM.stop()
    DEMO.reset()
    SIM.reset()
    VOTE.reset()
    from app.ws import HUB
    await HUB.broadcast("vote", "reset", {"session": VOTE.session})
    DEMO.last_replay = None
    return {"ok": True, "epoch": DEMO.reset_epoch}


@router.get("/world/summary")
def summary():
    return views.summary()


@router.get("/world/cold-open")
def cold_open():
    return views.cold_open()


@router.get("/cost")
def cost():
    return METER.snapshot()


@router.get("/listings")
def listings(area: str = "marina", strategy: str = "cheapest", nights: int = 3):
    return views.listings(area, strategy, nights)


@router.get("/clusters/featured")
def featured():
    return views.featured()


@router.get("/clusters/near-miss")
def near_miss():
    return views.near_miss()


@router.get("/clusters/{tid}")
def cluster(tid: str):
    if tid not in DEMO.hotels:
        raise HTTPException(404, "unknown tessera id")
    return views.cluster_detail(tid)


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
