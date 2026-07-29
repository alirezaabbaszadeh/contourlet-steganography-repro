#!/usr/bin/env bash
set -euo pipefail

required_variables=(
  CTSTEG_MANIFEST
  CTSTEG_CONFIG
  CTSTEG_STABILITY_PROFILE
  CTSTEG_OUTPUT_ROOT
  CTSTEG_RUNTIME_GATE_REPORT
)

for variable_name in "${required_variables[@]}"; do
  if [[ -z "${!variable_name:-}" ]]; then
    echo "missing required environment variable: ${variable_name}" >&2
    exit 64
  fi
done

required_files=(
  "${CTSTEG_MANIFEST}"
  "${CTSTEG_CONFIG}"
  "${CTSTEG_STABILITY_PROFILE}"
  "${CTSTEG_RUNTIME_GATE_REPORT}"
)

for required_file in "${required_files[@]}"; do
  if [[ ! -r "${required_file}" ]]; then
    echo "required research input is not readable: ${required_file}" >&2
    exit 64
  fi
done

ctsteg_bin="${CTSTEG_BIN:-/opt/ctsteg/current/venv/bin/ctsteg}"
if [[ ! -x "${ctsteg_bin}" ]]; then
  echo "ctsteg executable is not available: ${ctsteg_bin}" >&2
  exit 64
fi
workers="${CTSTEG_WORKERS:-0}"
reserve_cpus="${CTSTEG_RESERVE_CPUS:-4}"
reserve_memory_gib="${CTSTEG_RESERVE_MEMORY_GIB:-12}"
worker_memory_gib="${CTSTEG_WORKER_MEMORY_GIB:-3}"
max_workers="${CTSTEG_MAX_WORKERS:-16}"
minimum_free_disk_gib="${CTSTEG_MIN_FREE_DISK_GIB:-100}"

arguments=(
  digital-research-run
  --manifest "${CTSTEG_MANIFEST}"
  --config "${CTSTEG_CONFIG}"
  --stability-profile "${CTSTEG_STABILITY_PROFILE}"
  --output-root "${CTSTEG_OUTPUT_ROOT}"
  --runtime-gate-report "${CTSTEG_RUNTIME_GATE_REPORT}"
  --workers "${workers}"
  --reserve-cpus "${reserve_cpus}"
  --reserve-memory-gib "${reserve_memory_gib}"
  --worker-memory-gib "${worker_memory_gib}"
  --max-workers "${max_workers}"
  --minimum-free-disk-gib "${minimum_free_disk_gib}"
)

if [[ -n "${CTSTEG_CACHE_DIR:-}" ]]; then
  arguments+=(--cache-dir "${CTSTEG_CACHE_DIR}")
fi
if [[ "${CTSTEG_REQUIRE_PARQUET:-1}" == "1" ]]; then
  arguments+=(--require-parquet)
fi
if [[ "${CTSTEG_PACKAGE_RESULTS:-1}" != "1" ]]; then
  arguments+=(--no-package)
fi
if [[ "${CTSTEG_ENGINEERING_CONTROL:-0}" == "1" ]]; then
  arguments+=(--engineering-control)
fi

export PYTHONUNBUFFERED=1
export MPLCONFIGDIR="${MPLCONFIGDIR:-${CTSTEG_OUTPUT_ROOT}/matplotlib-cache}"
exec "${ctsteg_bin}" "${arguments[@]}"
