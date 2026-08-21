from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class BackendResponse:
    text: str
    metadata: dict[str, object]


class Backend(Protocol):
    def ask(self, prompt: str, *, model: str | None = None) -> BackendResponse: ...
