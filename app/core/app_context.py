from __future__ import annotations

import asyncio
from time import time

from redis.asyncio import Redis

from app.core.event_bus import EventBus
from app.core.asr_client import VolcengineAsrWsClient
from app.core.classroom_session_manager import ClassroomSessionManager
from app.core.schedulers import StageSummaryScheduler
from app.core.settings import settings
from app.core.summarization import LlmSummarizer
from app.infra.redis_fact_store import RedisFactStore
from app.llm.ark_client import ArkChatClient
from app.schema.events import EmittedEvent
from app.schema.agent_command import AgentCommandRequest
from app.schema.classroom import ClassroomOpenRequest, RealtimeAudioFrame, UtteranceFact


class AppContext:
    """
    全局应用上下文（进程级）。

    设计目标：
    - 第一层：接入实时数据并写入 Redis 事实存储
    - 第二层：后台调度阶段性总结（从 Redis 读事实 -> 调 LLM -> 写回 Redis）
    - 指令接口：从 Redis 读取上下文，调用 LLM 生成回复，通过事件总线推送到前端 WS
    """

    def __init__(self) -> None:
        self.event_bus = EventBus()
        self.session_manager = ClassroomSessionManager()

        self.redis: Redis = Redis.from_url(settings.redis_url, decode_responses=False)
        self.store = RedisFactStore(self.redis)

        if not settings.ark_api_key:
            raise RuntimeError("缺少 ARK_API_KEY：请通过环境变量配置火山方舟 API Key。")
        self.llm_client = ArkChatClient(
            base_url=settings.ark_base_url,
            api_key=settings.ark_api_key,
            model=settings.ark_model,
        )
        self.summarizer = LlmSummarizer(self.llm_client)

        self.stage_scheduler = StageSummaryScheduler(store=self.store, summarizer=self.summarizer, settings=settings)
        self._bg_started = False

    async def start_background(self) -> None:
        if self._bg_started:
            return
        self._bg_started = True
        self.stage_scheduler.start()

    async def shutdown(self) -> None:
        await self.stage_scheduler.stop()
        await self.llm_client.aclose()
        await self.redis.aclose()

    async def open_classroom(self, req: ClassroomOpenRequest) -> None:
        session = await self.session_manager.create(req.session_id)
        await self.store.init_classroom(req.session_id, req.model_dump())

        session.asr = VolcengineAsrWsClient(session_id=req.session_id)
        await session.asr.connect()

    async def end_classroom(self, session_id: str, end_time: float) -> None:
        await self.session_manager.mark_ending(session_id)
        await self.store.set_status(session_id, "ENDING")

        await asyncio.sleep(0)

        await self.store.set_status(session_id, "ENDED")
        await self.session_manager.mark_ended(session_id)
        asyncio.create_task(self._generate_final_report(session_id), name=f"final-report-{session_id}")

    async def _generate_final_report(self, session_id: str) -> None:
        utterances = await self.store.list_utterances(session_id, start_ts_exclusive=0.0, limit=5000)
        stage_summaries = await self.store.list_stage_summaries(session_id, limit=2000)

        utter_text = "\n".join(
            [f"[{u.get('role')}][{u.get('user_name')}] {u.get('text')}" for u in utterances if u.get("text")]
        ).strip()
        stage_text = "\n".join(
            [f"[{s.get('timestamp')}] {s.get('summary')}" for s in stage_summaries if s.get("summary")]
        ).strip()

        report = await self.summarizer.summarize_final(
            utterances_text=utter_text,
            stage_summaries_text=stage_text,
            course_meta_text=None,
        )
        report_payload = {"session_id": session_id, "timestamp": time(), "result": report}
        await self.store.set_final_report(session_id, report_payload)
        await self.event_bus.publish(session_id, EmittedEvent(type="final_report_ready", timestamp=time(), payload=report_payload))

    async def handle_realtime_audio_frame(self, frame: RealtimeAudioFrame) -> None:
        session = await self.session_manager.get(frame.session_id)
        async with session.lock:
            if session.status != "RUNNING":
                raise RuntimeError(f"classroom not running: {frame.session_id} status={session.status}")

            if session.asr is None:
                session.asr = VolcengineAsrWsClient(session_id=frame.session_id)
                await session.asr.connect()
            _ = session.asr.validate_audio_chunk(frame.audio_chunk)

            if frame.mock_text:
                fact = UtteranceFact(
                    session_id=frame.session_id,
                    user_id=frame.user_id,
                    user_name=frame.user_name,
                    role=frame.role,
                    text=frame.mock_text,
                    start_time=frame.timestamp,
                    end_time=frame.timestamp,
                    timestamp=frame.timestamp,
                    confidence=1.0,
                )
                await self.store.append_utterance(frame.session_id, frame.timestamp, fact.model_dump())

    async def handle_agent_command(self, req: AgentCommandRequest) -> None:
        prog = await self.store.get_progress(req.session_id)
        utterances = await self.store.list_utterances(
            req.session_id,
            start_ts_exclusive=max(0.0, prog.last_stage_summary_ts - 3600),
            limit=500,
        )
        stage_summaries = await self.store.list_stage_summaries(req.session_id, limit=200)

        context_lines: list[str] = []
        if stage_summaries:
            last = stage_summaries[-1]
            if last.get("summary"):
                context_lines.append(f"[阶段总结] {last.get('summary')}")
        for u in utterances[-80:]:
            context_lines.append(f"[{u.get('role')}][{u.get('user_name')}] {u.get('text')}")
        context = "\n".join([x for x in context_lines if x.strip()]).strip()

        reply = await self.summarizer.command_reply(
            instruction=req.instruction,
            image_url=req.image_url,
            context_text=context,
        )
        event = EmittedEvent(
            type="im_request",
            timestamp=time(),
            payload={"text": reply, "task": "agent_command"},
        )
        await self.event_bus.publish(req.session_id, event)

    async def list_stage_summaries(self, session_id: str) -> list[dict]:
        return await self.store.list_stage_summaries(session_id, limit=2000)

    async def get_final_report(self, session_id: str) -> dict | None:
        return await self.store.get_final_report(session_id)
