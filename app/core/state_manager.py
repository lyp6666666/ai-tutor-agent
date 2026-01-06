from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from time import time

from app.schema.ingest import IngestEvent


@dataclass
class DictationState:
    active: bool = False
    words: list[str] = field(default_factory=list)
    index: int = 0
    attempts: int = 0
    correct: int = 0
    last_prompted_at: float | None = None


@dataclass
class ObserverState:
    utterances_by_user: dict[str, int] = field(default_factory=dict)
    correct_answers_by_user: dict[str, int] = field(default_factory=dict)
    total_answers_by_user: dict[str, int] = field(default_factory=dict)
    focus_events: list[dict] = field(default_factory=list)


@dataclass
class SessionState:
    session_id: str
    created_at: float = field(default_factory=lambda: time())
    timeline: list[IngestEvent] = field(default_factory=list)
    dictation: DictationState = field(default_factory=DictationState)
    observer: ObserverState = field(default_factory=ObserverState)
    active_task: str | None = None


class StateManager:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._sessions: dict[str, SessionState] = {}

    async def get_session(self, session_id: str) -> SessionState:
        async with self._locks[session_id]:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionState(session_id=session_id)
            return self._sessions[session_id]

    async def append_event(self, event: IngestEvent) -> None:
        session = await self.get_session(event.session_id)
        async with self._locks[event.session_id]:
            session.timeline.append(event)

