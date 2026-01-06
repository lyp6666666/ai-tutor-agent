from __future__ import annotations

from time import time

from app.core.state_manager import SessionState
from app.schema.events import EmittedEvent
from app.schema.ingest import IngestEvent
from app.schema.report import ClassroomReport


class ClassroomObserver:
    async def on_event(self, session: SessionState, event: IngestEvent) -> list[EmittedEvent]:
        if event.type == "im_message" and event.im is not None:
            sender = event.im.get("sender_id") or "unknown"
            session.observer.utterances_by_user[sender] = session.observer.utterances_by_user.get(sender, 0) + 1

        if event.type == "video_event" and event.video is not None:
            session.observer.focus_events.append(
                {
                    "timestamp": event.timestamp,
                    "event": event.video.get("event"),
                    "student_id": event.video.get("student_id"),
                    "payload": event.video,
                }
            )
        return []

    async def build_report(self, session: SessionState, student_id: str) -> ClassroomReport:
        utterances = session.observer.utterances_by_user.get(student_id, 0)
        total = session.observer.total_answers_by_user.get(student_id, 0)
        correct = session.observer.correct_answers_by_user.get(student_id, 0)
        acc = (correct / total) if total else 0.0

        focus_score = self._focus_score(session, student_id)
        participation = "active" if utterances >= 5 else "normal" if utterances >= 2 else "silent"

        return ClassroomReport(
            student_id=student_id,
            participation=participation,
            focus_score=focus_score,
            utterances=utterances,
            answer_accuracy=round(acc, 4),
        )

    def _focus_score(self, session: SessionState, student_id: str) -> float:
        events = [e for e in session.observer.focus_events if e.get("student_id") == student_id]
        if not events:
            return 1.0
        bad = 0
        for e in events:
            if e.get("event") in {"MULTIPLE_PERSON", "LEAVE_SEAT", "HEAD_DOWN_FREQUENT"}:
                bad += 1
        score = max(0.0, 1.0 - 0.1 * bad)
        return round(score, 4)

