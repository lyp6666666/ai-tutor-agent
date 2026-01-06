from __future__ import annotations

from fastapi import APIRouter, Request

from app.schema.ingest import IngestEvent, IngestResponse

router = APIRouter(tags=["ingest"])


@router.post("/ingest/events", response_model=IngestResponse)
async def ingest_events(payload: IngestEvent, request: Request) -> IngestResponse:
    ctx = request.app.state.ctx
    outputs = await ctx.ingest_event(payload)
    return IngestResponse(ok=True, emitted_events=outputs)

