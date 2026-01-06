from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["ws"])


@router.websocket("/ws/{session_id}")
async def ws_events(websocket: WebSocket, session_id: str):
    ctx = websocket.app.state.ctx
    await websocket.accept()
    q = await ctx.event_bus.subscribe(session_id)
    try:
        while True:
            event = await q.get()
            await websocket.send_text(json.dumps(event.model_dump(), ensure_ascii=False))
    except WebSocketDisconnect:
        await ctx.event_bus.unsubscribe(session_id, q)
