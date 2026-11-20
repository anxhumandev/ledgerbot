"""Onboarding stream, Break-It trace, graph, risk control."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from app.demo import DEMO
from app.services.live import ONBOARDER, graph, presets, trace

router = APIRouter()


class SingleRecord(BaseModel):
    name: str = ""
    address: str | None = None
    lat: float | str | None = None
    lng: float | str | None = None
    phone: str | None = None
    room_name: str | None = None
    city: str | None = "Dubai"


@router.post("/pipeline/onboard")
async def onboard():
    return await ONBOARDER.start()


@router.get("/pipeline/onboard")
def onboard_state():
    return {"feed": ONBOARDER.feed_summary(), "state": DEMO.onboarding}


@router.post("/pipeline/single")
async def single(rec: SingleRecord):
    return await asyncio.to_thread(trace, rec.model_dump())


@router.get("/pipeline/presets")
def get_presets():
    return presets()


@router.get("/graph")
def get_graph(city: str = "dubai"):
    return graph(city)


@router.get("/risk/curve")
def risk_curve():
    s = DEMO.state["risk"]
    return {"grid": s["curve"], "dense": DEMO.dense_curve, "current": DEMO.current_risk, "alpha": DEMO.alpha,
            "cal_n": s["cal_n"], "cal_units": s["cal_units"], "test_units": s["test_units"], "delta": s["delta"],
            "beta": s["beta"]}


@router.get("/risk/at")
def risk_at(alpha: float = 0.01, apply: bool = False):
    alpha = min(0.05, max(0.001, alpha))
    return DEMO.set_alpha(alpha) if apply else DEMO.risk_at(alpha)
