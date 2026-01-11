from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx


class ArkClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArkChatContentPart:
    type: str
    text: str | None = None
    image_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": self.type}
        if self.text is not None:
            payload["text"] = self.text
        if self.image_url is not None:
            payload["image_url"] = self.image_url
        return payload


@dataclass(frozen=True)
class ArkChatTurn:
    role: str
    content: list[ArkChatContentPart]

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "content": [p.to_dict() for p in self.content]}


class ArkChatClient:
    """
    火山方舟 Chat API 轻量封装，面向“智能体运行时”使用。
    - 只负责可靠发起请求/解析响应
    - 不负责业务 prompt、状态、工具调用与结果落库
    """

    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_s: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout_s))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def chat(self, turns: list[ArkChatTurn]) -> str:
        url = f"{self._base_url}/chat/completions"
        req_payload = {
            "model": self._model,
            "input": [t.to_dict() for t in turns],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        resp = await self._client.post(url, headers=headers, json=req_payload)
        if resp.status_code >= 400:
            raise ArkClientError(f"Ark chat failed: {resp.status_code} {resp.text}")
        data = resp.json()
        text = self._extract_text(data)
        if text is None:
            raise ArkClientError(f"Ark chat response parse failed: {json.dumps(data, ensure_ascii=False)[:2000]}")
        return text

    def _extract_text(self, data: dict[str, Any]) -> str | None:
        candidates = data.get("output") or data.get("choices") or []
        if isinstance(candidates, list) and candidates:
            first = candidates[0]
            message = first.get("message") if isinstance(first, dict) else None
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts: list[str] = []
                    for p in content:
                        if isinstance(p, dict) and isinstance(p.get("text"), str):
                            parts.append(p["text"])
                    if parts:
                        return "\n".join(parts).strip()
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                return first["text"]
        if isinstance(data.get("text"), str):
            return data["text"]
        return None

