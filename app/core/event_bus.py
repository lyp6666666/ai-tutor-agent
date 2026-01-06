from __future__ import annotations

import asyncio
from collections import defaultdict

from app.schema.events import EmittedEvent


class EventBus:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._subscribers: dict[str, set[asyncio.Queue[EmittedEvent]]] = defaultdict(set)

    async def publish(self, session_id: str, event: EmittedEvent) -> None:
        async with self._locks[session_id]:
            for q in list(self._subscribers[session_id]):
                if q.full():
                    continue
                q.put_nowait(event)

    async def subscribe(self, session_id: str, maxsize: int = 1000) -> asyncio.Queue[EmittedEvent]:
        q: asyncio.Queue[EmittedEvent] = asyncio.Queue(maxsize=maxsize)
        async with self._locks[session_id]:
            self._subscribers[session_id].add(q)
        return q

    async def unsubscribe(self, session_id: str, q: asyncio.Queue[EmittedEvent]) -> None:
        async with self._locks[session_id]:
            self._subscribers[session_id].discard(q)

