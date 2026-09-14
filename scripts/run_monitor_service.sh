#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${CTSTEG_OUTPUT_ROOT:-}" ]]; then
  echo "missing required environment variable: CTSTEG_OUTPUT_ROOT" >&2
  exit 64
fi

ctsteg_bin="${CTSTEG_BIN:-/opt/ctsteg/current/venv/bin/ctsteg}"
status_dir="${CTSTEG_MONITOR_DIR:-/srv/ctsteg/monitor}"
interval_seconds="${CTSTEG_MONITOR_INTERVAL_SECONDS:-5}"

if [[ ! -x "${ctsteg_bin}" ]]; then
  echo "ctsteg executable is not available: ${ctsteg_bin}" >&2
  exit 64
fi

export PYTHONUNBUFFERED=1
exec "${ctsteg_bin}" research-monitor \
  --output-root "${CTSTEG_OUTPUT_ROOT}" \
  --status-dir "${status_dir}" \
  --interval-seconds "${interval_seconds}"
