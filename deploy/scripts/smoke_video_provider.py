#!/usr/bin/env python3
"""Minimal permission / generation smoke tests for video arena providers.

Usage (env must be loaded via deploy/*/export-*.sh first, or use --load):

  uv run --project agents/content-pipeline --extra video-arena \\
    python deploy/scripts/smoke_video_provider.py vertex_veo --check

  uv run --project agents/content-pipeline --extra video-arena \\
    python deploy/scripts/smoke_video_provider.py vertex_veo --generate

Providers: azure_sora, azure_sora_v1, vertex_veo, bedrock_luma, replicate_hailuo
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "agents" / "content-pipeline"))

MIN_PROMPT = (
    "Vertical 9:16 test clip, 4 seconds. Slow zoom on a padlock icon on a laptop screen. "
    "No text, no logos."
)


def _ok(msg: str) -> None:
    print(f"ok: {msg}")


def _fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _warn(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)


def smoke_azure_sora(*, generate: bool, v1: bool = False) -> None:
    from video_arena.providers.azure_sora import AzureSoraProvider
    from video_arena.providers.azure_sora_v1 import AzureSoraV1Provider

    if v1:
        provider = AzureSoraV1Provider()
        label = "Azure Sora v1"
    else:
        provider = AzureSoraProvider()
        label = "Azure Sora 2"

    if not provider.is_configured():
        _fail(f"{label}: not configured — eval \"$(./deploy/secrets/export-sora.sh)\"")

    endpoint = os.environ.get("AZURE_SORA_ENDPOINT") or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    deployment = os.environ.get("AZURE_SORA_DEPLOYMENT", "sora-2")
    _ok(f"{label}: endpoint set ({endpoint}), deployment={deployment}")

    if not generate:
        from video_arena.providers.azure_video_common import azure_video_client

        client = azure_video_client()
        # List deployments / verify auth — videos API has no list; retrieve bogus id → 401 vs 404
        try:
            client.videos.retrieve("video_smoke_test_nonexistent")
        except Exception as exc:  # noqa: BLE001
            name = type(exc).__name__
            if "Authentication" in name or "401" in str(exc):
                _fail(f"{label}: API key rejected ({exc})")
            _ok(f"{label}: API reachable (auth ok; {name} on probe as expected)")
        return

    out = Path("/tmp/smoke-azure-sora")
    os.environ.setdefault("AZURE_SORA_SECONDS", "4")
    result = provider.run(MIN_PROMPT, out)
    if result.status != "ok":
        _fail(f"{label}: generation failed — {result.message}")
    p = Path(result.video_path or "")
    _ok(f"{label}: generated {p} ({p.stat().st_size if p.is_file() else 0} bytes)")


def smoke_vertex_veo(*, generate: bool) -> None:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    model = os.environ.get("VERTEX_VEO_MODEL", "veo-3.1-fast-generate-001")

    if not project:
        _fail("Vertex Veo: GOOGLE_CLOUD_PROJECT unset — eval \"$(./deploy/vertex/export-veo.sh)\"")

    _ok(f"Vertex Veo: project={project} location={location} model={model}")

    try:
        from google import genai
    except ImportError:
        _fail("Vertex Veo: install google-genai — uv sync --extra video-arena")

    try:
        client = genai.Client(vertexai=True, project=project, location=location)
    except Exception as exc:  # noqa: BLE001
        _fail(f"Vertex Veo: client init failed — {exc}")

    _ok("Vertex Veo: genai client initialized (ADC accepted)")

    if not generate:
        # Lightweight: fetch model metadata (validates aiplatform permissions)
        try:
            client.models.get(model=model)
            _ok(f"Vertex Veo: models.get({model}) succeeded")
        except Exception as exc:  # noqa: BLE001
            _fail(f"Vertex Veo: models.get failed — {exc}")
        return

    from video_arena.providers.vertex_veo import VertexVeoProvider

    os.environ.setdefault("VERTEX_VEO_SECONDS", "4")
    out = Path("/tmp/smoke-vertex-veo")
    result = VertexVeoProvider().run(MIN_PROMPT, out)
    if result.status != "ok":
        _fail(f"Vertex Veo: generation failed — {result.message}")
    p = Path(result.video_path or "")
    _ok(f"Vertex Veo: generated {p} ({p.stat().st_size if p.is_file() else 0} bytes)")


def smoke_bedrock_luma(*, generate: bool) -> None:
    region = os.environ.get("AWS_REGION", "us-west-2")
    s3_uri = os.environ.get("VIDEO_ARENA_S3_OUTPUT_URI", "")

    if not s3_uri:
        _fail("Bedrock Luma: VIDEO_ARENA_S3_OUTPUT_URI unset — eval \"$(./deploy/aws/export-bedrock-luma.sh)\"")

    try:
        import boto3
    except ImportError:
        _fail("Bedrock Luma: install boto3 — uv sync --extra video-arena")

    sts = boto3.client("sts", region_name=region)
    try:
        ident = sts.get_caller_identity()
    except Exception as exc:  # noqa: BLE001
        _fail(f"Bedrock Luma: AWS credentials failed — {exc}")

    _ok(f"Bedrock Luma: AWS identity Account={ident.get('Account')} Arn={ident.get('Arn')}")

    bedrock = boto3.client("bedrock", region_name=region)
    model_id = "luma.ray-v2:0"
    try:
        bedrock.get_foundation_model(modelIdentifier=model_id)
        _ok(f"Bedrock Luma: get_foundation_model({model_id}) succeeded")
    except Exception as exc:  # noqa: BLE001
        _fail(f"Bedrock Luma: model access check failed — {exc}")

    bucket = s3_uri.replace("s3://", "").split("/")[0]
    s3 = boto3.client("s3", region_name=region)
    try:
        s3.head_bucket(Bucket=bucket)
        _ok(f"Bedrock Luma: S3 bucket reachable ({bucket})")
    except Exception as exc:  # noqa: BLE001
        _fail(f"Bedrock Luma: S3 head_bucket({bucket}) failed — {exc}")

    if not generate:
        return

    from video_arena.providers.bedrock_luma import BedrockLumaProvider

    out = Path("/tmp/smoke-bedrock-luma")
    result = BedrockLumaProvider().run(MIN_PROMPT, out)
    if result.status not in ("ok", "failed"):
        _fail(f"Bedrock Luma: unexpected status {result.status}")
    if result.status == "failed":
        _fail(f"Bedrock Luma: async invoke failed — {result.message}")
    _ok(f"Bedrock Luma: async job completed — {result.message}")


def smoke_replicate(*, generate: bool) -> None:
    token = os.environ.get("REPLICATE_API_TOKEN", "")
    if not token:
        _fail("Replicate: REPLICATE_API_TOKEN unset — eval \"$(./deploy/replicate/export-replicate.sh)\"")

    req = urllib.request.Request(
        "https://api.replicate.com/v1/account",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        _fail(f"Replicate: account API HTTP {exc.code} — token rejected?")
    except Exception as exc:  # noqa: BLE001
        _fail(f"Replicate: account API failed — {exc}")

    username = body.get("username") or body.get("name") or "unknown"
    _ok(f"Replicate: account API ok (user={username})")

    if not generate:
        return

    from video_arena.providers.replicate_hailuo import ReplicateHailuoProvider

    out = Path("/tmp/smoke-replicate-hailuo")
    result = ReplicateHailuoProvider().run(MIN_PROMPT, out)
    if result.status != "ok":
        _fail(f"Replicate Hailuo: generation failed — {result.message}")
    p = Path(result.video_path or "")
    _ok(f"Replicate Hailuo: generated {p} ({p.stat().st_size if p.is_file() else 0} bytes)")


PROVIDERS = {
    "azure_sora": lambda **kw: smoke_azure_sora(v1=False, **kw),
    "azure_sora_v1": lambda **kw: smoke_azure_sora(v1=True, **kw),
    "vertex_veo": smoke_vertex_veo,
    "bedrock_luma": smoke_bedrock_luma,
    "replicate_hailuo": smoke_replicate,
}

LOAD_EXPORT = {
    "azure_sora": "deploy/secrets/export-sora.sh",
    "azure_sora_v1": "deploy/secrets/export-sora.sh",
    "vertex_veo": "deploy/vertex/export-veo.sh",
    "bedrock_luma": "deploy/aws/export-bedrock-luma.sh",
    "replicate_hailuo": "deploy/replicate/export-replicate.sh",
}


def _load_export(provider: str) -> None:
    script = REPO_ROOT / LOAD_EXPORT[provider]
    if not script.is_file():
        _fail(f"missing export script {script}")
    proc = subprocess.run(
        [str(script)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    print(proc.stderr, file=sys.stderr, end="")
    if proc.returncode != 0:
        _fail(f"export script failed ({script})")
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("export "):
            continue
        assign = line[len("export ") :]
        key, _, raw = assign.partition("=")
        val = raw.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        os.environ[key] = val


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test video arena provider credentials")
    parser.add_argument(
        "provider",
        choices=[*PROVIDERS.keys(), "all"],
        help="Provider id or 'all' for permission checks",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--generate",
        action="store_true",
        help="Run minimal video generation (slow, billed). Default is permission check only.",
    )
    parser.add_argument(
        "--load",
        action="store_true",
        help="Run deploy export script before test",
    )
    args = parser.parse_args()

    generate = args.generate
    targets = list(PROVIDERS.keys()) if args.provider == "all" else [args.provider]

    failed = 0
    for pid in targets:
        print(f"--- {pid} ---")
        if args.load:
            _load_export(pid)
        try:
            PROVIDERS[pid](generate=generate)
        except SystemExit as exc:
            if exc.code:
                failed += 1
                if len(targets) == 1:
                    raise
        print()

    if failed:
        _fail(f"{failed} provider(s) failed smoke test")
    _ok("all smoke tests passed")


if __name__ == "__main__":
    main()
