from __future__ import annotations

import json
from pathlib import Path

from .backends import BrowserBridgeBackend, CommandBackend, OllamaBackend, OpenAICompatibleBackend
from .packer import render_bundle
from .repo import find_repo_root, run_git
from .store import bundle_dir, handoff_home, load_bundle


def build_backend(
    backend: str,
    *,
    base_url: str | None = None,
    command: str | None = None,
    provider: str = "chatgpt",
):
    if backend == "openai-compatible":
        return OpenAICompatibleBackend(base_url=base_url)
    if backend == "ollama":
        return OllamaBackend(host=base_url)
    if backend == "command":
        return CommandBackend(command or "")
    if backend == "browser-bridge":
        return BrowserBridgeBackend(provider=provider, bridge_command=command)
    raise ValueError(f"unknown backend: {backend}")


def ask_bundle(
    *,
    backend: str,
    model: str | None = None,
    bundle_id: str | None = None,
    root: Path | None = None,
    base_url: str | None = None,
    command: str | None = None,
    provider: str = "chatgpt",
) -> Path:
    root = find_repo_root(root)
    home = handoff_home(root)
    bundle = load_bundle(home, bundle_id)
    prompt = render_bundle(bundle)
    client = build_backend(backend, base_url=base_url, command=command, provider=provider)
    response = client.ask(prompt, model=model)
    target = bundle_dir(home, bundle.id)
    (target / "response.md").write_text(response.text + "\n", encoding="utf-8")
    (target / "response.json").write_text(
        json.dumps(
            {"text": response.text, "metadata": response.metadata},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return target / "response.md"


def resume_prompt(*, bundle_id: str | None = None, root: Path | None = None) -> str:
    root = find_repo_root(root)
    home = handoff_home(root)
    bundle = load_bundle(home, bundle_id)
    target = bundle_dir(home, bundle.id)
    response_path = target / "response.md"
    response = (
        response_path.read_text(encoding="utf-8").strip()
        if response_path.exists()
        else "[no response yet]"
    )
    current_status = run_git(root, "status", "--short")
    current_diff = run_git(root, "diff", "--no-ext-diff")
    return f"""# Resume coding task

Original task:
{bundle.task}

A secondary backend returned:
---
{response}
---

Current git status:
```text
{current_status}
```

Current unstaged diff:
```diff
{current_diff}
```

Resume the task in this repository. Treat the secondary response as advice, not ground truth.
Inspect the actual files, make only justified edits, run relevant tests, and report what changed.
"""
