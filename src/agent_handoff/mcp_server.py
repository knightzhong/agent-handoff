from __future__ import annotations

from pathlib import Path

from .packer import pack_context, save_bundle
from .repo import find_repo_root
from .runtime import ask_bundle, resume_prompt
from .store import handoff_home


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit("Install MCP support with: pip install 'agent-handoff[mcp]'") from exc

    mcp = FastMCP("agent-handoff")

    @mcp.tool()
    def pack_context_tool(task: str, files: list[str] | None = None, note: str = "") -> str:
        """Package the current repository state into a handoff bundle."""
        root = find_repo_root(Path.cwd())
        bundle = pack_context(task, root=root, files=files or [], note=note)
        save_bundle(bundle, handoff_home(root))
        return bundle.id

    @mcp.tool()
    def ask_handoff(
        backend: str,
        model: str | None = None,
        bundle_id: str | None = None,
        base_url: str | None = None,
        provider: str = "chatgpt",
    ) -> str:
        """Send a handoff bundle to a configured backend and save its response."""
        return str(
            ask_bundle(
                backend=backend,
                model=model,
                bundle_id=bundle_id,
                root=Path.cwd(),
                base_url=base_url,
                provider=provider,
            )
        )

    @mcp.tool()
    def resume_handoff(bundle_id: str | None = None) -> str:
        """Return a prompt for resuming the task in the current coding agent."""
        return resume_prompt(bundle_id=bundle_id, root=Path.cwd())

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
