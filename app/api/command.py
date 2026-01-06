from __future__ import annotations

from fastapi import APIRouter, Request

from app.schema.command import CommandRequest, CommandResponse

router = APIRouter(tags=["command"])


@router.post("/command", response_model=CommandResponse)
async def command(payload: CommandRequest, request: Request) -> CommandResponse:
    ctx = request.app.state.ctx
    result = await ctx.handle_command(payload)
    return result

