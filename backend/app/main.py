"""Tessera FastAPI app: REST under /api, WebSocket at /ws."""
from __future__ import annotations

import asyncio
import os
import traceback
from contextlib import asynccontextmanager

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
import warnings  # noqa: E402

warnings.filterwarnings("ignore", message=".*ORJSONResponse is deprecated.*")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import ORJSONResponse  # noqa: E402

from app.demo import DEMO  # noqa: E402
from app.pipeline.cost import METER  # noqa: E402
from app.routers import core, pipeline, sim  # noqa: E402
from app.ws import HUB  # noqa: E402


async def _cost_pump():
    last = None
    while True:
        await asyncio.sleep(1.0)
        if not DEMO.ready:
            continue
        snap = METER.snapshot()
        if snap != last:
            await HUB.broadcast("cost", "snapshot", snap)
            last = snap


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await asyncio.to_thread(DEMO.load)
        from app.services.simulator import SIM
        SIM.prepare()
        from app.pipeline.blocking import embedder
        await asyncio.to_thread(embedder)  # warm the encoder so the first Break-It trace is fast
    except Exception as e:  # keep serving /health with the error message
        DEMO.error = f"{type(e).__name__}: {e}. Run the data + train steps first."
        traceback.print_exc()
    pump = asyncio.create_task(_cost_pump())
    yield
    pump.cancel()


app = FastAPI(title="Tessera", default_response_class=ORJSONResponse, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origin_regex=r"https?://.*", allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
for r in (core.router, pipeline.router, sim.router):
    app.include_router(r, prefix="/api")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await HUB.connect(ws)
    try:
        while True:
            await ws.receive_text()  # clients may ping; nothing else expected
    except WebSocketDisconnect:
        HUB.disconnect(ws)
    except Exception:
        HUB.disconnect(ws)
