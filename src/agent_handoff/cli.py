from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .packer import pack_context, save_bundle
from .repo import find_repo_root
from .runtime import ask_bundle, resume_prompt
from .store import handoff_home
from .takeover import (
    create_takeover_session,
    load_takeover_session,
    run_takeover_turn,
    takeover_banner,
    takeover_repl,
)

BACKENDS = ["openai-compatible", "ollama", "command", "browser-bridge"]


def _add_backend_args(command: argparse.ArgumentParser, *, required: bool) -> None:
    command.add_argument(
        "--backend",
        required=required,
        default=None if required else "browser-bridge",
        choices=BACKENDS,
    )
    command.add_argument("--model")
    command.add_argument("--base-url")
    command.add_argument("--command")
    command.add_argument("--provider", default="chatgpt")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="handoff", description="Context handoff for coding agents")
    sub = p.add_subparsers(dest="cmd", required=True)

    pack = sub.add_parser("pack", help="package current repository context")
    pack.add_argument("--task", required=True)
    pack.add_argument("--file", action="append", default=[])
    pack.add_argument("--note", default="")
    pack.add_argument("--log")
    pack.add_argument("--repo", type=Path)

    ask = sub.add_parser("ask", help="send a bundle to another backend")
    _add_backend_args(ask, required=True)
    ask.add_argument("--bundle")
    ask.add_argument("--repo", type=Path)

    takeover = sub.add_parser(
        "takeover",
        help="explicitly switch to a fallback backend and keep discussing the same coding task",
    )
    _add_backend_args(takeover, required=False)
    takeover.add_argument(
        "--from-agent",
        default="codex",
        help="source agent shown in the handoff banner",
    )
    takeover.add_argument(
        "--task",
        default="Continue the current coding task from the repository and imported agent context.",
    )
    takeover.add_argument("--file", action="append", default=[])
    takeover.add_argument("--note", default="")
    takeover.add_argument("--log")
    takeover.add_argument("--repo", type=Path)
    takeover.add_argument(
        "--codex-session",
        type=Path,
        help="explicit Codex rollout JSONL to import",
    )
    takeover.add_argument(
        "--no-codex-history",
        action="store_true",
        help="do not import the newest local Codex session for this repository",
    )
    takeover.add_argument(
        "--resume",
        action="store_true",
        help="resume the latest saved takeover session",
    )
    takeover.add_argument("--session", help="resume a specific takeover session id")
    takeover.add_argument(
        "--message",
        help="send one takeover turn and exit instead of opening the REPL",
    )

    resume = sub.add_parser("resume", help="emit a continuation prompt")
    resume.add_argument("--bundle")
    resume.add_argument("--repo", type=Path)

    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.cmd == "pack":
            root = find_repo_root(args.repo)
            bundle = pack_context(
                args.task, root=root, files=args.file, note=args.note, log_path=args.log
            )
            target = save_bundle(bundle, handoff_home(root))
            print(bundle.id)
            print(target)
            return 0
        if args.cmd == "ask":
            path = ask_bundle(
                backend=args.backend,
                model=args.model,
                bundle_id=args.bundle,
                root=args.repo,
                base_url=args.base_url,
                command=args.command,
                provider=args.provider,
            )
            print(path)
            return 0
        if args.cmd == "takeover":
            root = find_repo_root(args.repo)
            home = handoff_home(root)
            if args.resume or args.session:
                session = load_takeover_session(home, args.session)
            else:
                session = create_takeover_session(
                    root=root,
                    task=args.task,
                    files=args.file,
                    note=args.note,
                    log_path=args.log,
                    source=args.from_agent,
                    backend=args.backend,
                    provider=args.provider,
                    model=args.model,
                    base_url=args.base_url,
                    import_codex_history=not args.no_codex_history,
                    codex_session=args.codex_session,
                )
            if args.message:
                print(takeover_banner(session), file=sys.stderr)
                response = run_takeover_turn(session, args.message, root=root, command=args.command)
                print(response.text)
                return 0
            if not sys.stdin.isatty():
                raise ValueError(
                    "interactive takeover needs a TTY; use --message for one-shot mode"
                )
            return takeover_repl(
                session,
                root=root,
                command=args.command,
                out=sys.stdout,
                err=sys.stderr,
            )
        if args.cmd == "resume":
            print(resume_prompt(bundle_id=args.bundle, root=args.repo))
            return 0
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"handoff: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
