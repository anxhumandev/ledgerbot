import asyncio
import json
import sqlite3

from app import config
from app.ws import Hub


def test_log_records_events_without_connected_clients(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    hub = Hub()

    async def simulate():
        await hub.broadcast("replay", "start", {"n": 1000})
        await hub.broadcast("replay", "done", {"done": 1000})

    asyncio.run(simulate())
    with sqlite3.connect(tmp_path / "events.sqlite3") as db:
        records = db.execute("SELECT topic, kind, envelope FROM events ORDER BY id").fetchall()
    assert [(topic, kind) for topic, kind, _ in records] == [("replay", "start"), ("replay", "done")]
    assert json.loads(records[-1][2])["payload"] == {"done": 1000}
