"""Append the same envelopes that reach the demo's WebSocket clients to SQLite."""
from contextlib import closing
from pathlib import Path
import sqlite3


def append_event(path: Path, timestamp: float, topic: str, kind: str, envelope: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY, ts REAL NOT NULL, topic TEXT NOT NULL,
            kind TEXT NOT NULL, envelope TEXT NOT NULL
        )""")
        db.execute("INSERT INTO events(ts, topic, kind, envelope) VALUES (?, ?, ?, ?)",
                   (timestamp, topic, kind, envelope))
