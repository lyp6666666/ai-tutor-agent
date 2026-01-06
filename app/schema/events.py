from __future__ import annotations

from pydantic import BaseModel, Field


class EmittedEvent(BaseModel):
    type: str
    timestamp: float
    payload: dict = Field(default_factory=dict)

