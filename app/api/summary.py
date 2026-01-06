from __future__ import annotations

from fastapi import APIRouter, Request

from app.schema.summary import SummaryRequest, SummaryResponse

router = APIRouter(tags=["summary"])


@router.post("/summary", response_model=SummaryResponse)
async def generate_summary(payload: SummaryRequest, request: Request) -> SummaryResponse:
    ctx = request.app.state.ctx
    return await ctx.generate_summary(payload)

