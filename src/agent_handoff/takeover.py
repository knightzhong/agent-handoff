from __future__ import annotations

import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from .backends.base import Backend, BackendResponse
from .codex_history import load_recent_codex_transcript
from .models import ContextBundle
from .packer import pack_context, render_bundle, save_bundle
from .repo import find_repo_root, run_git
from .runtime import build_backend, resume_prompt, save_response
from .store import handoff_home, load_bundle

MAX_TAKEOVER_HISTORY_CHARS = 60_000


@dataclass
class TakeoverSession:
    id: str
    bundle_id: str
    repo_root: str
    source: str
    backend: str
    provider: str
    model: str | None
    base_url: str | None
    imported_context: str = ""
    imported_context_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "bundle_id": self.bundle_id,
            "repo_root": self.repo_root,
            "source": self.source,
            "backend": self.backend,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "imported_context": self.imported_context,
            "imported_context_path": self.imported_context_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> TakeoverSession:
        return cls(
            id=str(data["id"]),
            bundle_id=str(data["bundle_id"]),
            repo_root=str(data["repo_root"]),
            source=str(data["source"]),
            backend=str(data["backend"]),
            provider=str(data.get("provider") or "chatgpt"),
            model=str(data["model"]) if data.get("model") is not None else None,
            base_url=str(data["base_url"]) if data.get("base_url") is not None else None,
            imported_context=str(data.get("imported_context") or ""),
            imported_context_path=(
                str(data["imported_context_path"])
                if data.get("imported_context_path") is not None
                else None
            ),
        )


def _session_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{secrets.token_hex(3)}"


def _sessions_home(home: Path) -> Path:
    return home / "sessions"


def session_dir(home: Path, session_id: str) -> Path:
    return _sessions_home(home) / session_id


