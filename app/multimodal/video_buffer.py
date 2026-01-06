from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VideoBuffer:
    events: list[dict] = field(default_factory=list)

    def append(self, event: dict) -> None:
        self.events.append(event)

    def tail(self, n: int = 200) -> list[dict]:
        return self.events[-n:]

