from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis


class FactStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class SessionProgress:
    status: str
    last_stage_summary_ts: float
    last_utterance_ts: float


class RedisFactStore:
    """
    事实缓存与时间线存储模块（Redis）。

    约束：
    - 只存“事实”与“中间智能结果”
    - 不做任何智能决策
    - 所有数据可追溯、可按时间有序读取
    """

    def __init__(self, redis: Redis) -> None:
        self._r = redis

    @staticmethod
    def _k_meta(session_id: str) -> str:
        return f"class:{session_id}:meta"

    @staticmethod
    def _k_progress(session_id: str) -> str:
        return f"class:{session_id}:progress"

    @staticmethod
    def _k_utterances(session_id: str) -> str:
        return f"class:{session_id}:utterances"

    @staticmethod
    def _k_stage_summaries(session_id: str) -> str:
        return f"class:{session_id}:stage_summaries"

    @staticmethod
    def _k_final_report(session_id: str) -> str:
        return f"class:{session_id}:final_report"

    async def init_classroom(self, session_id: str, meta: dict[str, Any]) -> None:
        k_meta = self._k_meta(session_id)
        k_progress = self._k_progress(session_id)

        exists = await self._r.exists(k_meta)
        if exists:
            raise FactStoreError(f"classroom already exists: {session_id}")

        pipe = self._r.pipeline()
        pipe.hset(k_meta, mapping={"meta": json.dumps(meta, ensure_ascii=False)})
        pipe.hset(
            k_progress,
            mapping={
                "status": "RUNNING",
                "last_stage_summary_ts": "0",
                "last_utterance_ts": "0",
            },
        )
        await pipe.execute()

    async def set_status(self, session_id: str, status: str) -> None:
        await self._r.hset(self._k_progress(session_id), mapping={"status": status})

    async def get_progress(self, session_id: str) -> SessionProgress:
        m = await self._r.hgetall(self._k_progress(session_id))
        if not m:
            raise FactStoreError(f"classroom progress missing: {session_id}")

        def _get_str(key: str, default: str) -> str:
            v = m.get(key.encode("utf-8")) if isinstance(next(iter(m.keys())), (bytes, bytearray)) else m.get(key)
            if v is None:
                return default
            if isinstance(v, (bytes, bytearray)):
                return v.decode("utf-8", errors="replace")
            return str(v)

        status = _get_str("status", "UNKNOWN")
        last_stage_summary_ts = float(_get_str("last_stage_summary_ts", "0"))
        last_utterance_ts = float(_get_str("last_utterance_ts", "0"))
        return SessionProgress(
            status=status,
            last_stage_summary_ts=last_stage_summary_ts,
            last_utterance_ts=last_utterance_ts,
        )

    async def append_utterance(self, session_id: str, timestamp: float, utterance: dict[str, Any]) -> None:
        payload = json.dumps(utterance, ensure_ascii=False)
        k = self._k_utterances(session_id)
        pipe = self._r.pipeline()
        pipe.zadd(k, {payload: timestamp})
        pipe.hset(self._k_progress(session_id), mapping={"last_utterance_ts": str(timestamp)})
        await pipe.execute()

    async def list_utterances(
        self,
        session_id: str,
        *,
        start_ts_exclusive: float = 0.0,
        end_ts_inclusive: float = 1e18,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        k = self._k_utterances(session_id)
        items = await self._r.zrangebyscore(
            k,
            min=f"({start_ts_exclusive}",
            max=end_ts_inclusive,
            start=0,
            num=limit,
        )
        out: list[dict[str, Any]] = []
        for raw in items:
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", errors="replace")
            try:
                out.append(json.loads(raw))
            except Exception:
                continue
        return out

    async def append_stage_summary(self, session_id: str, timestamp: float, summary: dict[str, Any]) -> None:
        payload = json.dumps(summary, ensure_ascii=False)
        k = self._k_stage_summaries(session_id)
        pipe = self._r.pipeline()
        pipe.zadd(k, {payload: timestamp})
        pipe.hset(self._k_progress(session_id), mapping={"last_stage_summary_ts": str(timestamp)})
        await pipe.execute()

    async def list_stage_summaries(self, session_id: str, limit: int = 2000) -> list[dict[str, Any]]:
        k = self._k_stage_summaries(session_id)
        items = await self._r.zrange(k, 0, limit - 1)
        out: list[dict[str, Any]] = []
        for raw in items:
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", errors="replace")
            try:
                out.append(json.loads(raw))
            except Exception:
                continue
        return out

    async def set_final_report(self, session_id: str, report: dict[str, Any]) -> None:
        await self._r.set(self._k_final_report(session_id), json.dumps(report, ensure_ascii=False))

    async def get_final_report(self, session_id: str) -> dict[str, Any] | None:
        raw = await self._r.get(self._k_final_report(session_id))
        if raw is None:
            return None
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except Exception:
            return None
