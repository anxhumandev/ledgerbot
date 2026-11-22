"""Single-record match tester and the risk curve."""
from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.demo import DEMO
from app.services.live import presets, trace

router = APIRouter()


class SingleRecord(BaseModel):
    name: str
    address: str | None = None
    phone: str | None = None
    lat: float | None = None
    lng: float | None = None
    room_name: str | None = None
    city: str | None = "Dubai"


@router.post("/pipeline/single")
def single(body: SingleRecord):
    """Runs one record through the live pipeline without changing the catalog."""
    return trace(body.model_dump())


@router.get("/pipeline/presets")
def get_presets():
    return presets()


@router.get("/risk/curve")
def risk_curve():
    return {"curve": DEMO.dense_curve, "current": DEMO.current_risk, "alpha": DEMO.alpha}


@router.get("/risk/at")
def risk_at(alpha: float = Query(..., ge=0.001, le=0.05)):
    return DEMO.risk_at(alpha)
