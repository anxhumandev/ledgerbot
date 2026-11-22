"""Read-only views of supplier reliability, ranking and the LLM-only benchmark.
State-changing simulation endpoints live in routers/operations.py behind role checks."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from app import config
from app.demo import DEMO
from app.pipeline import ranking
from app.services import arena

router = APIRouter()


@router.get("/suppliers")
def suppliers():
    from app.services.simulator import SIM
    return {"suppliers": DEMO.reliability.snapshot(), "sabotage": DEMO.sabotage, "running": SIM.running()}


@router.get("/personas")
def personas():
    return list(ranking.PERSONA.values())


@router.get("/arena/benchmark")
async def bench():
    return await asyncio.to_thread(arena.benchmark)


@router.get("/arena/corner-cases")
def corners():
    return arena.corner_cases()


@router.get("/config/suppliers")
def supplier_catalog():
    return {c: {"name": s["name"], "persona": s["persona"]} for c, s in config.SUPPLIERS.items()}
