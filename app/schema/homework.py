from __future__ import annotations

from pydantic import BaseModel


class HomeworkGradeResponse(BaseModel):
    ok: bool
    session_id: str
    student_id: str
    result: dict

