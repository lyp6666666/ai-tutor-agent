from __future__ import annotations

import json
from time import time

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from app.schema.classroom import (
    ClassroomEndRequest,
    ClassroomEndResponse,
    ClassroomOpenRequest,
    ClassroomOpenResponse,
    RealtimeAudioFrame,
)
from app.schema.classroom_queries import FinalReportResponse, StageSummariesResponse


router = APIRouter(tags=["classroom"])


@router.post("/classroom/open", response_model=ClassroomOpenResponse)
async def open_classroom(payload: ClassroomOpenRequest, request: Request) -> ClassroomOpenResponse:
    ctx = request.app.state.ctx
    await ctx.open_classroom(payload)
    return ClassroomOpenResponse(ok=True, session_id=payload.session_id)


@router.post("/classroom/end", response_model=ClassroomEndResponse)
async def end_classroom(payload: ClassroomEndRequest, request: Request) -> ClassroomEndResponse:
    ctx = request.app.state.ctx
    await ctx.end_classroom(payload.session_id, payload.end_time)
    return ClassroomEndResponse(ok=True, session_id=payload.session_id)


@router.get("/classroom/{session_id}/stage_summaries", response_model=StageSummariesResponse)
async def get_stage_summaries(session_id: str, request: Request) -> StageSummariesResponse:
    ctx = request.app.state.ctx
    items = await ctx.list_stage_summaries(session_id)
    return StageSummariesResponse(ok=True, session_id=session_id, items=items)


@router.get("/classroom/{session_id}/final_report", response_model=FinalReportResponse)
async def get_final_report(session_id: str, request: Request) -> FinalReportResponse:
    ctx = request.app.state.ctx
    report = await ctx.get_final_report(session_id)
    return FinalReportResponse(ok=True, session_id=session_id, report=report)


@router.websocket("/classroom/realtime")
async def classroom_realtime_ws(websocket: WebSocket):
    ctx = websocket.app.state.ctx
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            frame = RealtimeAudioFrame.model_validate(data)
            await ctx.handle_realtime_audio_frame(frame)
            await websocket.send_text(json.dumps({"ok": True, "timestamp": time()}, ensure_ascii=False))
    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        except Exception:
            pass
