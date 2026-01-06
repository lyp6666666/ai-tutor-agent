from __future__ import annotations

import re

from agentscope.agent import AgentBase, ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import OpenAIChatModel

from app.core.state_manager import SessionState
from app.schema.summary import SummaryResult


class _RuleBasedSummarizer(AgentBase):
    def __init__(self) -> None:
        super().__init__()
        self.name = "LessonSummarizer"

    async def reply(self, msg: Msg | list[Msg] | None) -> Msg:
        text = ""
        if isinstance(msg, list):
            text = "\n".join([m.get_text_content() for m in msg if hasattr(m, "get_text_content")])
        elif msg is not None:
            text = msg.get_text_content()

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        summary = "；".join(lines[-8:]) if lines else "本节课暂无可总结的文本记录。"
        return Msg(name=self.name, content=summary, role="assistant")

    async def observe(self, *args, **kwargs) -> None:
        return None

    async def handle_interrupt(self, *args, **kwargs) -> Msg:
        return Msg(name=self.name, content="总结被中断。", role="assistant")


class LessonSummarizer:
    def __init__(self) -> None:
        self._fallback = _RuleBasedSummarizer()

    async def summarize(self, session: SessionState, prefer_llm: bool = False) -> SummaryResult:
        timeline_text = self._build_timeline_text(session)
        if prefer_llm:
            llm = self._build_llm_agent()
            if llm is not None:
                msg = Msg(
                    name="user",
                    role="user",
                    content=(
                        "你是课堂AI助教。请基于时间轴文本，输出JSON："
                        '{"summary": "...", "knowledge_points": ["..."], "homework_suggestion": ["..."]}\n\n'
                        f"时间轴：\n{timeline_text}"
                    ),
                )
                res = await llm(msg)
                parsed = self._try_parse_json(res.get_text_content())
                if parsed:
                    return SummaryResult(**parsed)

        msg = Msg(name="user", role="user", content=timeline_text)
        res = await self._fallback(msg)
        return SummaryResult(
            summary=res.get_text_content(),
            knowledge_points=self._extract_knowledge_points(timeline_text),
            homework_suggestion=[],
        )

    def _build_timeline_text(self, session: SessionState) -> str:
        parts: list[str] = []
        for ev in session.timeline[-400:]:
            if ev.type == "im_message" and ev.im is not None:
                sender = ev.im.get("sender_id", "unknown")
                parts.append(f"[IM][{sender}] {ev.im.get('text','')}")
            elif ev.type == "asr_text" and ev.asr is not None:
                parts.append(f"[ASR] {ev.asr.get('text','')}")
            elif ev.type == "video_event" and ev.video is not None:
                parts.append(f"[VIDEO] {ev.video.get('event','')}")
        return "\n".join(parts)

    def _extract_knowledge_points(self, text: str) -> list[str]:
        candidates = re.findall(r"(?:知识点|重点|概念)[:：]\s*([^\n]{2,64})", text)
        out: list[str] = []
        for c in candidates:
            c = c.strip()
            if c and c not in out:
                out.append(c)
        return out[:20]

    def _try_parse_json(self, text: str) -> dict | None:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        import json

        try:
            return json.loads(m.group(0))
        except Exception:
            return None

    def _build_llm_agent(self) -> ReActAgent | None:
        import os

        api_key = os.getenv("OPENAI_API_KEY")
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not api_key:
            return None

        return ReActAgent(
            name="LessonSummarizerLLM",
            sys_prompt="你是课堂AI助教，擅长结构化课后总结。",
            model=OpenAIChatModel(model_name=model_name, api_key=api_key, stream=False),
            formatter=OpenAIChatFormatter(),
            memory=InMemoryMemory(),
        )

