# Contributing

Thanks for helping improve `agent-handoff`.

- Keep backends isolated from context packing.
- Never commit credentials, cookies, or session tokens.
- New remote transports should document their authentication and terms assumptions.
- Add tests for path validation and response parsing.
- Prefer explicit user-controlled behavior over automatic quota/rate-limit circumvention.

Run `ruff check .` and `pytest -q` before opening a pull request.
