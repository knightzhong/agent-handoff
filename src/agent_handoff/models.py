from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class FileSnapshot:
    path: str
    content: str
    truncated: bool = False


@dataclass
class ContextBundle:
    id: str
    created_at: str
    repo_root: str
    task: str
    note: str = ""
    git_status: str = ""
    git_diff: str = ""
    instructions: list[FileSnapshot] = field(default_factory=list)
    files: list[FileSnapshot] = field(default_factory=list)
    log: str = ""

    @classmethod
    def now(cls, *, bundle_id: str, repo_root: str, task: str, **kwargs: Any) -> ContextBundle:
        return cls(
            id=bundle_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            repo_root=repo_root,
            task=task,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextBundle:
        data = dict(data)
        data["instructions"] = [FileSnapshot(**x) for x in data.get("instructions", [])]
        data["files"] = [FileSnapshot(**x) for x in data.get("files", [])]
        return cls(**data)
