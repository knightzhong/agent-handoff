import subprocess
from pathlib import Path

import pytest

from agent_handoff.packer import pack_context, render_bundle, save_bundle
from agent_handoff.repo import RepoError, safe_path
from agent_handoff.store import load_bundle


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.PIPE)


def test_pack_roundtrip(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "AGENTS.md").write_text("Keep changes small.\n")
    (tmp_path / "app.py").write_text("print('a')\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "init")
    (tmp_path / "app.py").write_text("print('b')\n")

    bundle = pack_context("change output", root=tmp_path, files=["app.py"], note="test")
    assert "app.py" in bundle.git_status
    assert "print('b')" in bundle.git_diff
    assert bundle.instructions[0].path == "AGENTS.md"
    assert bundle.files[0].path == "app.py"
    assert "change output" in render_bundle(bundle)

    home = tmp_path / ".handoff"
    save_bundle(bundle, home)
    loaded = load_bundle(home)
    assert loaded.id == bundle.id
    assert loaded.files[0].content == bundle.files[0].content


def test_safe_path_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(RepoError):
        safe_path(tmp_path, "../secret.txt")