def create_takeover_session(
    *,
    root: Path,
    task: str,
    files: list[str],
    note: str,
    log_path: str | None,
    source: str,
    backend: str,
    provider: str,
    model: str | None,
    base_url: str | None,
    import_codex_history: bool = True,
    codex_session: Path | None = None,
) -> TakeoverSession:
    root = find_repo_root(root)
    home = handoff_home(root)
    bundle = pack_context(task, root=root, files=files, note=note, log_path=log_path)
    save_bundle(bundle, home)

    imported = ""
    imported_path: Path | None = None
    if source.lower() == "codex" and import_codex_history:
        imported, imported_path = load_recent_codex_transcript(
            root,
            explicit_path=codex_session,
        )

    session = TakeoverSession(
        id=_session_id(),
        bundle_id=bundle.id,
        repo_root=str(root),
        source=source,
        backend=backend,
        provider=provider,
        model=model,
        base_url=base_url,
        imported_context=imported,
        imported_context_path=str(imported_path) if imported_path else None,
    )
    target = session_dir(home, session.id)
    target.mkdir(parents=True, exist_ok=True)
    (target / "session.json").write_text(
        json.dumps(session.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if imported:
        (target / "imported-context.md").write_text(imported + "\n", encoding="utf-8")
    (home / "latest_takeover").write_text(session.id, encoding="utf-8")
    return session


def resolve_takeover_id(home: Path, session_id: str | None = None) -> str:
    if session_id:
        return session_id
    latest = home / "latest_takeover"
    if not latest.exists():
        raise FileNotFoundError("no takeover session found; run `handoff takeover` first")
    return latest.read_text(encoding="utf-8").strip()


def load_takeover_session(home: Path, session_id: str | None = None) -> TakeoverSession:
    resolved = resolve_takeover_id(home, session_id)
    path = session_dir(home, resolved) / "session.json"
    return TakeoverSession.from_dict(json.loads(path.read_text(encoding="utf-8")))


def append_turn(home: Path, session: TakeoverSession, role: str, text: str) -> None:
    target = session_dir(home, session.id)
    target.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "text": text,
    }
    with (target / "transcript.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_turns(home: Path, session: TakeoverSession) -> list[dict[str, str]]:
    path = session_dir(home, session.id) / "transcript.jsonl"
    if not path.exists():
        return []
    turns: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("text"), str):
            turns.append({"role": str(data.get("role") or "unknown"), "text": data["text"]})
    return turns


def _render_turns(turns: list[dict[str, str]]) -> str:
    blocks = [
        f"### {turn['role']}\n{turn['text'].strip()}"
        for turn in turns
        if turn["text"].strip()
    ]
    selected: list[str] = []
    total = 0
    for block in reversed(blocks):
        size = len(block) + 2
        if selected and total + size > MAX_TAKEOVER_HISTORY_CHARS:
            break
        selected.append(block)
        total += size
    selected.reverse()
    prefix = "[... earlier takeover turns omitted ...]\n\n" if len(selected) < len(blocks) else ""
    return prefix + "\n\n".join(selected)


def takeover_prompt(
    *,
    session: TakeoverSession,
    bundle: ContextBundle,
    turns: list[dict[str, str]],
    root: Path,
) -> str:
    active = session.provider if session.backend == "browser-bridge" else session.backend
    current_status = run_git(root, "status", "--short")
    current_diff = run_git(root, "diff", "--no-ext-diff")
    imported = session.imported_context.strip() or "[no previous agent transcript was imported]"
    conversation = _render_turns(turns) or "[this is the first fallback turn]"
    return f"""# Manual coding-agent takeover

The user explicitly switched from **{session.source}** to **{active}** using agent-handoff.
This is not a silent model switch. Do not claim to still be {session.source}; if identity matters,
state that you are the active fallback backend. Continue the same task as faithfully as possible.

## Repository handoff bundle

{render_bundle(bundle)}

## Imported {session.source} conversation

{imported}

## Conversation since takeover

{conversation}

## Repository state right now

```text
{current_status}
```

```diff
{current_diff}
```

Answer the latest user message in the takeover conversation. Use the imported history and repository
state for continuity. Do not pretend that you ran tools or changed files unless this backend
actually did so.
"""


def backend_label(session: TakeoverSession) -> str:
    if session.backend == "browser-bridge":
        return f"browser-bridge/{session.provider}"
    if session.model:
        return f"{session.backend}/{session.model}"
    return session.backend


def takeover_banner(session: TakeoverSession) -> str:
    imported = session.imported_context_path or "none"
    return (
        "=== MANUAL TAKEOVER ACTIVE ===\n"
        f"source: {session.source}\n"
        f"active backend: {backend_label(session)}\n"
        f"takeover session: {session.id}\n"
        f"imported source history: {imported}\n"
        "No silent switching: assistant replies in this session come from the active backend.\n"
        "Commands: /status  /resume  /help  /quit"
    )


def run_takeover_turn(
    session: TakeoverSession,
    message: str,
    *,
    root: Path | None = None,
    command: str | None = None,
    client: Backend | None = None,
) -> BackendResponse:
    root = find_repo_root(root or Path(session.repo_root))
    home = handoff_home(root)
    append_turn(home, session, "user", message)
    turns = load_turns(home, session)
    bundle = load_bundle(home, session.bundle_id)
    prompt = takeover_prompt(session=session, bundle=bundle, turns=turns, root=root)
    if client is None:
        client = build_backend(
            session.backend,
            base_url=session.base_url,
            command=command,
            provider=session.provider,
        )
    response = client.ask(prompt, model=session.model)
    append_turn(home, session, "assistant", response.text)
    save_response(home, bundle.id, response)
    return response


def takeover_status(session: TakeoverSession) -> str:
    return (
        f"manual takeover {session.id}: {session.source} -> {backend_label(session)}; "
        f"bundle={session.bundle_id}"
    )


def takeover_repl(
    session: TakeoverSession,
    *,
    root: Path,
    command: str | None = None,
    input_fn: Callable[[str], str] = input,
    out: TextIO,
    err: TextIO,
) -> int:
    print(takeover_banner(session), file=err)
    while True:
        try:
            message = input_fn(f"[you -> {backend_label(session)}] > ").strip()
        except EOFError:
            print("\nTakeover session saved. Resume with `handoff takeover --resume`.", file=err)
            return 0
        if not message:
            continue
        if message in {"/quit", "/exit"}:
            print("Takeover session saved. Resume with `handoff takeover --resume`.", file=err)
            return 0
        if message == "/status":
            print(takeover_status(session), file=err)
            continue
        if message == "/help":
            print(
                "/status show active backend; /resume print handback prompt; /quit save and exit",
                file=err,
            )
            continue
        if message == "/resume":
            print(resume_prompt(bundle_id=session.bundle_id, root=root), file=out)
            continue
        response = run_takeover_turn(session, message, root=root, command=command)
        print(f"\n[{backend_label(session)}]\n{response.text}\n", file=out)
