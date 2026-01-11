from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.agent import router as agent_router
from app.api.classroom import router as classroom_router
from app.api.ws import router as ws_router
from app.core.app_context import AppContext


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ctx = AppContext()
    await app.state.ctx.start_background()
    yield
    await app.state.ctx.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="AI Tutor Agent", version="0.1.0", lifespan=lifespan)
    app.include_router(classroom_router, prefix="/api/v1")
    app.include_router(agent_router, prefix="/api/v1")
    app.include_router(ws_router, prefix="/api/v1")
    return app


app = create_app()
