#!/usr/bin/env bash

# Shared bounded-retry helpers for the Ubuntu bootstrap.  This file deliberately
# does not enable shell options because it is sourced by both the installer and
# isolated fault-injection tests.

ctsteg_validate_retry_settings() {
  local attempts="${CTSTEG_RETRY_ATTEMPTS:-8}"
  local initial_seconds="${CTSTEG_RETRY_INITIAL_SECONDS:-5}"
  local maximum_seconds="${CTSTEG_RETRY_MAX_SECONDS:-120}"

  [[ "${attempts}" =~ ^[0-9]+$ ]] \
    && ((attempts >= 1 && attempts <= 20)) || {
      echo "CTSTEG_RETRY_ATTEMPTS must be an integer from 1 through 20" >&2
      return 64
    }
  [[ "${initial_seconds}" =~ ^[0-9]+$ ]] \
    && ((initial_seconds <= 900)) || {
      echo "CTSTEG_RETRY_INITIAL_SECONDS must be an integer from 0 through 900" >&2
      return 64
    }
  [[ "${maximum_seconds}" =~ ^[0-9]+$ ]] \
    && ((maximum_seconds >= initial_seconds && maximum_seconds <= 3600)) || {
      echo "CTSTEG_RETRY_MAX_SECONDS must be an integer from the initial delay through 3600" >&2
      return 64
    }
}

ctsteg_retry_command_n() {
  (($# >= 3)) || {
    echo "ctsteg_retry_command_n requires attempts, label, and command" >&2
    return 64
  }
  local maximum_attempts="$1"
  local label="$2"
  shift 2
  [[ "${maximum_attempts}" =~ ^[0-9]+$ ]] \
    && ((maximum_attempts >= 1 && maximum_attempts <= 20)) || {
      echo "retry count for ${label} must be an integer from 1 through 20" >&2
      return 64
    }
  ctsteg_validate_retry_settings || return $?

  local attempt=1
  local delay="${CTSTEG_RETRY_INITIAL_SECONDS:-5}"
  local maximum_delay="${CTSTEG_RETRY_MAX_SECONDS:-120}"
  local status=0
  while true; do
    printf '[ctsteg-retry] %s: attempt %d/%d\n' \
      "${label}" \
      "${attempt}" \
      "${maximum_attempts}"
    if "$@"; then
      if ((attempt > 1)); then
        printf '[ctsteg-retry] %s: recovered on attempt %d/%d\n' \
          "${label}" \
          "${attempt}" \
          "${maximum_attempts}"
      fi
      return 0
    else
      status=$?
    fi
    if ((attempt >= maximum_attempts)); then
      printf '[ctsteg-retry] %s: exhausted after %d attempts (exit %d)\n' \
        "${label}" \
        "${attempt}" \
        "${status}" \
        >&2
      return "${status}"
    fi
    printf '[ctsteg-retry] %s: exit %d; retrying in %ds\n' \
      "${label}" \
      "${status}" \
      "${delay}" \
      >&2
    sleep "${delay}"
    attempt=$((attempt + 1))
    if ((delay < maximum_delay)); then
      delay=$((delay * 2))
      if ((delay > maximum_delay)); then
        delay="${maximum_delay}"
      fi
    fi
  done
}

ctsteg_retry_command() {
  (($# >= 2)) || {
    echo "ctsteg_retry_command requires a label and command" >&2
    return 64
  }
  local label="$1"
  shift
  ctsteg_retry_command_n \
    "${CTSTEG_RETRY_ATTEMPTS:-8}" \
    "${label}" \
    "$@"
}
