from __future__ import annotations

import subprocess
from pathlib import Path


class RepoError(RuntimeError):
    pass


def run_git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.rstrip()


def find_repo_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        return Path(proc.stdout.strip()).resolve()
    return start


def safe_path(root: Path, raw: str | Path) -> Path:
    candidate = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RepoError(f"path escapes repository root: {raw}") from exc
    return candidate
