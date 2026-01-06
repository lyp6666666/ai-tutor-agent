from __future__ import annotations

from pydantic import BaseModel, Field


class ClassroomReport(BaseModel):
    student_id: str
    participation: str
    focus_score: float
    utterances: int = 0
    answer_accuracy: float = 0.0


class ReportRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    student_id: str = Field(..., min_length=1)


class ReportResponse(BaseModel):
    ok: bool
    session_id: str
    report: ClassroomReport

