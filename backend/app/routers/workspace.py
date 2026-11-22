"""Enterprise workspace API: identity, overview, inventory, matching and review, analytics, audit, settings."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from app import audit, config, identity, store
from app.demo import DEMO
from app.errors import ApiError
from app.identity import User, current_user, require
from app.services import catalog, detail, insights, review, settings_svc

router = APIRouter()


# ---------------------------------------------------------------- identity
@router.get("/me")
def me(user: User | None = Depends(current_user)):
    return {"user": user.view() if user else None, "users": identity.list_users(), "roles": identity.ROLES,
            "workspace": {"name": settings_svc.get("workspace_name"), "mode": "demo", "data": "synthetic",
                          "auth": "Local demo identities (X-LedgerBot-User header). Not authentication."}}


@router.get("/users")
def users():
    return identity.list_users()


class RoleBody(BaseModel):
    role: str
    reason: str | None = None


@router.patch("/users/{uid}")
def set_role(uid: str, body: RoleBody, user: User = Depends(require("users.manage"))):
    if body.role not in identity.ROLES:
        raise ApiError(422, "invalid_value", "Unknown role.", {"field": "role"})
    target = identity.get_user(uid)
    if not target:
        raise ApiError(404, "not_found", "Unknown user.")
    if uid == user.id and body.role != "admin":
        raise ApiError(409, "conflict", "You cannot remove your own administrator role.")
    store.execute("UPDATE users SET role = ? WHERE id = ?", (body.role, uid))
    audit.record(user, "user.role_changed", "user", uid, before={"role": target.role}, after={"role": body.role}, reason=body.reason)
    return identity.list_users()


# ---------------------------------------------------------------- overview
@router.get("/overview")
def overview():
    return insights.overview()


# ---------------------------------------------------------------- inventory
@router.get("/inventory")
def inventory(type: str = "hotel", q: str = "", country: str = "", city: str = "", supplier: str = "", status: str = "",
              quality: str = "", conf_min: float | None = Query(None, ge=0, le=1), conf_max: float | None = Query(None, ge=0, le=1),
              sort: str = "relevance", order: str = Query("asc", pattern="^(asc|desc)$"), page: int = Query(1, ge=1),
              page_size: int = Query(25, ge=1, le=200)):
    return catalog.list_inventory(type, q, country, city, supplier, status, quality, conf_min, conf_max, sort, order, page, page_size)


@router.get("/inventory/hotel/{tid}")
def inventory_hotel(tid: str):
    return detail.hotel(tid)


@router.get("/inventory/activity/{pid}")
def inventory_activity(pid: str):
    return detail.activity(pid)


@router.get("/matching/explain")
def explain(a: str, b: str):
    return detail.explain_pair(a, b)


@router.get("/matching/policy")
def policy():
    s = DEMO.state["risk"]
    return {"alpha": DEMO.alpha, "beta": config.DEFAULT_BETA, "delta": config.RISK_DELTA, "current": DEMO.current_risk,
            "curve": DEMO.dense_curve, "calibration": {"pairs": s.get("cal_n"), "units": s.get("cal_units"), "matches": s.get("cal_matches")},
            "routes": DEMO.state["routes"], "llm_enabled": config.LLM_ENABLED, "adjudicator_model": config.ADJUDICATOR_MODEL,
            "updated": settings_svc.all_settings()["alpha"]}


@router.get("/matching/policy/preview")
def policy_preview(alpha: float = Query(..., ge=0.001, le=0.05)):
    return DEMO.risk_at(alpha)


@router.get("/matching/clusters")
def clusters(q: str = "", sort: str = "confidence", order: str = "asc", page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
    out = catalog.list_inventory("hotel", q=q, sort=sort, order=order, page=1, page_size=10_000)
    items = [r for r in out["items"] if r["n_suppliers"] >= 2]
    start = (page - 1) * page_size
    return {"items": items[start:start + page_size], "total": len(items), "page": page, "page_size": page_size}


# ---------------------------------------------------------------- review
@router.get("/review/cases")
def cases(status: str = "open,escalated", priority: str = "", assignee: str = "", q: str = "", source: str = "",
          page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    return review.list_cases(status, priority, assignee, q, source, page, page_size)


@router.get("/review/cases/{cid}")
def case(cid: str):
    return review.get_case(cid)


class DecisionBody(BaseModel):
    decision: str
    reason: str = ""
    version: int = Field(..., ge=1)


@router.post("/review/cases/{cid}/decision")
def decide(cid: str, body: DecisionBody, user: User = Depends(require("review.decide")),
           idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    return review.decide(cid, body.decision, body.reason, body.version, user, idempotency_key)


class ReasonBody(BaseModel):
    reason: str = ""


@router.post("/review/cases/{cid}/reopen")
def reopen(cid: str, body: ReasonBody, user: User = Depends(require("review.decide"))):
    return review.reopen(cid, body.reason, user)


class AssignBody(BaseModel):
    assignee: str | None = None


@router.post("/review/cases/{cid}/assign")
def assign(cid: str, body: AssignBody, user: User = Depends(require("review.assign"))):
    return review.assign(cid, body.assignee, user)


class NoteBody(BaseModel):
    body: str


@router.post("/review/cases/{cid}/notes")
def note(cid: str, body: NoteBody, user: User = Depends(require("review.note"))):
    return review.add_note(cid, body.body, user)


# ---------------------------------------------------------------- analytics and audit
@router.get("/analytics")
def analytics():
    return insights.analytics()


@router.get("/audit")
def audit_log(q: str = "", actor: str = "", action: str = "", entity_type: str = "", entity_id: str = "",
              since: float | None = None, until: float | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    return audit.search(q, actor, action, entity_type, entity_id, since, until, page, page_size)


# ---------------------------------------------------------------- settings
@router.get("/settings")
def get_settings():
    return {"settings": settings_svc.all_settings(), "beta": config.DEFAULT_BETA, "delta": config.RISK_DELTA,
            "failure_cost_inr": config.FAILURE_COST_INR, "kendall_guardrail": config.KENDALL_GUARDRAIL,
            "llm": {"enabled": config.LLM_ENABLED, "adjudicator": config.ADJUDICATOR_MODEL},
            "cors": config.ALLOWED_ORIGINS, "max_upload_mb": config.MAX_UPLOAD_BYTES // (1024 * 1024)}


class SettingBody(BaseModel):
    value: object
    reason: str | None = None


@router.put("/settings/{key}")
def put_setting(key: str, body: SettingBody, user: User | None = Depends(current_user)):
    if user is None:
        raise ApiError(401, "unauthenticated", "Choose a workspace identity before making changes.")
    return settings_svc.update(key, body.value, user, body.reason)


@router.post("/workspace/reset")
async def reset_workspace(body: ReasonBody, user: User = Depends(require("workspace.reset"))):
    from app.services.simulator import REPLAY, SIM
    SIM.stop()
    REPLAY.stop()
    store.reset()
    identity.seed_users()
    DEMO.reset()
    DEMO.last_replay = None
    catalog.rebuild()
    settings_svc.apply_runtime()
    review.sync_cases()
    audit.record(user, "workspace.reset", "workspace", "demo", reason=body.reason or "Demo workspace reset to the pipeline build")
    return {"ok": True}
