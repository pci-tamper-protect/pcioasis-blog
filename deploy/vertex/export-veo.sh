#!/usr/bin/env bash
# Export Vertex Veo env vars for the video arena.
# Usage: eval "$(./deploy/vertex/export-veo.sh)"
#
# Status messages go to stderr; export statements go to stdout (for eval).
#
# Reads: VERTEX_CONFIG_FILE (default deploy/vertex/veo-config.json)
# Optional fetch: GCP secret vertex_veo_config (override with VERTEX_CONFIG_GCP_SECRET)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../scripts/export-common.sh
source "$SCRIPT_DIR/../scripts/export-common.sh"

CONFIG_FILE="${VERTEX_CONFIG_FILE:-$SCRIPT_DIR/veo-config.json}"
GCP_PROJECT="${GCP_PROJECT:-pcioasis-blog}"
GCP_SECRET="${VERTEX_CONFIG_GCP_SECRET:-vertex_veo_config}"
SOURCE="$CONFIG_FILE"

if [[ ! -f "$CONFIG_FILE" ]] && command -v gcloud >/dev/null 2>&1; then
  if gcloud secrets describe "$GCP_SECRET" --project="$GCP_PROJECT" >/dev/null 2>&1; then
    mkdir -p "$(dirname "$CONFIG_FILE")"
    gcloud secrets versions access latest \
      --secret="$GCP_SECRET" \
      --project="$GCP_PROJECT" >"$CONFIG_FILE"
    SOURCE="gcp secret $GCP_SECRET"
  fi
fi

if [[ ! -f "$CONFIG_FILE" ]] && [[ -f "$SCRIPT_DIR/veo-config.json" ]]; then
  CONFIG_FILE="$SCRIPT_DIR/veo-config.json"
  SOURCE="$CONFIG_FILE"
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  export_report_err "Vertex Veo: missing $CONFIG_FILE"
  echo "  cp deploy/vertex/veo-config.json $CONFIG_FILE" >&2
  echo "  ./deploy/vertex/bootstrap-gcp-veo-config.sh" >&2
  echo "  gcloud auth application-default login" >&2
  exit 1
fi

EXPORTS="$(python3 - "$CONFIG_FILE" <<'PY' || exit 1
import json, shlex, sys

path = sys.argv[1]
try:
    data = json.load(open(path))
except json.JSONDecodeError as exc:
    print(f"Vertex Veo: invalid JSON in {path}: {exc}", file=sys.stderr)
    sys.exit(1)

project = (data.get("project_id") or "").strip()
if not project or project in ("REPLACE_ME", "YOUR_PROJECT_ID"):
    print(f'Vertex Veo: set "project_id" in {path}', file=sys.stderr)
    sys.exit(1)

exports = {
    "GOOGLE_CLOUD_PROJECT": project,
    "GOOGLE_CLOUD_QUOTA_PROJECT": project,
    "GOOGLE_CLOUD_LOCATION": (data.get("location") or "us-central1").strip(),
    "VERTEX_VEO_MODEL": (data.get("model") or "veo-3.1-fast-generate-001").strip(),
}
if data.get("seconds"):
    exports["VERTEX_VEO_SECONDS"] = str(data["seconds"])

lines = [f"export {k}={shlex.quote(v)}" for k, v in exports.items() if v]
print("\n".join(lines))
PY
)"

export_emit_or_fail "Vertex Veo" "$SOURCE" "$EXPORTS" || exit 1

if command -v gcloud >/dev/null 2>&1; then
  if gcloud auth application-default print-access-token >/dev/null 2>&1; then
    export_report_ok "Vertex ADC credentials present (application-default login)"
    adc_quota="$(python3 - <<'PY' 2>/dev/null || true
import json
from pathlib import Path
p = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
if p.is_file():
    q = json.load(open(p)).get("quota_project_id", "")
    if q:
        print(q)
PY
)"
    cfg_project="$(python3 - "$CONFIG_FILE" <<'PY' 2>/dev/null || true
import json, sys
print(json.load(open(sys.argv[1])).get("project_id", "").strip())
PY
)"
    if [[ -n "$adc_quota" && -n "$cfg_project" && "$adc_quota" != "$cfg_project" ]]; then
      echo "warning: Vertex Veo: ADC quota project is $adc_quota but config project is $cfg_project; GOOGLE_CLOUD_QUOTA_PROJECT is set to $cfg_project" >&2
    fi
  else
    echo "warning: Vertex Veo: GOOGLE_CLOUD_PROJECT set but ADC not logged in — run: gcloud auth application-default login" >&2
  fi
else
  echo "warning: Vertex Veo: gcloud not installed — cannot verify ADC" >&2
fi
