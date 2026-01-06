from __future__ import annotations

from agentscope.agent import AgentBase
from agentscope.message import Msg


class QuestionGenerator(AgentBase):
    def __init__(self) -> None:
        super().__init__()
        self.name = "QuestionGenerator"

    async def reply(self, msg: Msg | list[Msg] | None) -> Msg:
        # TODO: 结合LLM按知识点生成选择/填空/简答题，可输出结构化JSON
        return Msg(name=self.name, role="assistant", content="TODO: 临时出题需要接入LLM或题库。")

    async def observe(self, *args, **kwargs) -> None:
        return None

    async def handle_interrupt(self, *args, **kwargs) -> Msg:
        return Msg(name=self.name, role="assistant", content="出题任务被中断。")

