from __future__ import annotations

import json
import re
from dataclasses import dataclass
from time import time
from typing import Any

from app.llm.ark_client import ArkChatClient, ArkChatContentPart, ArkChatTurn


@dataclass(frozen=True)
class StageSummary:
    timestamp: float
    summary: str
    knowledge_points: list[str]
    classroom_insights: list[str]


def _try_parse_json(text: str) -> dict[str, Any] | None:
    m = re.search(r"\{[\s\S]*\}", text or "")
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


class LlmSummarizer:
    def __init__(self, client: ArkChatClient) -> None:
        self._client = client

    async def summarize_stage(self, *, utterances_text: str, course_meta_text: str | None = None) -> StageSummary:
        prompt = (
            "你是课堂AI助教。请基于课堂发言记录，输出严格JSON："
            '{"summary": "...", "knowledge_points": ["..."], "classroom_insights": ["..."]}\n'
            "要求：knowledge_points 为精炼短语；classroom_insights 用于课堂节奏/互动观察。\n\n"
        )
        if course_meta_text:
            prompt += f"课程信息：\n{course_meta_text}\n\n"
        prompt += f"发言记录：\n{utterances_text}"

        turns = [
            ArkChatTurn(role="user", content=[ArkChatContentPart(type="input_text", text=prompt)]),
        ]
        raw = await self._client.chat(turns)
        parsed = _try_parse_json(raw) or {}
        summary = str(parsed.get("summary") or raw).strip()
        knowledge_points = parsed.get("knowledge_points") if isinstance(parsed.get("knowledge_points"), list) else []
        classroom_insights = (
            parsed.get("classroom_insights") if isinstance(parsed.get("classroom_insights"), list) else []
        )
        return StageSummary(
            timestamp=time(),
            summary=summary,
            knowledge_points=[str(x) for x in knowledge_points if str(x).strip()][:30],
            classroom_insights=[str(x) for x in classroom_insights if str(x).strip()][:30],
        )

    async def summarize_final(
        self,
        *,
        utterances_text: str,
        stage_summaries_text: str,
        course_meta_text: str | None = None,
    ) -> dict[str, Any]:
        prompt = (
            "你是课堂AI助教。请基于整节课的课堂事实与阶段总结，输出严格JSON："
            '{"summary": "...", "knowledge_points": ["..."], "homework_suggestion": ["..."],'
            ' "classroom_report": {"participation_overview":"...","focus_overview":"...","highlights":["..."]}}\n'
            "要求：summary 为可读的课后总结；knowledge_points 为精炼短语；homework_suggestion 为可执行条目。\n\n"
        )
        if course_meta_text:
            prompt += f"课程信息：\n{course_meta_text}\n\n"
        if stage_summaries_text.strip():
            prompt += f"阶段总结：\n{stage_summaries_text}\n\n"
        prompt += f"课堂发言事实：\n{utterances_text}"

        turns = [
            ArkChatTurn(role="user", content=[ArkChatContentPart(type="input_text", text=prompt)]),
        ]
        raw = await self._client.chat(turns)
        parsed = _try_parse_json(raw)
        if parsed:
            return parsed
        return {
            "summary": raw.strip(),
            "knowledge_points": [],
            "homework_suggestion": [],
            "classroom_report": {"participation_overview": "", "focus_overview": "", "highlights": []},
        }

    async def command_reply(
        self,
        *,
        instruction: str,
        image_url: str | None,
        context_text: str,
    ) -> str:
        turns: list[ArkChatTurn] = []

        if image_url:
            turns.append(
                ArkChatTurn(
                    role="user",
                    content=[
                        ArkChatContentPart(type="input_image", image_url=image_url),
                        ArkChatContentPart(
                            type="input_text",
                            text=(
                                "你是课堂AI助教。请结合课堂上下文与教师指令给出可直接发送给教师的中文回复。\n\n"
                                f"教师指令：{instruction}\n\n"
                                f"课堂上下文：\n{context_text}"
                            ),
                        ),
                    ],
                )
            )
        else:
            turns.append(
                ArkChatTurn(
                    role="user",
                    content=[
                        ArkChatContentPart(
                            type="input_text",
                            text=(
                                "你是课堂AI助教。请结合课堂上下文与教师指令给出可直接发送给教师的中文回复。\n\n"
                                f"教师指令：{instruction}\n\n"
                                f"课堂上下文：\n{context_text}"
                            ),
                        )
                    ],
                )
            )

        return (await self._client.chat(turns)).strip()
