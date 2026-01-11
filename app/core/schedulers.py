from __future__ import annotations

import asyncio
from time import time

from app.core.settings import Settings
from app.core.summarization import LlmSummarizer
from app.infra.redis_fact_store import RedisFactStore


class StageSummaryScheduler:
    """
    阶段性智能处理层：周期性扫描 RUNNING 课堂，触发阶段总结。
    """

    def __init__(self, *, store: RedisFactStore, summarizer: LlmSummarizer, settings: Settings) -> None:
        self._store = store
        self._summarizer = summarizer
        self._settings = settings
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="stage-summary-scheduler")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await asyncio.wait([self._task], timeout=3.0)

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick()
            except Exception:
                pass
            await asyncio.sleep(2.0)

    async def _tick(self) -> None:
        sessions = await self._list_running_sessions()
        for session_id in sessions:
            try:
                await self._process_session(session_id)
            except Exception:
                continue

    async def _list_running_sessions(self) -> list[str]:
        keys = await self._store._r.keys("class:*:progress")
        out: list[str] = []
        for k in keys:
            if isinstance(k, (bytes, bytearray)):
                k = k.decode("utf-8", errors="replace")
            parts = str(k).split(":")
            if len(parts) < 3:
                continue
            session_id = parts[1]
            try:
                prog = await self._store.get_progress(session_id)
            except Exception:
                continue
            if prog.status == "RUNNING":
                out.append(session_id)
        return out

    async def _process_session(self, session_id: str) -> None:
        prog = await self._store.get_progress(session_id)
        now = time()
        if (now - prog.last_stage_summary_ts) < self._settings.stage_summary_min_interval_s:
            return

        utterances = await self._store.list_utterances(
            session_id,
            start_ts_exclusive=prog.last_stage_summary_ts,
            limit=self._settings.stage_summary_max_utterances,
        )
        if not utterances:
            return

        text = "\n".join(
            [f"[{u.get('role')}][{u.get('user_name')}] {u.get('text')}" for u in utterances if u.get("text")]
        ).strip()
        if len(text) < self._settings.stage_summary_min_chars:
            return

        stage = await self._summarizer.summarize_stage(utterances_text=text)
        await self._store.append_stage_summary(
            session_id,
            stage.timestamp,
            {
                "timestamp": stage.timestamp,
                "summary": stage.summary,
                "knowledge_points": stage.knowledge_points,
                "classroom_insights": stage.classroom_insights,
                "window": {
                    "start_ts_exclusive": prog.last_stage_summary_ts,
                    "end_ts_inclusive": utterances[-1].get("timestamp", stage.timestamp),
                },
            },
        )

