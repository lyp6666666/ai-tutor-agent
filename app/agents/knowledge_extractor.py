from __future__ import annotations

import re

from agentscope.agent import AgentBase
from agentscope.message import Msg


class KnowledgeExtractor(AgentBase):
    def __init__(self) -> None:
        super().__init__()
        self.name = "KnowledgeExtractor"

    async def reply(self, msg: Msg | list[Msg] | None) -> Msg:
        text = ""
        if isinstance(msg, list):
            text = "\n".join([m.get_text_content() for m in msg])
        elif msg is not None:
            text = msg.get_text_content()

        points = re.findall(r"(?:知识点|重点|概念)[:：]\s*([^\n]{2,64})", text)
        points = list(dict.fromkeys([p.strip() for p in points if p.strip()]))[:20]
        return Msg(name=self.name, role="assistant", content="\n".join(points) if points else "未抽取到明确知识点。")

    async def observe(self, *args, **kwargs) -> None:
        return None

    async def handle_interrupt(self, *args, **kwargs) -> Msg:
        return Msg(name=self.name, role="assistant", content="知识点抽取被中断。")

