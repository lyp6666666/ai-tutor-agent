from __future__ import annotations

from fastapi import APIRouter, Request

from app.schema.agent_command import AgentCommandRequest, AgentCommandResponse


router = APIRouter(tags=["agent"])


@router.post("/agent/command", response_model=AgentCommandResponse)
async def agent_command(payload: AgentCommandRequest, request: Request) -> AgentCommandResponse:
    ctx = request.app.state.ctx
    await ctx.handle_agent_command(payload)
    return AgentCommandResponse(ok=True, session_id=payload.session_id)

