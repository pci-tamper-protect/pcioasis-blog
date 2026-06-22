"""Load video provider credentials into os.environ before arena runs."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def find_repo_root(start: Path) -> Path | None:
    cur = start.resolve()
    for _ in range(8):
        if (cur / "deploy" / "secrets" / "load_ai_config.py").is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _sora_env_ready() -> bool:
    return bool(
        os.environ.get("AZURE_SORA_ENDPOINT")
        and (
            os.environ.get("AZURE_SORA_API_KEY")
            or os.environ.get("AZURE_OPENAI_API_KEY")
        )
    )


def ensure_sora_env(*, repo_root: Path | None = None, post_dir: Path | None = None) -> bool:
    """Populate AZURE_SORA_* from /tmp/sora.json (or keychain) when available.

    Always prefers the canonical Sora secret over stale AZURE_SORA_* already in the
    process environment (e.g. chat Foundry endpoint copied into AZURE_SORA_ENDPOINT).
    """
    root = repo_root
    if root is None and post_dir is not None:
        root = find_repo_root(post_dir)
    if root is None:
        root = find_repo_root(Path.cwd())

    if root is not None:
        secrets_dir = root / "deploy" / "secrets"
        if str(secrets_dir) not in sys.path:
            sys.path.insert(0, str(secrets_dir))

        try:
            from load_ai_config import apply_sora_to_environ, load_sora_config

            try:
                cfg, raw = load_sora_config()
            except FileNotFoundError:
                cfg, raw = load_sora_config(prefer_keychain=True)
            apply_sora_to_environ(cfg, raw)
            return bool(os.environ.get("AZURE_SORA_ENDPOINT"))
        except (FileNotFoundError, ImportError, ValueError):
            pass

    return _sora_env_ready()
