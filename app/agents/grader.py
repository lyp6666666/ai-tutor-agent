from __future__ import annotations

from difflib import SequenceMatcher


class HomeworkGrader:
    async def grade_text(self, student_answer: str, standard_answer: str) -> dict:
        s = (student_answer or "").strip()
        t = (standard_answer or "").strip()
        ratio = SequenceMatcher(a=s.lower(), b=t.lower()).ratio() if (s and t) else 0.0
        score = int(round(ratio * 100))
        correct = score >= 90
        reason = "与标准答案高度一致" if correct else "与标准答案存在差异"
        return {"correct": correct, "score": score, "reason": reason}

    async def grade_image(self, image_bytes: bytes, standard_answer: str) -> dict:
        # TODO: 接入OCR（如PaddleOCR）后将图片转文本，再复用 grade_text
        return {"correct": False, "score": 0, "reason": "TODO: 图片作业批改需要OCR能力"}

