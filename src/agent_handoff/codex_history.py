from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_MAX_TRANSCRIPT_CHARS = 80_000


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def _session_cwd(path: Path) -> Path | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for _ in range(20):
                line = handle.readline()
                if not line:
                    break
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if item.get("type") != "session_meta":
                    continue
                payload = item.get("payload") or {}
                meta = payload.get("meta") if isinstance(payload, dict) else None
                data = meta if isinstance(meta, dict) else payload
                cwd = data.get("cwd") if isinstance(data, dict) else None
                if isinstance(cwd, str) and cwd.strip():
                    return Path(cwd).expanduser().resolve()
    except OSError:
        return None
    return None


def _same_repo(session_cwd: Path | None, repo_root: Path) -> bool:
    if session_cwd is None:
        return False
    try:
        return session_cwd == repo_root or session_cwd.is_relative_to(repo_root)
    except (OSError, ValueError):
        return False


def find_recent_codex_rollout(
    repo_root: Path,
    *,
    codex_home: Path | None = None,
    scan_limit: int = 80,
) -> Path | None:
    """Find the newest plain Codex rollout whose recorded cwd belongs to this repo.

    Codex persists interactive rollout JSONL under CODEX_HOME/sessions/YYYY/MM/DD.
    Compressed .zst archives are intentionally skipped because agent-handoff has no
    zstd dependency.
    """

    root = repo_root.resolve()
    sessions = (codex_home or default_codex_home()) / "sessions"
    if not sessions.is_dir():
        return None

    candidates: list[Path] = []
    try:
        candidates = sorted(
            sessions.rglob("rollout-*.jsonl"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return None

    for path in candidates[:scan_limit]:
        if _same_repo(_session_cwd(path), root):
            return path
    return None


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for element in content:
        if isinstance(element, str):
            parts.append(element)
            continue
        if not isinstance(element, dict):
            continue
        text = element.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(part for part in parts if part.strip()).strip()


def _message_from_item(item: dict[str, Any]) -> tuple[str, str] | None:
    item_type = item.get("type")
    payload = item.get("payload")
    if not isinstance(payload, dict):
        return None

    if item_type == "response_item" and payload.get("type") == "message":
        role = payload.get("role")
        if role not in {"user", "assistant"}:
            return None
        text = _content_text(payload.get("content"))
        return (role, text) if text else None

    if item_type == "event_msg":
        event_type = payload.get("type")
        if event_type == "user_message":
            text = payload.get("message")
            return ("user", text) if isinstance(text, str) and text.strip() else None
        if event_type in {"agent_message", "assistant_message"}:
            text = payload.get("message") or payload.get("text")
            return ("assistant", text) if isinstance(text, str) and text.strip() else None
    return None


def extract_codex_transcript(path: Path, *, max_chars: int = DEFAULT_MAX_TRANSCRIPT_CHARS) -> str:
    messages: list[tuple[str, str]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            message = _message_from_item(item)
            if message is None:
                continue
            # Codex can persist both response_item and event_msg copies of a user turn.
            if messages and messages[-1] == message:
                continue
            messages.append(message)

    rendered = [f"### {role}\n{text.strip()}" for role, text in messages if text.strip()]
    if not rendered:
        return ""

    selected: list[str] = []
    total = 0
    for block in reversed(rendered):
        size = len(block) + 2
        if selected and total + size > max_chars:
            break
        if not selected and size > max_chars:
            block = block[-max_chars:]
            block = "[... earlier content truncated ...]\n" + block
            size = len(block)
        selected.append(block)
        total += size
    selected.reverse()
    prefix = "[... earlier Codex turns omitted ...]\n\n" if len(selected) < len(rendered) else ""
    return prefix + "\n\n".join(selected)


def load_recent_codex_transcript(
    repo_root: Path,
    *,
    explicit_path: Path | None = None,
    codex_home: Path | None = None,
    max_chars: int = DEFAULT_MAX_TRANSCRIPT_CHARS,
) -> tuple[str, Path | None]:
    path = explicit_path.expanduser().resolve() if explicit_path else find_recent_codex_rollout(
        repo_root, codex_home=codex_home
    )
    if path is None:
        return "", None
    if not path.is_file():
        raise FileNotFoundError(path)
    return extract_codex_transcript(path, max_chars=max_chars), path
