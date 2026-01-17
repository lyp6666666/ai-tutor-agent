from __future__ import annotations

import re
from time import time

from app.agents.grader import HomeworkGrader
from app.agents.observer import ClassroomObserver
from app.agents.summarizer import LessonSummarizer
from app.core.event_bus import EventBus
from app.core.state_manager import StateManager
from app.schema.command import CommandRequest, CommandResponse
from app.schema.events import EmittedEvent
from app.schema.ingest import IngestEvent
from app.schema.report import ReportRequest, ReportResponse
from app.schema.summary import SummaryRequest, SummaryResponse

"""
    任务调度器类，负责根据事件类型调用相应的处理器。
        
    每个会话都有一个独立的任务状态，用于记录当前正在执行的任务。
    任务调度器会根据事件类型和任务状态，调用不同的处理器进行处理。
"""
class TaskDispatcher:
    def __init__(
        self,
        *,
        state_manager: StateManager,
        event_bus: EventBus,
        summarizer: LessonSummarizer,
        observer: ClassroomObserver,
        grader: HomeworkGrader,
    ) -> None:
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.summarizer = summarizer
        self.observer = observer
        self.grader = grader

    """
        处理事件的入口方法
        
        1. 根据事件类型和任务状态，调用不同的处理器进行处理
        2. 将处理器的输出事件添加到输出列表中
        3. 返回输出事件列表
    """
    async def on_event(self, event: IngestEvent) -> list[EmittedEvent]:
        session = await self.state_manager.get_session(event.session_id)

        outputs: list[EmittedEvent] = []
        observer_out = await self.observer.on_event(session, event)
        outputs.extend(observer_out)

        if event.type == "im_message" and event.im is not None:
            if self._is_teacher_command_im(event.im):
                cmd_text = self._extract_command_from_im(event.im.get("text", ""))
                cmd_req = CommandRequest(
                    session_id=event.session_id,
                    teacher_id=event.im.get("sender_id"),
                    command_text=cmd_text,
                    args={},
                )
                cmd_res = await self.on_command(cmd_req)
                outputs.extend(cmd_res.emitted_events)

        if session.active_task == "dictation":
            if event.type == "im_message" and event.im is not None:
                dict_out = await self._on_dictation_im(session, event.im["text"], event.im.get("sender_id"))
                outputs.extend(dict_out)

        return outputs

    async def on_command(self, req: CommandRequest) -> CommandResponse:
        session = await self.state_manager.get_session(req.session_id)
        text = req.command_text.strip()

        emitted: list[EmittedEvent] = []

        if self._is_start_dictation(text):
            words = req.args.get("words") if req.args else None
            if not words:
                words = self._extract_words_from_command(text) or ["apple", "banana", "orange"]

            session.dictation.active = True
            session.dictation.words = list(words)
            session.dictation.index = 0
            session.dictation.attempts = 0
            session.dictation.correct = 0
            session.active_task = "dictation"

            emitted.append(
                EmittedEvent(
                    type="agent_notice",
                    timestamp=time(),
                    payload={"task": "dictation", "status": "started", "words_count": len(words)},
                )
            )
            emitted.extend(await self._prompt_next_word(session))
            return CommandResponse(ok=True, active_task=session.active_task, emitted_events=emitted)

        if self._is_stop_task(text):
            prev = session.active_task
            session.active_task = None
            session.dictation.active = False
            emitted.append(
                EmittedEvent(
                    type="agent_notice",
                    timestamp=time(),
                    payload={"task": prev, "status": "stopped"},
                )
            )
            return CommandResponse(ok=True, active_task=session.active_task, emitted_events=emitted)

        if self._is_generate_summary(text):
            summary = await self.summarizer.summarize(session, prefer_llm=req.args.get("prefer_llm", False) if req.args else False)
            return CommandResponse(
                ok=True,
                active_task=session.active_task,
                emitted_events=[
                    EmittedEvent(type="summary_ready", timestamp=time(), payload=summary.model_dump())
                ],
            )

        return CommandResponse(
            ok=True,
            active_task=session.active_task,
            emitted_events=[
                EmittedEvent(
                    type="agent_notice",
                    timestamp=time(),
                    payload={"status": "ignored", "reason": "unknown_command", "command_text": text},
                )
            ],
        )

    async def generate_summary(self, req: SummaryRequest) -> SummaryResponse:
        session = await self.state_manager.get_session(req.session_id)
        result = await self.summarizer.summarize(session, prefer_llm=req.prefer_llm)
        return SummaryResponse(ok=True, session_id=req.session_id, result=result)

    async def generate_report(self, req: ReportRequest) -> ReportResponse:
        session = await self.state_manager.get_session(req.session_id)
        report = await self.observer.build_report(session, student_id=req.student_id)
        return ReportResponse(ok=True, session_id=req.session_id, report=report)

    def _is_start_dictation(self, text: str) -> bool:
        return bool(re.search(r"(开始|开启).*(单词)?听写", text))

    def _is_stop_task(self, text: str) -> bool:
        return bool(re.search(r"(停止|结束).*(任务|听写)?", text))

    def _is_generate_summary(self, text: str) -> bool:
        return bool(re.search(r"(生成|输出).*(总结|课后总结)", text))

    def _extract_words_from_command(self, text: str) -> list[str]:
        m = re.search(r"听写[:：]\s*(.+)$", text)
        if not m:
            return []
        parts = re.split(r"[,\s，、]+", m.group(1).strip())
        return [p for p in (x.strip() for x in parts) if p]

    def _is_teacher_command_im(self, im: dict) -> bool:
        if not im:
            return False
        if not (im.get("is_teacher") or im.get("role") == "teacher"):
            return False
        txt = (im.get("text") or "").strip()
        return txt.startswith("@AI") or txt.startswith("@AI助教") or txt.startswith("@AI 助教")

    def _extract_command_from_im(self, text: str) -> str:
        t = (text or "").strip()
        t = re.sub(r"^@AI(\s*助教)?\s*", "", t)
        return t.strip()

    async def _prompt_next_word(self, session) -> list[EmittedEvent]:
        if session.dictation.index >= len(session.dictation.words):
            acc = (session.dictation.correct / session.dictation.attempts) if session.dictation.attempts else 0.0
            session.active_task = None
            session.dictation.active = False
            return [
                EmittedEvent(
                    type="dictation_finished",
                    timestamp=time(),
                    payload={
                        "attempts": session.dictation.attempts,
                        "correct": session.dictation.correct,
                        "accuracy": round(acc, 4),
                    },
                )
            ]

        word = session.dictation.words[session.dictation.index]
        session.dictation.last_prompted_at = time()
        return [
            EmittedEvent(
                type="tts_request",
                timestamp=time(),
                payload={
                    "text": word,
                    "task": "dictation",
                    "index": session.dictation.index,
                    "total": len(session.dictation.words),
                },
            ),
            EmittedEvent(
                type="im_request",
                timestamp=time(),
                payload={
                    "text": f"请输入第 {session.dictation.index + 1}/{len(session.dictation.words)} 个单词的拼写",
                    "task": "dictation",
                },
            ),
        ]

    async def _on_dictation_im(self, session, student_text: str, sender_id: str | None) -> list[EmittedEvent]:
        expected = session.dictation.words[session.dictation.index]
        answer = (student_text or "").strip()
        session.dictation.attempts += 1
        is_correct = answer.lower() == expected.lower()
        if is_correct:
            session.dictation.correct += 1

        out = [
            EmittedEvent(
                type="dictation_result",
                timestamp=time(),
                payload={
                    "sender_id": sender_id,
                    "expected": expected,
                    "answer": answer,
                    "correct": is_correct,
                    "index": session.dictation.index,
                },
            )
        ]
        session.dictation.index += 1
        out.extend(await self._prompt_next_word(session))
        return out
