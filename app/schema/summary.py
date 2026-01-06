from __future__ import annotations

from pydantic import BaseModel, Field


class SummaryResult(BaseModel):
    summary: str
    knowledge_points: list[str] = Field(default_factory=list)
    homework_suggestion: list[str] = Field(default_factory=list)


class SummaryRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    prefer_llm: bool = False


class SummaryResponse(BaseModel):
    ok: bool
    session_id: str
    result: SummaryResult

