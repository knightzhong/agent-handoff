from __future__ import annotations

import json
import os
import shlex
import subprocess

from .base import BackendResponse


class CommandBackend:
    def __init__(self, command: str):
        if not command.strip():
            raise ValueError("--command is required for command backend")
        self.command = command

    def ask(self, prompt: str, *, model: str | None = None) -> BackendResponse:
        env = os.environ.copy()
        if model:
            env["HANDOFF_MODEL"] = model
        proc = subprocess.run(
            shlex.split(self.command),
            input=prompt,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"command backend failed ({proc.returncode}): {proc.stderr[-2000:]}")
        return BackendResponse(
            text=proc.stdout.rstrip(), metadata={"backend": "command", "command": self.command}
        )


class BrowserBridgeBackend:
    def __init__(self, provider: str = "chatgpt", bridge_command: str | None = None):
        self.provider = provider
        self.bridge_command = bridge_command or os.getenv("HANDOFF_BRIDGE_COMMAND", "bridge")

    def ask(self, prompt: str, *, model: str | None = None) -> BackendResponse:
        cmd = [self.bridge_command, "ask", "--provider", self.provider, "--json", prompt]
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"browser bridge failed ({proc.returncode}): {proc.stderr[-2000:]}")
        raw = proc.stdout.strip()
        text = raw
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                if isinstance(data.get("reply"), str):
                    text = data["reply"]
                elif self.provider in data and isinstance(data[self.provider], dict):
                    text = str(data[self.provider].get("reply", raw))
        except json.JSONDecodeError:
            pass
        return BackendResponse(
            text=text,
            metadata={
                "backend": "browser-bridge",
                "provider": self.provider,
                "model": model or "session-default",
            },
        )
