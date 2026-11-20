"""WebSocket broadcast hub. Messages: {topic, type, payload, ts}. Clients filter by topic."""
from __future__ import annotations

import asyncio
import time

from app import config
from app.event_log import append_event

import orjson
from fastapi import WebSocket


def _default(o):
    import numpy as np
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    if isinstance(o, set):
        return sorted(o)
    raise TypeError


def dumps(obj) -> bytes:
    return orjson.dumps(obj, default=_default, option=orjson.OPT_SERIALIZE_NUMPY)


class Hub:
    def __init__(self):
        self.clients: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.add(ws)
        self.loop = asyncio.get_running_loop()

    def disconnect(self, ws: WebSocket):
        self.clients.discard(ws)

    async def broadcast(self, topic: str, type_: str, payload) -> None:
        timestamp = time.time()
        msg = dumps({"topic": topic, "type": type_, "payload": payload, "ts": timestamp}).decode()
        await asyncio.to_thread(append_event, config.CACHE_DIR / "events.sqlite3", timestamp, topic, type_, msg)
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def publish(self, topic: str, type_: str, payload) -> None:
        """Thread-safe fire-and-forget (for worker threads)."""
        if self.loop is None:
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(topic, type_, payload), self.loop)


HUB = Hub()
