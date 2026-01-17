from __future__ import annotations

import asyncio
from collections import defaultdict

from app.schema.events import EmittedEvent


class EventBus:
    """
        事件总线类，负责事件的发布和订阅。
        
        每个会话都有一个独立的事件队列，用于存储和分发事件。
        发布事件时，会将事件放入对应会话的队列中；订阅时，会创建一个新的队列并返回。
    """
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._subscribers: dict[str, set[asyncio.Queue[EmittedEvent]]] = defaultdict(set)
    
    """
        发布事件到指定会话的队列中
        
        参数:
        session_id: 会话ID，用于指定事件发布到哪个会话的队列
        event: 要发布的事件对象，必须是EmittedEvent类型
    """
    async def publish(self, session_id: str, event: EmittedEvent) -> None:
        async with self._locks[session_id]:
            for q in list(self._subscribers[session_id]):
                if q.full():
                    continue
                q.put_nowait(event)

    """
        订阅会话事件的方法
        
        1. 创建一个新的事件队列，用于存储会话事件
        2. 将队列添加到会话的订阅列表中
        3. 返回队列，用于消费会话事件
        
        参数：
        - session_id: 会话ID，用于标识不同的会话
        - maxsize: 队列最大容量，默认值为1000
        
        返回：
        - asyncio.Queue[EmittedEvent]: 会话事件队列，用于消费会话事件
    """
    async def subscribe(self, session_id: str, maxsize: int = 1000) -> asyncio.Queue[EmittedEvent]:
        q: asyncio.Queue[EmittedEvent] = asyncio.Queue(maxsize=maxsize)
        async with self._locks[session_id]:
            self._subscribers[session_id].add(q)
        return q

    """
        取消订阅会话事件的方法
        
        1. 从会话的订阅列表中移除指定的队列
        2. 确保在取消订阅时，队列中没有未处理的事件
        
        参数：
        - session_id: 会话ID，用于标识不同的会话
        - q: 要取消订阅的事件队列，必须是subscribe方法返回的队列
    """
    async def unsubscribe(self, session_id: str, q: asyncio.Queue[EmittedEvent]) -> None:
        async with self._locks[session_id]:
            self._subscribers[session_id].discard(q)

