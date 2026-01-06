from __future__ import annotations

from agentscope.agent import AgentBase
from agentscope.message import Msg


class DictationAgent(AgentBase):
    def __init__(self) -> None:
        super().__init__()
        self.name = "DictationAgent"

    async def reply(self, msg: Msg | list[Msg] | None) -> Msg:
        return Msg(name=self.name, role="assistant", content="DictationAgent 由任务调度器驱动。")

    async def observe(self, *args, **kwargs) -> None:
        return None

    async def handle_interrupt(self, *args, **kwargs) -> Msg:
        return Msg(name=self.name, role="assistant", content="听写任务被中断。")

