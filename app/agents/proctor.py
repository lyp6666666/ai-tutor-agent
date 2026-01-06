from __future__ import annotations

from agentscope.agent import AgentBase
from agentscope.message import Msg


class ProctorAgent(AgentBase):
    def __init__(self) -> None:
        super().__init__()
        self.name = "ProctorAgent"

    async def reply(self, msg: Msg | list[Msg] | None) -> Msg:
        # TODO: 接入YOLOv8/OpenCV，对视频帧进行多人/离开座位/低头等检测
        return Msg(name=self.name, role="assistant", content="TODO: 监考能力需要接入视频检测模型。")

    async def observe(self, *args, **kwargs) -> None:
        return None

    async def handle_interrupt(self, *args, **kwargs) -> Msg:
        return Msg(name=self.name, role="assistant", content="监考任务被中断。")

