from __future__ import annotations

from pydantic import BaseModel, Field

from app.schema.events import EmittedEvent


class CommandRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    teacher_id: str | None = None
    command_text: str = Field(..., min_length=1)
    args: dict = Field(default_factory=dict)


class CommandResponse(BaseModel):
    ok: bool
    active_task: str | None = None
    emitted_events: list[EmittedEvent] = Field(default_factory=list)

