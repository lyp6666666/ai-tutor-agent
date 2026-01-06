from __future__ import annotations

from fastapi import APIRouter, Request

from app.schema.report import ReportRequest, ReportResponse

router = APIRouter(tags=["report"])


@router.post("/report", response_model=ReportResponse)
async def generate_report(payload: ReportRequest, request: Request) -> ReportResponse:
    ctx = request.app.state.ctx
    return await ctx.generate_report(payload)

