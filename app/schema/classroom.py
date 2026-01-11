from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TeacherInfo(BaseModel):
    teacher_id: str = Field(..., min_length=1)
    teacher_name: str = Field(..., min_length=1)


class ClassroomOpenRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    course_id: str = Field(..., min_length=1)
    course_name: str = Field(..., min_length=1)
    teacher: TeacherInfo
    start_time: float


class ClassroomOpenResponse(BaseModel):
    ok: bool
    session_id: str


class ClassroomEndRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    end_time: float


class ClassroomEndResponse(BaseModel):
    ok: bool
    session_id: str


class RealtimeAudioFrame(BaseModel):
    session_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    user_name: str = Field(..., min_length=1)
    role: Literal["teacher", "student"]
    timestamp: float
    audio_chunk: str = Field(..., min_length=1)
    is_last: bool = False

    mock_text: str | None = None


class UtteranceFact(BaseModel):
    session_id: str
    user_id: str
    user_name: str
    role: Literal["teacher", "student"]
    text: str
    start_time: float
    end_time: float
    timestamp: float
    confidence: float | None = None

