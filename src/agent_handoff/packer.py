from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .models import ContextBundle, FileSnapshot
from .repo import find_repo_root, run_git, safe_path

MAX_FILE_BYTES = 64 * 1024
MAX_DIFF_CHARS = 120_000
MAX_LOG_CHARS = 60_000
INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md")


def _read_text(path: Path, limit: int = MAX_FILE_BYTES) -> tuple[str, bool]:
    data = path.read_bytes()
    if b"\x00" in data[:4096]:
        return "[binary file skipped]", False
    truncated = len(data) > limit
    data = data[:limit]
    text = data.decode("utf-8", errors="replace")
    if truncated:
        text += "\n\n[... truncated by agent-handoff ...]"
    return text, truncated


def _make_id(root: Path, task: str) -> str:
    seed = f"{root}:{task}:{os.urandom(8).hex()}".encode()
    return hashlib.sha256(seed).hexdigest()[:12]


def pack_context(
    task: str,
    *,
    root: Path | None = None,
    files: list[str] | None = None,
    note: str = "",
    log_path: str | None = None,
) -> ContextBundle:
    root = find_repo_root(root)
    selected: list[FileSnapshot] = []
    for raw in files or []:
        path = safe_path(root, raw)
        if not path.is_file():
            raise FileNotFoundError(path)
        content, truncated = _read_text(path)
        selected.append(FileSnapshot(str(path.relative_to(root)), content, truncated))

    instructions: list[FileSnapshot] = []
    for name in INSTRUCTION_FILES:
        path = root / name
        if path.is_file():
            content, truncated = _read_text(path)
            instructions.append(FileSnapshot(name, content, truncated))

    status = run_git(root, "status", "--short")
    unstaged = run_git(root, "diff", "--no-ext-diff")
    staged = run_git(root, "diff", "--cached", "--no-ext-diff")
    diff_parts = []
    if unstaged:
        diff_parts.append("# Unstaged diff\n" + unstaged)
    if staged:
        diff_parts.append("# Staged diff\n" + staged)
    diff = "\n\n".join(diff_parts)
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n\n[... diff truncated by agent-handoff ...]"

    log = ""
    if log_path:
        lp = Path(log_path).expanduser().resolve()
        if not lp.is_file():
            raise FileNotFoundError(lp)
        log = lp.read_text(encoding="utf-8", errors="replace")
        if len(log) > MAX_LOG_CHARS:
            log = log[-MAX_LOG_CHARS:]
            log = "[... beginning of log truncated ...]\n" + log

    return ContextBundle.now(
        bundle_id=_make_id(root, task),
        repo_root=str(root),
        task=task,
        note=note,
        git_status=status,
        git_diff=diff,
        instructions=instructions,
        files=selected,
        log=log,
    )


def render_bundle(bundle: ContextBundle) -> str:
    out = [
        "# Coding-agent handoff",
        "",
        "## Task",
        bundle.task.strip(),
    ]
    if bundle.note.strip():
        out += ["", "## Operator notes", bundle.note.strip()]
    if bundle.git_status:
        out += ["", "## Git status", "```text", bundle.git_status, "```"]
    if bundle.git_diff:
        out += ["", "## Current diff", "```diff", bundle.git_diff, "```"]
    if bundle.instructions:
        out += ["", "## Project instructions"]
        for item in bundle.instructions:
            out += [f"### {item.path}", "```text", item.content, "```"]
    if bundle.files:
        out += ["", "## Selected files"]
        for item in bundle.files:
            out += [f"### {item.path}", "```text", item.content, "```"]
    if bundle.log:
        out += ["", "## Recent test/error log", "```text", bundle.log, "```"]
    out += [
        "",
        "## Handoff request",
        (
            "Continue this coding task from the supplied state. Be concrete about the next changes. "
            "Do not claim you ran commands or edited files unless your transport actually "
            "provides those tools. Prefer a small patch plan, likely root cause, and validation "
            "steps."
        ),
        "",
    ]
    return "\n".join(out)


def save_bundle(bundle: ContextBundle, home: Path) -> Path:
    target = home / "bundles" / bundle.id
    target.mkdir(parents=True, exist_ok=True)
    (target / "bundle.json").write_text(
        json.dumps(bundle.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (target / "prompt.md").write_text(render_bundle(bundle), encoding="utf-8")
    (home / "latest").write_text(bundle.id, encoding="utf-8")
    return target
