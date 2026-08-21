import subprocess
from pathlib import Path

from agent_handoff.backends.base import BackendResponse
from agent_handoff.store import handoff_home
from agent_handoff.takeover import (
    create_takeover_session,
    load_turns,
    run_takeover_turn,
    takeover_banner,
)


class FakeBackend:
    def __init__(self) -> None:
        self.prompt = ""

    def ask(self, prompt: str, *, model: str | None = None) -> BackendResponse:
        self.prompt = prompt
        return BackendResponse("fallback reply", {"backend": "fake", "model": model or "fake"})


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_takeover_is_explicit_and_persists_turns(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "app.py").write_text("print('hello')\n")
    git(tmp_path, "add", "app.py")
    git(tmp_path, "commit", "-qm", "init")

    session = create_takeover_session(
        root=tmp_path,
        task="keep debugging",
        files=["app.py"],
        note="",
        log_path=None,
        source="codex",
        backend="command",
        provider="chatgpt",
        model=None,
        base_url=None,
        import_codex_history=False,
    )
    fake = FakeBackend()
    response = run_takeover_turn(session, "what should I try next?", root=tmp_path, client=fake)

    assert response.text == "fallback reply"
    assert "explicitly switched from **codex**" in fake.prompt
    assert "what should I try next?" in fake.prompt
    assert "No silent switching" in takeover_banner(session)
    turns = load_turns(handoff_home(tmp_path), session)
    assert [turn["role"] for turn in turns] == ["user", "assistant"]
    assert turns[-1]["text"] == "fallback reply"
    assert (tmp_path / ".handoff" / "bundles" / session.bundle_id / "response.md").exists()
