from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .packer import pack_context, save_bundle
from .repo import find_repo_root
from .runtime import ask_bundle, resume_prompt
from .store import handoff_home


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
    ask.add_argument(
        "--backend",
        required=True,
        choices=["openai-compatible", "ollama", "command", "browser-bridge"],
    )
    ask.add_argument("--model")
    ask.add_argument("--bundle")
    ask.add_argument("--base-url")
    ask.add_argument("--command")
    ask.add_argument("--provider", default="chatgpt")
    ask.add_argument("--repo", type=Path)

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
        if args.cmd == "resume":
            print(resume_prompt(bundle_id=args.bundle, root=args.repo))
            return 0
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"handoff: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
