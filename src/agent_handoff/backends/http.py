from __future__ import annotations

import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .base import BackendResponse


def _post_json(url: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urlopen(request, timeout=300) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"backend HTTP {exc.code}: {detail[:1000]}") from exc


class OpenAICompatibleBackend:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        default = os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        self.base_url = (base_url or default).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")

    def ask(self, prompt: str, *, model: str | None = None) -> BackendResponse:
        if not model:
            raise ValueError("--model is required for openai-compatible")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        data = _post_json(
            f"{self.base_url}/chat/completions",
            {"model": model, "messages": [{"role": "user", "content": prompt}]},
            headers,
        )
        text = data["choices"][0]["message"]["content"]
        return BackendResponse(text=text, metadata={"backend": "openai-compatible", "model": model})


class OllamaBackend:
    def __init__(self, host: str | None = None):
        self.host = (host or os.getenv("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")

    def ask(self, prompt: str, *, model: str | None = None) -> BackendResponse:
        if not model:
            raise ValueError("--model is required for ollama")
        data = _post_json(
            f"{self.host}/api/chat",
            {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False},
        )
        return BackendResponse(
            text=data["message"]["content"], metadata={"backend": "ollama", "model": model}
        )
