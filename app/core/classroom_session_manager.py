from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from time import time

from app.core.asr_client import VolcengineAsrWsClient


@dataclass
class ClassroomSession:
    session_id: str
    created_at: float = field(default_factory=lambda: time())
    seq: int = 0
    status: str = "RUNNING"
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    asr: VolcengineAsrWsClient | None = None

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq


class ClassroomSessionManager:
    """
    课堂会话管理器（内存）。

    职责：
    - 管理 session 生命周期
    - 管理与 session 绑定的运行时资源（例如 ASR 客户端、序号、互斥锁）
    """

    def __init__(self) -> None:
        self._sessions: dict[str, ClassroomSession] = {}
        self._lock = asyncio.Lock()

    async def create(self, session_id: str) -> ClassroomSession:
        async with self._lock:
            if session_id in self._sessions:
                raise ValueError(f"session already exists: {session_id}")
            s = ClassroomSession(session_id=session_id)
            self._sessions[session_id] = s
            return s

    async def get(self, session_id: str) -> ClassroomSession:
        async with self._lock:
            s = self._sessions.get(session_id)
            if s is None:
                raise ValueError(f"session not found: {session_id}")
            return s

    async def mark_ending(self, session_id: str) -> None:
        s = await self.get(session_id)
        async with s.lock:
            s.status = "ENDING"

    async def mark_ended(self, session_id: str) -> None:
        s = await self.get(session_id)
        async with s.lock:
            s.status = "ENDED"
