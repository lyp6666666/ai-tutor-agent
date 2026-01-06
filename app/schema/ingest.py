from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schema.events import EmittedEvent


class IngestEvent(BaseModel):
    session_id: str = Field(..., min_length=1)
    type: Literal["im_message", "asr_text", "video_event"]
    timestamp: float

    im: dict | None = None
    asr: dict | None = None
    video: dict | None = None


class IngestResponse(BaseModel):
    ok: bool
    emitted_events: list[EmittedEvent] = Field(default_factory=list)

