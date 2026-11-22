"""LedgerBot FastAPI app: REST API under /api."""
from __future__ import annotations

import asyncio
import os
import traceback
from contextlib import asynccontextmanager

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
import warnings  # noqa: E402

warnings.filterwarnings("ignore", message=".*ORJSONResponse is deprecated.*")

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import ORJSONResponse  # noqa: E402

from app.demo import DEMO  # noqa: E402
from app import errors, store  # noqa: E402
from app.routers import core, feed, operations, pipeline, sim, workspace  # noqa: E402


def _init_workspace():
    """Open the operational store and bring the in-memory engine in line with it."""
    from app import audit, identity
    from app.services import catalog, ingestion, review, settings_svc
    store.init()
    identity.seed_users()
    settings_svc.apply_runtime()
    if catalog.has_mutations():
        res = catalog.rebuild()
        print(f"Replayed catalog changes in {res['applied_in_s']}s; skipped {len(res['skipped'])}")
    review.sync_cases()
    ingestion.recover_interrupted()
    if not store.one("SELECT 1 AS x FROM audit_events LIMIT 1"):
        audit.record("system", "workspace.initialized", "workspace", "demo",
                     after={"catalog_built_at": DEMO.state["built_at"], "world": DEMO.state.get("world")})


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await asyncio.to_thread(DEMO.load)
        await asyncio.to_thread(_init_workspace)
        from app.services.simulator import SIM
        SIM.prepare()
        from app.pipeline.blocking import embedder
        await asyncio.to_thread(embedder)  # warm the encoder so the first Break-It trace is fast
    except Exception as e:  # keep serving /health with the error message
        DEMO.ready = False
        DEMO.error = f"{type(e).__name__}: {e}. Run the data + train steps first."
        traceback.print_exc()
    try:
        yield
    finally:
        from app.services.simulator import REPLAY, SIM
        jobs = [task for task in (SIM.task, REPLAY.task) if task]
        for task in jobs:
            task.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)


app = FastAPI(title="LedgerBot", default_response_class=ORJSONResponse, lifespan=lifespan)
from app import config  # noqa: E402

app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   allow_headers=["Content-Type", "X-LedgerBot-User", "Idempotency-Key", "X-Request-ID"],
                   expose_headers=["X-Request-ID"])
errors.install(app)
for r in (core.router, pipeline.router, sim.router, feed.router, workspace.router, operations.router):
    app.include_router(r, prefix="/api")

