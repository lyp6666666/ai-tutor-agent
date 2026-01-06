from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AudioBuffer:
    asr_items: list[str] = field(default_factory=list)

    def append_asr(self, text: str) -> None:
        if text:
            self.asr_items.append(text)

    def tail_asr(self, n: int = 200) -> list[str]:
        return self.asr_items[-n:]

