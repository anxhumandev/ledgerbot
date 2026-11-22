"""Workspace settings that change application behaviour, plus supplier configuration.

Every setting listed in SETTINGS is wired to real behaviour:
- alpha: the guaranteed false-merge budget; re-certifies thresholds and therefore the review band.
- price_cap_pct: offer selection may not recommend an offer priced more than this above the cheapest comparable one.
- rank_weights: business weights the ranker blends in (margin, Platinum, reliability risk).
- workspace_name: shown in the application header.
Supplier status 'paused' removes that supplier's offers from recommendation and blocks new ingestion jobs.
"""
from __future__ import annotations

from app import audit, config, store
from app.demo import DEMO
from app.errors import ApiError

SETTINGS = {
    "alpha": {"default": config.DEFAULT_ALPHA, "label": "Guaranteed false-merge budget (α)", "permission": "matching.configure"},
    "price_cap_pct": {"default": config.DEFAULT_PRICE_CAP_PCT, "label": "Price competitiveness cap (%)", "permission": "offers.configure"},
    "rank_weights": {"default": dict(config.RANK_WEIGHTS), "label": "Ranking business weights", "permission": "ranking.configure"},
    "workspace_name": {"default": config.WORKSPACE_NAME, "label": "Workspace name", "permission": "workspace.configure"},
}
SUPPLIER_STATUS = ("active", "paused", "onboarding")


def get(key: str):
    row = store.one("SELECT value FROM settings WHERE key = ?", (key,))
    return store.loads(row["value"]) if row else SETTINGS[key]["default"]


def all_settings() -> dict:
    meta = {r["key"]: r for r in store.query("SELECT key, updated_by, updated_at FROM settings")}
    return {k: {"value": get(k), "label": v["label"], "permission": v["permission"],
                "updated_by": meta.get(k, {}).get("updated_by"), "updated_at": meta.get(k, {}).get("updated_at")}
            for k, v in SETTINGS.items()}


def validate(key: str, value):
    if key not in SETTINGS:
        raise ApiError(400, "unknown_setting", f"'{key}' is not a workspace setting.")
    if key == "alpha":
        v = float(value)
        if not 0.001 <= v <= 0.05:
            raise ApiError(422, "invalid_value", "α must be between 0.1% and 5%.", {"field": "alpha"})
        return v
    if key == "price_cap_pct":
        v = float(value)
        if not 0 <= v <= 50:
            raise ApiError(422, "invalid_value", "The price cap must be between 0% and 50%.", {"field": "price_cap_pct"})
        return v
    if key == "rank_weights":
        if not isinstance(value, dict) or set(value) != {"margin", "platinum", "risk"}:
            raise ApiError(422, "invalid_value", "Weights need margin, platinum and risk.", {"field": "rank_weights"})
        out = {k: float(value[k]) for k in ("margin", "platinum", "risk")}
        if any(not 0 <= v <= 2 for v in out.values()):
            raise ApiError(422, "invalid_value", "Each weight must be between 0 and 2.", {"field": "rank_weights"})
        return out
    if key == "workspace_name":
        v = str(value).strip()
        if not 2 <= len(v) <= 60:
            raise ApiError(422, "invalid_value", "Workspace name must be 2–60 characters.", {"field": "workspace_name"})
        return v


def apply_runtime() -> None:
    """Push persisted settings into the running engine (on startup and after every change)."""
    alpha = float(get("alpha"))
    if abs(alpha - DEMO.alpha) > 1e-12:
        DEMO.set_alpha(alpha)
    config.RANK_WEIGHTS.clear()
    config.RANK_WEIGHTS.update(get("rank_weights"))


def update(key: str, value, user, reason: str | None = None) -> dict:
    if not user.can(SETTINGS.get(key, {}).get("permission", "workspace.configure")):
        raise ApiError(403, "forbidden", f"Your role cannot change '{SETTINGS[key]['label']}'.")
    value = validate(key, value)
    before = get(key)
    store.execute("INSERT INTO settings(key, value, updated_by, updated_at) VALUES (?,?,?,?) "
                  "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_by = excluded.updated_by, updated_at = excluded.updated_at",
                  (key, store.dumps(value), user.id, store.now()))
    apply_runtime()
    if key == "alpha":
        from app.services import review
        review.sync_cases()
    audit.record(user, "settings.updated", "setting", key, before={"value": before}, after={"value": value}, reason=reason)
    return all_settings()[key]


# ---------------------------------------------------------------- suppliers
def supplier_status(code: str) -> str:
    row = store.one("SELECT status FROM supplier_config WHERE supplier = ?", (code,))
    if row:
        return row["status"]
    return "active" if code in config.ACTIVE_SUPPLIERS else "onboarding"


def paused_suppliers() -> set[str]:
    return {r["supplier"] for r in store.query("SELECT supplier FROM supplier_config WHERE status = 'paused'")}


def supplier_config(code: str) -> dict:
    row = store.one("SELECT * FROM supplier_config WHERE supplier = ?", (code,)) or {}
    return {"supplier": code, "status": supplier_status(code), "notes": row.get("notes", ""),
            "updated_by": row.get("updated_by"), "updated_at": row.get("updated_at"),
            "take_rate": config.SUPPLIERS[code]["take_rate"]}


def set_supplier_config(code: str, status: str | None, notes: str | None, user, reason: str | None) -> dict:
    if code not in config.SUPPLIERS:
        raise ApiError(404, "not_found", f"Supplier {code} does not exist.")
    if status is not None and status not in SUPPLIER_STATUS:
        raise ApiError(422, "invalid_value", f"Status must be one of {', '.join(SUPPLIER_STATUS)}.", {"field": "status"})
    before = supplier_config(code)
    new_status = status or before["status"]
    new_notes = before["notes"] if notes is None else notes[:2000]
    store.execute("INSERT INTO supplier_config(supplier, status, notes, updated_by, updated_at) VALUES (?,?,?,?,?) "
                  "ON CONFLICT(supplier) DO UPDATE SET status = excluded.status, notes = excluded.notes, "
                  "updated_by = excluded.updated_by, updated_at = excluded.updated_at",
                  (code, new_status, new_notes, user.id, store.now()))
    after = supplier_config(code)
    audit.record(user, "supplier.config_updated", "supplier", code,
                 before={"status": before["status"], "notes": before["notes"]},
                 after={"status": after["status"], "notes": after["notes"]}, reason=reason)
    return after
