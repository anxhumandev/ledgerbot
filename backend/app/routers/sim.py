"""Suppliers, simulator, ranking, arena, voting."""
from __future__ import annotations

import asyncio
import socket

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import config
from app.demo import DEMO
from app.pipeline import ranking
from app.services import arena
from app.services.simulator import REPLAY, SIM
from app.services.vote import VOTE

router = APIRouter()


class Sabotage(BaseModel):
    supplier: str
    mode: str = "price_jump"
    severity: float = 0.35


@router.get("/suppliers")
def suppliers():
    return {"suppliers": DEMO.reliability.snapshot(), "sabotage": DEMO.sabotage, "running": SIM.running()}


@router.post("/sim/start")
async def sim_start():
    return await SIM.start()


@router.post("/sim/stop")
def sim_stop():
    SIM.stop()
    return {"status": "stopped"}


@router.get("/sim/showcase")
def showcase():
    if not SIM.showcase:
        SIM.prepare()
    return {"cards": SIM.showcase_view(), "toast": SIM.last_toast}


@router.post("/sim/sabotage")
def sabotage(body: Sabotage):
    if body.supplier not in config.SUPPLIERS or body.mode not in ("price_jump", "timeouts", "failures"):
        raise HTTPException(400, "bad sabotage request")
    SIM.sabotage(body.supplier, body.mode, body.severity)
    return {"sabotage": DEMO.sabotage}


@router.post("/sim/heal")
def heal():
    SIM.heal()
    return {"sabotage": DEMO.sabotage}


class ReplayBody(BaseModel):
    n: int = config.REPLAY_N


@router.post("/sim/replay")
async def replay(body: ReplayBody | None = None):
    n = body.n if body else config.REPLAY_N
    return await REPLAY.start(min(max(n, 1000), 200_000))


@router.get("/sim/replay")
def replay_state():
    return {"running": REPLAY.running(), "last": getattr(DEMO, "last_replay", None)}


@router.get("/ranking")
def get_ranking(persona: str = "riya", mode: str = "relevance"):
    if persona not in ranking.PERSONA:
        raise HTTPException(404, "unknown persona")
    rel = {c: DEMO.reliability.get(c).score for c in config.SUPPLIERS}
    res = ranking.rank(persona, mode, DEMO.hotel_table, DEMO.ranking, rel)
    res["proof"] = {"ndcg_naive": DEMO.ranking["ndcg"]["naive"], "ndcg_ipw": DEMO.ranking["ndcg"]["ipw"],
                    "eta": DEMO.ranking["eta"], "n_sessions": DEMO.ranking["n_sessions"],
                    "n_randomized": DEMO.ranking["n_randomized"]}
    return res


@router.get("/personas")
def personas():
    return list(ranking.PERSONA.values())


@router.get("/arena/benchmark")
async def bench():
    return await asyncio.to_thread(arena.benchmark)


@router.get("/arena/corner-cases")
def corners():
    return arena.corner_cases()


def lan_ip() -> str:
    if config.PUBLIC_HOST:
        return config.PUBLIC_HOST
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@router.post("/vote/session")
def vote_session():
    st = VOTE.state()
    return {**st, "url": f"http://{lan_ip()}:{config.FRONTEND_PORT}/vote?s={VOTE.session}"}


@router.get("/vote/state")
def vote_state():
    return VOTE.state()


@router.post("/vote/next")
async def vote_next():
    return await VOTE.next()


@router.post("/vote/reveal")
async def vote_reveal():
    return await VOTE.reveal()


class Cast(BaseModel):
    nickname: str
    idx: int
    answer: str
    session: str | None = None


@router.post("/vote/cast")
async def vote_cast(body: Cast):
    if body.session and body.session != VOTE.session:
        return {"ok": False, "reason": "stale session"}
    return await VOTE.cast(body.nickname, body.idx, body.answer)


@router.post("/vote/learn")
async def vote_learn():
    return await asyncio.to_thread(VOTE.learn)
