"""Durable operational store (SQLite).

Holds everything an operator changes: review cases and notes, the ordered log of catalog mutations (merges, splits,
ingested records), ingestion jobs, supplier configuration, workspace settings, users and the append-only audit log.
The synthetic world and trained model artifacts stay read-only; this store only records decisions made on top of them.

The schema is versioned through MIGRATIONS so it can move to PostgreSQL later without changing callers: every query
goes through `query`, `one` and `execute`, and JSON columns are plain TEXT.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app import config

_LOCK = threading.RLock()
_CONN: sqlite3.Connection | None = None
_PATH: Path | None = None

MIGRATIONS: list[str] = [
    # 1: initial enterprise schema
    """
    CREATE TABLE users (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, role TEXT NOT NULL,
        title TEXT NOT NULL, created_at REAL NOT NULL
    );
    CREATE TABLE review_cases (
        id TEXT PRIMARY KEY, pair_key TEXT NOT NULL UNIQUE, record_a TEXT NOT NULL, record_b TEXT NOT NULL,
        p REAL NOT NULL, priority TEXT NOT NULL, source TEXT NOT NULL, status TEXT NOT NULL,
        assignee TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL,
        decided_by TEXT, decided_at REAL, decision_reason TEXT, mutation_id INTEGER, version INTEGER NOT NULL DEFAULT 1
    );
    CREATE INDEX review_cases_status ON review_cases(status);
    CREATE TABLE review_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL, author TEXT NOT NULL, body TEXT NOT NULL,
        created_at REAL NOT NULL
    );
    CREATE TABLE catalog_mutations (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL,
        actor TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, source TEXT NOT NULL
    );
    CREATE TABLE ingestion_jobs (
        id TEXT PRIMARY KEY, supplier TEXT NOT NULL, filename TEXT NOT NULL, format TEXT NOT NULL, status TEXT NOT NULL,
        created_by TEXT NOT NULL, created_at REAL NOT NULL, started_at REAL, finished_at REAL,
        total INTEGER NOT NULL DEFAULT 0, valid INTEGER NOT NULL DEFAULT 0, invalid INTEGER NOT NULL DEFAULT 0,
        processed INTEGER NOT NULL DEFAULT 0, merged INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL DEFAULT 0,
        updated INTEGER NOT NULL DEFAULT 0, review INTEGER NOT NULL DEFAULT 0, rejected INTEGER NOT NULL DEFAULT 0,
        issues TEXT NOT NULL DEFAULT '[]', payload TEXT NOT NULL, error TEXT, attempts INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE ingestion_results (
        job_id TEXT NOT NULL, record_id TEXT NOT NULL, outcome TEXT NOT NULL, tessera_id TEXT, p REAL, detail TEXT,
        PRIMARY KEY (job_id, record_id)
    );
    CREATE TABLE supplier_config (
        supplier TEXT PRIMARY KEY, status TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', updated_by TEXT,
        updated_at REAL
    );
    CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_by TEXT, updated_at REAL);
    CREATE TABLE idempotency (key TEXT PRIMARY KEY, response TEXT NOT NULL, created_at REAL NOT NULL);
    CREATE TABLE audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, ts REAL NOT NULL, actor TEXT NOT NULL,
        actor_role TEXT, action TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
        before TEXT, after TEXT, reason TEXT, request_id TEXT
    );
    CREATE INDEX audit_entity ON audit_events(entity_type, entity_id);
    CREATE INDEX audit_ts ON audit_events(ts);
    CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_events
        BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
    CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_events
        BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
    """,
]


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init(path: Path | None = None) -> None:
    """Open the database and apply pending migrations. Safe to call repeatedly."""
    global _CONN, _PATH
    with _LOCK:
        path = Path(path or config.DB_PATH)
        if _CONN is not None and _PATH == path:
            return
        if _CONN is not None:
            _CONN.close()
        _CONN, _PATH = _connect(path), path
        _CONN.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        row = _CONN.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
        current = row["v"] or 0
        for i, sql in enumerate(MIGRATIONS[current:], start=current + 1):
            with transaction() as c:
                for statement in _split(sql):
                    c.execute(statement)
                c.execute("INSERT INTO schema_version(version) VALUES (?)", (i,))


def _split(script: str) -> list[str]:
    """Split a migration into statements, keeping trigger bodies (which contain ';') intact."""
    out, buf, depth = [], [], 0
    for line in script.splitlines():
        s = line.strip()
        if not s:
            continue
        buf.append(line)
        up = s.upper()
        depth += len(re.findall(r"\bBEGIN\b", up)) - len(re.findall(r"\bEND\b", up))
        if s.endswith(";") and depth == 0:
            out.append("\n".join(buf))
            buf = []
    if buf:
        out.append("\n".join(buf))
    return out


def reset(path: Path | None = None) -> None:
    """Delete every operational record (used by the admin 'reset demo workspace' action and by tests)."""
    global _CONN, _PATH
    with _LOCK:
        target = Path(path or _PATH or config.DB_PATH)
        if _CONN is not None:
            _CONN.close()
        _CONN = None
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(target) + suffix)
            if p.exists():
                p.unlink()
        init(target)


def conn() -> sqlite3.Connection:
    if _CONN is None:
        init()
    return _CONN  # type: ignore[return-value]


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    with _LOCK:
        c = _CONN if _CONN is not None else conn()
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise


def query(sql: str, params: tuple | list = ()) -> list[dict]:
    with _LOCK:
        return [dict(r) for r in conn().execute(sql, params).fetchall()]


def one(sql: str, params: tuple | list = ()) -> dict | None:
    with _LOCK:
        r = conn().execute(sql, params).fetchone()
        return dict(r) if r else None


def execute(sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
    with _LOCK:
        return conn().execute(sql, params)


def now() -> float:
    return time.time()


def dumps(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


def loads(s: str | None, default: Any = None) -> Any:
    if s in (None, ""):
        return default
    return json.loads(s)
