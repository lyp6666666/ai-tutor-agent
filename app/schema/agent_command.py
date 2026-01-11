from __future__ import annotations

from pydantic import BaseModel, Field


class AgentCommandRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    teacher_id: str | None = None
    instruction: str = Field(..., min_length=1)

    image_url: str | None = None


class AgentCommandResponse(BaseModel):
    ok: bool
    session_id: str

