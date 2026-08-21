from __future__ import annotations

import json
from pathlib import Path

from .models import ContextBundle


def handoff_home(repo_root: Path) -> Path:
    from os import environ

    configured = environ.get("HANDOFF_HOME")
    return Path(configured).expanduser().resolve() if configured else repo_root / ".handoff"


def resolve_bundle_id(home: Path, bundle_id: str | None) -> str:
    if bundle_id:
        return bundle_id
    latest = home / "latest"
    if not latest.exists():
        raise FileNotFoundError("no handoff bundle found; run `handoff pack` first")
    return latest.read_text(encoding="utf-8").strip()


def load_bundle(home: Path, bundle_id: str | None = None) -> ContextBundle:
    bundle_id = resolve_bundle_id(home, bundle_id)
    path = home / "bundles" / bundle_id / "bundle.json"
    return ContextBundle.from_dict(json.loads(path.read_text(encoding="utf-8")))


def bundle_dir(home: Path, bundle_id: str | None = None) -> Path:
    return home / "bundles" / resolve_bundle_id(home, bundle_id)
