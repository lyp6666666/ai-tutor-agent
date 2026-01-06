from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TextBuffer:
    items: list[str] = field(default_factory=list)

    def append(self, text: str) -> None:
        if text:
            self.items.append(text)

    def tail(self, n: int = 200) -> list[str]:
        return self.items[-n:]

