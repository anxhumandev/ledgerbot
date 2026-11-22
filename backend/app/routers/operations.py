"""Enterprise operations API: suppliers, ingestion, offer intelligence, ranking and simulations."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app import audit, config
from app.demo import DEMO
from app.errors import ApiError
from app.identity import User, require
from app.services import ingestion, offers_svc, ranking_svc, settings_svc, suppliers_ops

router = APIRouter()


# ---------------------------------------------------------------- suppliers
@router.get("/ops/suppliers")
def suppliers():
    return {"items": suppliers_ops.directory()}


@router.get("/ops/suppliers/{code}")
def supplier(code: str):
    return suppliers_ops.detail(code)


@router.get("/ops/suppliers/{code}/listings")
def supplier_listings(code: str, q: str = "", issues_only: bool = False, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
    return suppliers_ops.listings(code, q, issues_only, page, page_size)


@router.get("/ops/suppliers/{code}/reliability")
def supplier_reliability(code: str):
    return suppliers_ops.reliability_history(code)


class SupplierConfigBody(BaseModel):
    status: str | None = None
    notes: str | None = None
    reason: str | None = None


@router.patch("/ops/suppliers/{code}/config")
def supplier_config(code: str, body: SupplierConfigBody, user: User = Depends(require("supplier.configure"))):
    return settings_svc.set_supplier_config(code, body.status, body.notes, user, body.reason)


# ---------------------------------------------------------------- simulation (what-if, labelled simulated)
class FaultBody(BaseModel):
    mode: str = "price_jump"
    severity: float = Field(0.35, ge=0.05, le=0.9)


@router.get("/ops/simulation")
def simulation():
    return suppliers_ops.simulation_state()


@router.post("/ops/simulation/stream")
async def stream(user: User = Depends(require("simulation.run"))):
    from app.services.simulator import SIM
    await SIM.start()
    return suppliers_ops.simulation_state()


@router.post("/ops/simulation/stream/stop")
def stream_stop(user: User = Depends(require("simulation.run"))):
    from app.services.simulator import SIM
    SIM.stop()
    return suppliers_ops.simulation_state()


@router.post("/ops/suppliers/{code}/simulate")
async def simulate(code: str, body: FaultBody, user: User = Depends(require("simulation.run"))):
    from app.services.simulator import SIM
    state = suppliers_ops.simulate(code, body.mode, body.severity, user)
    await SIM.start()
    return state


@router.post("/ops/simulation/heal")
def heal(user: User = Depends(require("simulation.run"))):
    return suppliers_ops.heal(user)


class ReplayBody(BaseModel):
    n: int = Field(config.REPLAY_N, ge=1000, le=200_000)


@router.post("/ops/simulation/replay")
async def replay(body: ReplayBody, user: User = Depends(require("simulation.run"))):
    from app.services.simulator import REPLAY
    res = await REPLAY.start(body.n)
    audit.record(user, "simulation.replay_started", "workspace", "replay", after={"searches": body.n})
    return res


@router.get("/ops/simulation/replay")
def replay_state():
    from app.services.simulator import REPLAY
    return {"running": REPLAY.running(), "last": getattr(DEMO, "last_replay", None)}


# ---------------------------------------------------------------- ingestion
@router.get("/ingestion/jobs")
def jobs(supplier: str = "", page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    return ingestion.list_jobs(supplier, page, page_size)


@router.get("/ingestion/jobs/{jid}")
def job(jid: str):
    return ingestion.get_job(jid)


@router.post("/ingestion/jobs")
async def create_job(supplier: str = Form(...), file: UploadFile = File(...), user: User = Depends(require("ingestion.run"))):
    raw = await file.read(config.MAX_UPLOAD_BYTES + 1)
    return ingestion.create_job(supplier, file.filename or "upload", raw, user)


@router.post("/ingestion/jobs/{jid}/start")
def start_job(jid: str, user: User = Depends(require("ingestion.run"))):
    return ingestion.start(jid, user)


@router.post("/ingestion/jobs/{jid}/retry")
def retry_job(jid: str, user: User = Depends(require("ingestion.run"))):
    return ingestion.start(jid, user, retry=True)


@router.get("/ingestion/sample")
def sample(format: str = Query("json", pattern="^(json|csv)$")):
    body, name, ctype = ingestion.sample_feed(format)
    return Response(body, media_type=ctype, headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---------------------------------------------------------------- offers
@router.get("/offers/search")
def offer_search(type: str = Query("hotel", pattern="^(hotel|activity)$"), q: str = "", city: str = "", limit: int = Query(20, ge=1, le=100)):
    return offers_svc.search(type, q, city, limit)


@router.get("/offers/hotel/{tid}")
def hotel_offers(tid: str, nights: int = Query(3, ge=1, le=30), board: str = "", refundable: str = Query("", pattern="^(|yes|no)$"),
                 payment: str = Query("", pattern="^(|prepay|pay_later)$"), supplier: str = ""):
    return offers_svc.hotel_offers(tid, nights, board, refundable, payment, supplier)


@router.get("/offers/activity/{pid}")
def activity_offers(pid: str, supplier: str = ""):
    return offers_svc.activity_offers(pid, supplier)


# ---------------------------------------------------------------- ranking
@router.get("/ranking/options")
def ranking_options():
    return {"personas": ranking_svc.personas(), "areas": ranking_svc.areas(),
            "hotel_strategies": ranking_svc.HOTEL_STRATEGIES, "activity_strategies": ranking_svc.ACTIVITY_STRATEGIES,
            "weights": settings_svc.get("rank_weights"), "guardrail": config.KENDALL_GUARDRAIL,
            "ndcg": DEMO.ranking["ndcg"], "sessions": DEMO.ranking.get("n_sessions")}


@router.get("/ranking/hotels")
def ranking_hotels(persona: str = "riya", strategy: str = "relevance", area: str = "", q: str = "", min_stars: int = Query(0, ge=0, le=5),
                   offer_policy: str = Query("expected_value", pattern="^(expected_value|cheapest)$")):
    return ranking_svc.hotels(persona, strategy, area, q, min_stars, offer_policy)


@router.get("/ranking/compare")
def ranking_compare(persona: str = "riya", a: str = "relevance", b: str = "balanced", area: str = "", q: str = "",
                    offer_a: str = Query("expected_value", pattern="^(expected_value|cheapest)$"),
                    offer_b: str = Query("expected_value", pattern="^(expected_value|cheapest)$")):
    return ranking_svc.compare(persona, a, b, area, q, offer_a, offer_b)


@router.get("/ranking/activities")
def ranking_activities(q: str = "", city: str = "", strategy: str = "relevance"):
    return ranking_svc.activities(q, city, strategy)
