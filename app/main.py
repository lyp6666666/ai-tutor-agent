from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.command import router as command_router
from app.api.homework import router as homework_router
from app.api.ingest import router as ingest_router
from app.api.report import router as report_router
from app.api.summary import router as summary_router
from app.api.ws import router as ws_router
from app.core.app_context import AppContext


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ctx = AppContext()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="AI Tutor Agent", version="0.1.0", lifespan=lifespan)
    app.state.ctx = AppContext()
    app.include_router(ingest_router, prefix="/api/v1")
    app.include_router(command_router, prefix="/api/v1")
    app.include_router(summary_router, prefix="/api/v1")
    app.include_router(report_router, prefix="/api/v1")
    app.include_router(homework_router, prefix="/api/v1")
    app.include_router(ws_router, prefix="/api/v1")
    return app


app = create_app()
