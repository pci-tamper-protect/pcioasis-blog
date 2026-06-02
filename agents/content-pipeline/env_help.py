"""Print copy-paste shell commands when required env vars or tools are missing."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from cwd or this file to the pcioasis-blog root."""
    candidates = [start or Path.cwd(), Path(__file__).resolve().parent]
    for base in candidates:
        path = base.resolve()
        for _ in range(8):
            if (path / "deploy" / "secrets" / "export-macos-keychain.sh").is_file():
                return path
            if path.parent == path:
                break
            path = path.parent
    return Path.cwd().resolve()


def _is_anthropic_key(key: str) -> bool:
    return key.startswith("sk-ant-")


def credential_snapshot() -> dict[str, bool | str]:
    anthropic = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    azure_ep = (
        os.environ.get("AZURE_OPENAI_ENDPOINT")
        or os.environ.get("AI_AZURE_OPENAI_ENDPOINT")
        or ""
    ).strip()
    api_key = (
        os.environ.get("AZURE_OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("AI_API_KEY")
        or ""
    ).strip()
    secret = Path(os.environ.get("AI_SECRET_FILE", "/tmp/ai"))
    return {
        "anthropic_valid": bool(anthropic) and _is_anthropic_key(anthropic),
        "anthropic_invalid_alias": bool(anthropic) and not _is_anthropic_key(anthropic),
        "azure_ready": bool(azure_ep and api_key),
        "azure_missing_endpoint": bool(api_key) and not azure_ep,
        "azure_missing_key": bool(azure_ep) and not api_key,
        "azure_missing_deployment": bool(azure_ep and api_key)
        and not (
            os.environ.get("AZURE_OPENAI_DEPLOYMENT")
            or os.environ.get("OPENAI_MODEL")
        ),
        "openai_ready": bool(api_key) and not azure_ep,
        "secret_file_path": str(secret),
        "secret_file_exists": secret.is_file(),
    }


def llm_setup_commands(repo_root: Path | None = None) -> list[str]:
    root = repo_root or find_repo_root()
    snap = credential_snapshot()
    lines = [
        "Commands to set credentials (run from repo root):",
        f"  cd {root}",
        "",
    ]

    if snap["anthropic_invalid_alias"]:
        lines.extend(
            [
                "# Wrong: ANTHROPIC_API_KEY is set but is not an Anthropic key (often an Azure key):",
                "unset ANTHROPIC_API_KEY",
                "",
            ]
        )

    if not snap["secret_file_exists"]:
        lines.extend(
            [
                "# Bootstrap secrets into Keychain (once), then export:",
                f"  # Place JSON at {snap['secret_file_path']} or set AI_SECRET_FILE",
                "./deploy/secrets/bootstrap-macos-keychain.sh",
                "",
            ]
        )

    lines.extend(
        [
            "# Azure AI Foundry (recommended after Keychain bootstrap):",
            'eval "$(./deploy/secrets/export-macos-keychain.sh)"',
            'export AZURE_OPENAI_DEPLOYMENT="${AZURE_OPENAI_DEPLOYMENT:-YOUR_DEPLOYMENT_NAME}"',
            'export CONTENT_PIPELINE_LLM_BACKEND="${CONTENT_PIPELINE_LLM_BACKEND:-azure_openai}"',
            "",
            "# Or export /tmp/ai fields manually:",
            'export AZURE_OPENAI_ENDPOINT="https://YOUR_RESOURCE.openai.azure.com/openai/v1"',
            'export AZURE_OPENAI_API_KEY="..."   # or: eval "$(./deploy/secrets/export-macos-keychain.sh)"',
            "export AZURE_OPENAI_DEPLOYMENT=YOUR_DEPLOYMENT_NAME",
            "",
            "# Anthropic (real key only — must start with sk-ant-):",
            'export ANTHROPIC_API_KEY="sk-ant-..."',
            "",
            "# Optional overrides:",
            "export CONTENT_PIPELINE_LLM_BACKEND=anthropic  # or azure_openai | openai",
            "export ANTHROPIC_MODEL=claude-opus-4-7",
            "export AZURE_OPENAI_API_VERSION=2024-10-21",
        ]
    )

    if snap["azure_missing_deployment"]:
        lines.insert(
            -4,
            "# Still required for Azure: deployment name (model deployment id in Foundry)",
        )

    return lines


def print_llm_setup_commands(
    *,
    reason: str = "",
    secret_path: str | None = None,
    file: object | None = None,
) -> None:
    out = file if file is not None else sys.stderr
    if reason:
        print(f"error: {reason}", file=out)
        print(file=out)
    if secret_path:
        print(f"  (checked secret file: {secret_path})", file=out)
        print(file=out)
    for line in llm_setup_commands():
        print(line, file=out)


def exit_missing_llm_credentials(
    secret_path: str | None = None,
    *,
    reason: str = "No LLM credentials found.",
) -> None:
    print_llm_setup_commands(reason=reason, secret_path=secret_path)
    sys.exit(1)


def print_azure_not_found_help(cfg: Any, *, file: object | None = None) -> None:
    """cfg: ai_backend.BackendConfig (Any to avoid circular import)."""
    out = file if file is not None else sys.stderr
    print("error: Azure returned 404 Resource not found.", file=out)
    print(file=out)
    print("Usually one of:", file=out)
    print(
        f"  • Wrong deployment name (current AZURE_OPENAI_DEPLOYMENT / model={cfg.model!r})",
        file=out,
    )
    print(
        f"  • Wrong endpoint shape (current endpoint={cfg.azure_endpoint!r})",
        file=out,
    )
    if getattr(cfg, "azure_use_v1_base_url", False):
        print(
            "  • Foundry /openai/v1 endpoints must use base_url mode (auto-enabled).",
            file=out,
        )
    else:
        print(
            "  • If your portal shows …/openai/v1, re-export secrets or set AZURE_OPENAI_ENDPOINT to that URL.",
            file=out,
        )
    print(file=out)
    print("Commands to fix (copy deployment name from Azure AI Foundry → Deployments):", file=out)
    print('  export AZURE_OPENAI_DEPLOYMENT="YOUR_EXACT_DEPLOYMENT_NAME"', file=out)
    if not getattr(cfg, "azure_use_v1_base_url", False):
        print(
            '  export AZURE_OPENAI_ENDPOINT="https://YOUR_RESOURCE.openai.azure.com/"',
            file=out,
        )
        print("  # Remove /openai/v1 from AZURE_OPENAI_ENDPOINT when using the AzureOpenAI SDK path.", file=out)
    print('  export AZURE_OPENAI_API_VERSION="2024-10-21"', file=out)
    print("  # Re-run generate_variants.py", file=out)


def print_auth_failure_help(backend: str, *, file: object | None = None) -> None:
    out = file if file is not None else sys.stderr
    print(f"error: authentication failed for backend={backend}", file=out)
    print(file=out)
    snap = credential_snapshot()
    if backend == "anthropic" and snap["anthropic_invalid_alias"]:
        print(
            "  ANTHROPIC_API_KEY is set but does not look like an Anthropic key.",
            file=out,
        )
        print("  unset ANTHROPIC_API_KEY", file=out)
        print(file=out)
    print_llm_setup_commands(file=out)


def generate_variants_command(post_dir: Path, repo_root: Path | None = None) -> str:
    root = repo_root or find_repo_root()
    try:
        rel_post = post_dir.resolve().relative_to(root)
    except ValueError:
        rel_post = post_dir.resolve()
    return (
        f"uv run --project agents/content-pipeline "
        f"python agents/content-pipeline/generate_variants.py {rel_post}"
    )


def print_missing_variants_help(variants_dir: Path, post_dir: Path) -> None:
    root = find_repo_root()
    print(f"error: no _variants/ at {variants_dir}", file=sys.stderr)
    print(file=sys.stderr)
    print("Run variant generation first:", file=sys.stderr)
    print(f"  cd {root}", file=sys.stderr)
    print("  eval \"$(./deploy/secrets/export-macos-keychain.sh)\"", file=sys.stderr)
    print(
        '  export AZURE_OPENAI_DEPLOYMENT="${AZURE_OPENAI_DEPLOYMENT:-YOUR_DEPLOYMENT_NAME}"',
        file=sys.stderr,
    )
    print(f"  {generate_variants_command(post_dir, root)}", file=sys.stderr)
    sys.exit(1)


def gh_setup_commands() -> list[str]:
    return [
        "Commands for GitHub CLI (assemble_pr.py):",
        "  gh auth login",
        '  export GH_TOKEN="ghp_..."   # or use GITHUB_TOKEN — repo + pull_requests scope',
        "  gh auth status",
    ]


def print_gh_setup_commands(*, reason: str = "", file: object | None = None) -> None:
    out = file if file is not None else sys.stderr
    if reason:
        print(f"error: {reason}", file=out)
        print(file=out)
    for line in gh_setup_commands():
        print(line, file=out)


def check_gh_available() -> None:
    import shutil

    if shutil.which("gh"):
        return
    print_gh_setup_commands(reason="gh CLI not found.")
    sys.exit(1)
