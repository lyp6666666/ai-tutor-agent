from __future__ import annotations

from pydantic import BaseModel


class StageSummariesResponse(BaseModel):
    ok: bool
    session_id: str
    items: list[dict]


class FinalReportResponse(BaseModel):
    ok: bool
    session_id: str
    report: dict | None = None

