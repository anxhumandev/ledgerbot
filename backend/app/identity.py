"""Workspace identities, roles and permissions (local demo mode).

This build has no login. The client names the acting user in the `X-LedgerBot-User` header and the backend checks
that the user exists and that its role allows the action. That is enough to attribute decisions and to enforce
role boundaries in a demo workspace, but it is NOT authentication: anyone who can reach the API can claim any
seeded identity. Production needs SSO (OIDC/SAML) in front of this dependency; the permission checks stay the same.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request

from app import store
from app.errors import ApiError

ROLES = {
    "analyst": "Inventory Analyst",
    "supplier_ops": "Supplier Operations Manager",
    "revenue": "Commercial / Revenue Analyst",
    "admin": "Platform Administrator",
}

PERMISSIONS: dict[str, set[str]] = {
    "review.decide": {"analyst", "admin"},
    "review.note": {"analyst", "supplier_ops", "revenue", "admin"},
    "review.assign": {"analyst", "admin"},
    "supplier.configure": {"supplier_ops", "admin"},
    "ingestion.run": {"supplier_ops", "admin"},
    "simulation.run": {"supplier_ops", "revenue", "admin"},
    "offers.configure": {"revenue", "admin"},
    "ranking.configure": {"revenue", "admin"},
    "matching.configure": {"admin"},
    "users.manage": {"admin"},
    "workspace.configure": {"admin"},
    "workspace.reset": {"admin"},
}

SEED_USERS = [
    ("u-priya", "Priya Nair", "priya.nair@ledgerbot.demo", "analyst", "Inventory Analyst"),
    ("u-rahul", "Rahul Mehta", "rahul.mehta@ledgerbot.demo", "supplier_ops", "Supplier Operations Manager"),
    ("u-sara", "Sara Khan", "sara.khan@ledgerbot.demo", "revenue", "Revenue Analyst"),
    ("u-admin", "Dev Admin", "admin@ledgerbot.demo", "admin", "Platform Administrator"),
]
SYSTEM_ACTOR = "system"


@dataclass(frozen=True)
class User:
    id: str
    name: str
    email: str
    role: str
    title: str

    def can(self, permission: str) -> bool:
        return self.role in PERMISSIONS.get(permission, set())

    def view(self) -> dict:
        return {"id": self.id, "name": self.name, "email": self.email, "role": self.role, "role_label": ROLES[self.role],
                "title": self.title, "permissions": sorted(p for p in PERMISSIONS if self.can(p))}


DEFAULT_USER = "u-admin"


def seed_users() -> None:
    """Make the users table match the seeded directory (removed demo identities are dropped, their open
    assignments released; past decisions keep the id they were made under)."""
    ids = [u[0] for u in SEED_USERS]
    marks = ",".join("?" * len(ids))
    store.execute(f"UPDATE review_cases SET assignee = NULL WHERE assignee IS NOT NULL AND assignee NOT IN ({marks})", ids)
    store.execute(f"DELETE FROM users WHERE id NOT IN ({marks})", ids)
    for uid, name, email, role, title in SEED_USERS:
        store.execute("INSERT OR IGNORE INTO users(id, name, email, role, title, created_at) VALUES (?,?,?,?,?,?)",
                      (uid, name, email, role, title, store.now()))


def get_user(uid: str | None) -> User | None:
    if not uid:
        return None
    r = store.one("SELECT id, name, email, role, title FROM users WHERE id = ?", (uid,))
    return User(**r) if r else None


def list_users() -> list[dict]:
    return [User(**r).view() for r in store.query("SELECT id, name, email, role, title FROM users ORDER BY name")]


def current_user(request: Request) -> User | None:
    return get_user(request.headers.get("X-LedgerBot-User"))


def require(permission: str):
    """FastAPI dependency: the request must name a known user whose role grants `permission`."""
    def dep(user: User | None = Depends(current_user)) -> User:
        if user is None:
            raise ApiError(401, "unauthenticated", "Choose a workspace identity before making changes.")
        if not user.can(permission):
            raise ApiError(403, "forbidden", f"{ROLES[user.role]} cannot perform '{permission}'.",
                           {"permission": permission, "role": user.role})
        return user
    return dep
