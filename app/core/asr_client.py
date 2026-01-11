from __future__ import annotations

import base64
from dataclasses import dataclass


@dataclass(frozen=True)
class AsrResult:
    text: str
    confidence: float | None
    start_time: float
    end_time: float


class VolcengineAsrWsClient:
    """
    火山引擎 ASR WebSocket 客户端占位实现。

    TODO:
    - 按火山引擎 ASR SDK/协议建立 WebSocket 长连接
    - 支持 new_full_client_request 初始化帧
    - 支持 new_audio_only_request 音频帧
    - 在接收协程里持续产出 AsrResult

    当前为了不阻塞架构改造，只提供：
    - validate_audio_chunk：把 base64 解成 bytes，确保格式可用
    """

    def __init__(self, *, session_id: str) -> None:
        self.session_id = session_id

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def validate_audio_chunk(self, audio_chunk_b64: str) -> bytes:
        return base64.b64decode(audio_chunk_b64)

