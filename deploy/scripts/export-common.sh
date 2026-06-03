# shellcheck shell=bash
# Helpers for deploy/*/export-*.sh — status on stderr, exports on stdout.

export_report_ok() {
  echo "ok: $*" >&2
}

export_report_err() {
  echo "error: $*" >&2
}

export_emit_or_fail() {
  local label="$1"
  local source="$2"
  local exports="$3"
  if [[ -z "$exports" ]]; then
    export_report_err "$label: no environment variables exported (check config fields)"
    return 1
  fi
  printf '%s\n' "$exports"
  export_report_ok "$label loaded from $source"
}
