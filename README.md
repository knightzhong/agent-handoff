# agent-handoff

**Keep the work when the model changes.**

`agent-handoff` packages the state of a coding task — goal, git status/diff, project instructions,
selected files, and recent failures — into a portable bundle that can be handed to another LLM
backend and later resumed locally.

It is deliberately a **context continuity layer**, not a quota-bypass tool. Backends are explicit,
user-configured transports. The browser adapter delegates to an external bridge command rather than
scraping or authenticating to a web service itself.

## Why

Coding agents often stop for reasons unrelated to the task: provider outage, rate limiting, cost,
model availability, or simply because you want a second model to review the work. A normal retry
loses the important state scattered across the repository and terminal.

`agent-handoff` turns that state into a small, inspectable artifact:

```text
workspace
  │
  ├─ task / notes
  ├─ AGENTS.md / CLAUDE.md
  ├─ git status + diff
  ├─ selected files
  └─ test/error log
       │
       ▼
  handoff pack
       │
       ▼
 .handoff/bundles/<id>/
       │
       ├──────────► OpenAI-compatible endpoint
       ├──────────► Ollama
       ├──────────► arbitrary command
       └──────────► browser bridge command
                         │
                         ▼
                    response.md
                         │
                         ▼
                   handoff resume
```

## Quick start

```bash
pip install -e .

# 1. Package current repo state
handoff pack --task "Fix the flaky retry test" --log /tmp/pytest.log

# 2. Ask another backend using the latest bundle
handoff ask --backend ollama --model qwen3-coder:latest

# or any OpenAI-compatible endpoint
export OPENAI_API_KEY=...
handoff ask --backend openai-compatible --model gpt-5-mini \
  --base-url https://api.openai.com/v1

# or a local/custom command. The prompt is sent on stdin.
handoff ask --backend command --command 'my-agent --stdin'

# or delegate to an installed browser bridge (for example ai-browser-bridge)
handoff ask --backend browser-bridge --provider chatgpt

# 3. Print a compact continuation prompt for your original coding agent
handoff resume
```

## Commands

### `handoff pack`

Collects:

- task text
- `git status --short`
- staged + unstaged diff
- `AGENTS.md`, `CLAUDE.md`, and `CONTRIBUTING.md` when present
- explicitly selected files (`--file` can be repeated)
- a test/error log (`--log`)
- optional notes (`--note`)

Binary files are skipped, paths are constrained to the repository root, and large text inputs are
truncated with a marker. Bundles are JSON plus a rendered Markdown prompt under `.handoff/`.

### `handoff ask`

Available backend IDs:

| Backend | Transport |
|---|---|
| `openai-compatible` | `/chat/completions` over HTTP |
| `ollama` | local `/api/chat` |
| `command` | arbitrary local process, prompt via stdin |
| `browser-bridge` | external `bridge ask --json` command |

The response is stored next to the bundle, so a later agent can inspect exactly what was sent and
what came back.

### `handoff resume`

Emits a continuation prompt containing the original task, current repository state, and the most
recent handoff response. It does **not** automatically apply model-generated patches; the coding
agent remains responsible for validating edits and tests.

## MCP server

Install the optional dependency:

```bash
pip install -e '.[mcp]'
handoff-mcp
```

The stdio MCP server exposes:

- `pack_context(task, files?, note?)`
- `ask_handoff(backend, model?, bundle_id?)`
- `resume_handoff(bundle_id?)`

That lets Codex, Claude Code, or another MCP-capable coding agent use the handoff runtime as a tool
without forking the agent.

Example client configuration:

```json
{
  "mcpServers": {
    "agent-handoff": {
      "command": "handoff-mcp"
    }
  }
}
```

## Configuration

Environment variables:

```text
HANDOFF_HOME              default: <repo>/.handoff
OPENAI_API_KEY            used by openai-compatible
OPENAI_BASE_URL           default: https://api.openai.com/v1
OLLAMA_HOST                default: http://127.0.0.1:11434
HANDOFF_BRIDGE_COMMAND     default: bridge
```

Nothing secret is written into a bundle by the library. You should still review selected files and
`git diff` before sending a bundle to any remote model.

## Design principles

1. **Inspectability** — every handoff is a plain JSON/Markdown artifact.
2. **Local-first state** — no hosted coordinator is required.
3. **Backend neutrality** — transport and context packing are separate.
4. **Explicit trust** — browser/API credentials belong to the backend, not this project.
5. **Verification over auto-apply** — generated code returns to the coding agent for review/tests.

## Development

```bash
python -m pip install -e '.[dev]'
pytest -q
ruff check .
```

## License

MIT
