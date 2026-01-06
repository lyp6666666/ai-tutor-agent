from __future__ import annotations

from app.agents.grader import HomeworkGrader
from app.agents.observer import ClassroomObserver
from app.agents.summarizer import LessonSummarizer
from app.core.event_bus import EventBus
from app.core.state_manager import StateManager
from app.core.task_dispatcher import TaskDispatcher
from app.schema.command import CommandRequest, CommandResponse
from app.schema.events import EmittedEvent
from app.schema.ingest import IngestEvent
from app.schema.report import ReportRequest, ReportResponse
from app.schema.summary import SummaryRequest, SummaryResponse


class AppContext:
    def __init__(self) -> None:
        self.event_bus = EventBus()
        self.state_manager = StateManager()
        self.dispatcher = TaskDispatcher(
            state_manager=self.state_manager,
            event_bus=self.event_bus,
            summarizer=LessonSummarizer(),
            observer=ClassroomObserver(),
            grader=HomeworkGrader(),
        )

    async def ingest_event(self, event: IngestEvent) -> list[EmittedEvent]:
        await self.state_manager.append_event(event)
        outputs = await self.dispatcher.on_event(event)
        for out in outputs:
            await self.event_bus.publish(event.session_id, out)
        return outputs

    async def handle_command(self, req: CommandRequest) -> CommandResponse:
        result = await self.dispatcher.on_command(req)
        for out in result.emitted_events:
            await self.event_bus.publish(req.session_id, out)
        return result

    async def generate_summary(self, req: SummaryRequest) -> SummaryResponse:
        return await self.dispatcher.generate_summary(req)

    async def generate_report(self, req: ReportRequest) -> ReportResponse:
        return await self.dispatcher.generate_report(req)

