"""Append-only audit trail. Rows can be added and read; the database rejects updates and deletes."""
from __future__ import annotations

import uuid

from app import store
from app.errors import REQUEST_ID


def record(actor, action: str, entity_type: str, entity_id: str, *, before=None, after=None, reason: str | None = None) -> dict:
    """`actor` is an identity.User or the string 'system'."""
    actor_id = getattr(actor, "id", actor) or "system"
    role = getattr(actor, "role", "system")
    ev = {"event_id": f"EV-{uuid.uuid4().hex[:10].upper()}", "ts": store.now(), "actor": actor_id, "actor_role": role,
          "action": action, "entity_type": entity_type, "entity_id": str(entity_id),
          "before": store.dumps(before) if before is not None else None,
          "after": store.dumps(after) if after is not None else None, "reason": reason, "request_id": REQUEST_ID.get() or None}
    store.execute("""INSERT INTO audit_events(event_id, ts, actor, actor_role, action, entity_type, entity_id, before, after,
                     reason, request_id) VALUES (:event_id,:ts,:actor,:actor_role,:action,:entity_type,:entity_id,:before,:after,
                     :reason,:request_id)""", ev)
    return ev


def _view(r: dict, names: dict) -> dict:
    return {**r, "actor_name": names.get(r["actor"], "System" if r["actor"] == "system" else r["actor"]),
            "before": store.loads(r["before"]), "after": store.loads(r["after"])}


def search(q: str = "", actor: str = "", action: str = "", entity_type: str = "", entity_id: str = "",
           since: float | None = None, until: float | None = None, page: int = 1, page_size: int = 50) -> dict:
    where, params = [], []
    if q:
        where.append("(action LIKE ? OR entity_id LIKE ? OR reason LIKE ? OR after LIKE ? OR event_id LIKE ?)")
        params += [f"%{q}%"] * 5
    for col, val in (("actor", actor), ("action", action), ("entity_type", entity_type), ("entity_id", entity_id)):
        if val:
            where.append(f"{col} = ?")
            params.append(val)
    if since:
        where.append("ts >= ?")
        params.append(since)
    if until:
        where.append("ts <= ?")
        params.append(until)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    total = store.one(f"SELECT COUNT(*) AS n FROM audit_events {clause}", params)["n"]
    rows = store.query(f"SELECT * FROM audit_events {clause} ORDER BY ts DESC, id DESC LIMIT ? OFFSET ?",
                       params + [page_size, (page - 1) * page_size])
    names = {u["id"]: u["name"] for u in store.query("SELECT id, name FROM users")}
    actions = [r["action"] for r in store.query("SELECT DISTINCT action FROM audit_events ORDER BY action")]
    return {"items": [_view(r, names) for r in rows], "total": total, "page": page, "page_size": page_size, "actions": actions}


def for_entity(entity_type: str, entity_id: str, limit: int = 50) -> list[dict]:
    names = {u["id"]: u["name"] for u in store.query("SELECT id, name FROM users")}
    rows = store.query("SELECT * FROM audit_events WHERE entity_type = ? AND entity_id = ? ORDER BY ts DESC LIMIT ?",
                       (entity_type, entity_id, limit))
    return [_view(r, names) for r in rows]


def last_touch(entity_type: str) -> dict[str, float]:
    return {r["entity_id"]: r["ts"] for r in store.query(
        "SELECT entity_id, MAX(ts) AS ts FROM audit_events WHERE entity_type = ? GROUP BY entity_id", (entity_type,))}
