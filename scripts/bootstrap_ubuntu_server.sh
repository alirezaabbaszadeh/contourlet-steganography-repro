#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
bootstrap_libexec="${CTSTEG_BOOTSTRAP_LIBEXEC_DIR:-/usr/local/libexec/ctsteg}"
retry_library=""
for retry_candidate in \
  "${script_dir}/bootstrap_retry.sh" \
  "${bootstrap_libexec}/bootstrap_retry.sh"
do
  if [[ -r "${retry_candidate}" ]]; then
    retry_library="${retry_candidate}"
    break
  fi
done
[[ -n "${retry_library}" ]] || {
  echo "bootstrap retry library is missing" >&2
  exit 64
}
# shellcheck disable=SC1090
source "${retry_library}"

usage() {
  cat <<'EOF'
Usage:
  bootstrap_ubuntu_server.sh --check  --config /path/server.env
  bootstrap_ubuntu_server.sh --apply  --config /path/server.env
  bootstrap_ubuntu_server.sh --ensure --config /path/server.env
  bootstrap_ubuntu_server.sh --verify --config /path/server.env

--check is read-only. --apply is idempotent and requires root or passwordless
sudo. --ensure verifies first and applies only when repair is needed.
--verify performs no package, repository, or service mutations.
EOF
}

mode=""
config_file=""
while (($#)); do
  case "$1" in
    --check|--apply|--ensure|--verify)
      [[ -z "${mode}" ]] || {
        echo "choose exactly one operating mode" >&2
        exit 64
      }
      mode="${1#--}"
      shift
      ;;
    --config)
      (($# >= 2)) || {
        echo "--config requires a path" >&2
        exit 64
      }
      config_file="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 64
      ;;
  esac
done

[[ -n "${mode}" && -n "${config_file}" ]] || {
  usage >&2
  exit 64
}
[[ -r "${config_file}" ]] || {
  echo "configuration is not readable: ${config_file}" >&2
  exit 64
}

# The configuration is an administrator-controlled shell environment file and
# must not contain credentials. MATLAB/GitHub credentials live elsewhere.
set -a
# shellcheck disable=SC1090
source "${config_file}"
set +a

CTSTEG_REPOSITORY_URL="${CTSTEG_REPOSITORY_URL:-https://github.com/alirezaabbaszadeh/contourlet-steganography-repro.git}"
CTSTEG_GIT_REF="${CTSTEG_GIT_REF:-}"
CTSTEG_ALLOW_FLOATING_GIT_REF="${CTSTEG_ALLOW_FLOATING_GIT_REF:-0}"
CTSTEG_SERVICE_INSTANCE="${CTSTEG_SERVICE_INSTANCE:-final}"
CTSTEG_INSTALL_ROOT="${CTSTEG_INSTALL_ROOT:-/opt/ctsteg}"
CTSTEG_DATA_ROOT="${CTSTEG_DATA_ROOT:-/srv/ctsteg}"
CTSTEG_SERVICE_USER="${CTSTEG_SERVICE_USER:-ctsteg}"
CTSTEG_PYTHON_VERSION="${CTSTEG_PYTHON_VERSION:-3.12}"
CTSTEG_UV_VERSION="${CTSTEG_UV_VERSION:-0.8.22}"
CTSTEG_RUN_TESTS="${CTSTEG_RUN_TESTS:-1}"
CTSTEG_RUN_RUNTIME_GATE="${CTSTEG_RUN_RUNTIME_GATE:-1}"
CTSTEG_INSTALL_MATLAB="${CTSTEG_INSTALL_MATLAB:-1}"
CTSTEG_MATLAB_RELEASE="${CTSTEG_MATLAB_RELEASE:-R2026a}"
CTSTEG_MATLAB_PRODUCTS="${CTSTEG_MATLAB_PRODUCTS:-MATLAB Image_Processing_Toolbox}"
CTSTEG_MATLAB_ROOT="${CTSTEG_MATLAB_ROOT:-/opt/matlab/${CTSTEG_MATLAB_RELEASE}}"
CTSTEG_MATLAB_NO_GPU="${CTSTEG_MATLAB_NO_GPU:-1}"
CTSTEG_INSTALL_CONTOURLET="${CTSTEG_INSTALL_CONTOURLET:-1}"
CTSTEG_CONTOURLET_ARCHIVE="${CTSTEG_CONTOURLET_ARCHIVE:-}"
CTSTEG_CONTOURLET_ARCHIVE_SHA256="${CTSTEG_CONTOURLET_ARCHIVE_SHA256:-}"
CTSTEG_PREFETCH_USC_SIPI="${CTSTEG_PREFETCH_USC_SIPI:-1}"
CTSTEG_ENABLE_MONITOR_SERVICE="${CTSTEG_ENABLE_MONITOR_SERVICE:-1}"
CTSTEG_ENABLE_RESEARCH_SERVICE="${CTSTEG_ENABLE_RESEARCH_SERVICE:-0}"
CTSTEG_MIN_CPUS="${CTSTEG_MIN_CPUS:-16}"
CTSTEG_MIN_MEMORY_GIB="${CTSTEG_MIN_MEMORY_GIB:-32}"
CTSTEG_MIN_DISK_GIB="${CTSTEG_MIN_DISK_GIB:-250}"
CTSTEG_RECOMMENDED_CPUS="${CTSTEG_RECOMMENDED_CPUS:-32}"
CTSTEG_RECOMMENDED_MEMORY_GIB="${CTSTEG_RECOMMENDED_MEMORY_GIB:-64}"
CTSTEG_RECOMMENDED_DISK_GIB="${CTSTEG_RECOMMENDED_DISK_GIB:-500}"
CTSTEG_RETRY_ATTEMPTS="${CTSTEG_RETRY_ATTEMPTS:-8}"
CTSTEG_RETRY_INITIAL_SECONDS="${CTSTEG_RETRY_INITIAL_SECONDS:-5}"
CTSTEG_RETRY_MAX_SECONDS="${CTSTEG_RETRY_MAX_SECONDS:-120}"
CTSTEG_NETWORK_CHECK_ATTEMPTS="${CTSTEG_NETWORK_CHECK_ATTEMPTS:-4}"
CTSTEG_NETWORK_CHECK_BACKOFF_SECONDS="${CTSTEG_NETWORK_CHECK_BACKOFF_SECONDS:-2}"
CTSTEG_RUNTIME_GATE_ATTEMPTS="${CTSTEG_RUNTIME_GATE_ATTEMPTS:-3}"

log() {
  printf '[ctsteg-bootstrap] %s\n' "$*"
}

fail() {
  printf '[ctsteg-bootstrap] ERROR: %s\n' "$*" >&2
  exit 64
}

require_boolean() {
  local name="$1"
  local value="${!name}"
  [[ "${value}" == "0" || "${value}" == "1" ]] || {
    fail "${name} must be 0 or 1"
  }
}

for boolean_name in \
  CTSTEG_ALLOW_FLOATING_GIT_REF \
  CTSTEG_RUN_TESTS \
  CTSTEG_RUN_RUNTIME_GATE \
  CTSTEG_INSTALL_MATLAB \
  CTSTEG_MATLAB_NO_GPU \
  CTSTEG_INSTALL_CONTOURLET \
  CTSTEG_PREFETCH_USC_SIPI \
  CTSTEG_ENABLE_MONITOR_SERVICE \
  CTSTEG_ENABLE_RESEARCH_SERVICE
do
  require_boolean "${boolean_name}"
done

[[ "${CTSTEG_INSTALL_ROOT}" == "/opt/ctsteg" ]] || {
  fail "systemd units currently require CTSTEG_INSTALL_ROOT=/opt/ctsteg"
}
[[ "${CTSTEG_DATA_ROOT}" == "/srv/ctsteg" ]] || {
  fail "systemd units currently require CTSTEG_DATA_ROOT=/srv/ctsteg"
}
[[ "${CTSTEG_SERVICE_USER}" == "ctsteg" ]] || {
  fail "systemd units currently require CTSTEG_SERVICE_USER=ctsteg"
}
[[ "${CTSTEG_SERVICE_INSTANCE}" =~ ^[A-Za-z0-9_.-]+$ ]] || {
  fail "CTSTEG_SERVICE_INSTANCE contains unsafe characters"
}
[[ "${CTSTEG_MATLAB_RELEASE}" =~ ^R20[0-9]{2}[ab](U[0-9]+)?$ ]] || {
  fail "CTSTEG_MATLAB_RELEASE is invalid"
}
[[ "${CTSTEG_PYTHON_VERSION}" =~ ^3\.(11|12|13)$ ]] || {
  fail "CTSTEG_PYTHON_VERSION must be 3.11, 3.12, or 3.13"
}
ctsteg_validate_retry_settings || exit $?
[[ "${CTSTEG_NETWORK_CHECK_ATTEMPTS}" =~ ^[0-9]+$ ]] \
  && ((CTSTEG_NETWORK_CHECK_ATTEMPTS >= 1 \
    && CTSTEG_NETWORK_CHECK_ATTEMPTS <= 20)) || {
  fail "CTSTEG_NETWORK_CHECK_ATTEMPTS must be an integer from 1 through 20"
}
[[ "${CTSTEG_NETWORK_CHECK_BACKOFF_SECONDS}" =~ ^[0-9]+$ ]] \
  && ((CTSTEG_NETWORK_CHECK_BACKOFF_SECONDS <= 900)) || {
  fail "CTSTEG_NETWORK_CHECK_BACKOFF_SECONDS must be an integer from 0 through 900"
}
[[ "${CTSTEG_RUNTIME_GATE_ATTEMPTS}" =~ ^[0-9]+$ ]] \
  && ((CTSTEG_RUNTIME_GATE_ATTEMPTS >= 1 \
    && CTSTEG_RUNTIME_GATE_ATTEMPTS <= 5)) || {
  fail "CTSTEG_RUNTIME_GATE_ATTEMPTS must be an integer from 1 through 5"
}

preflight_script=""
for preflight_candidate in \
  "${script_dir}/server_preflight.py" \
  "${bootstrap_libexec}/server_preflight.py"
do
  if [[ -r "${preflight_candidate}" ]]; then
    preflight_script="${preflight_candidate}"
    break
  fi
done
[[ -n "${preflight_script}" ]] || {
  fail "server_preflight.py is missing beside the bootstrap script"
}

storage_probe="${CTSTEG_DATA_ROOT}"
while [[ ! -e "${storage_probe}" && "${storage_probe}" != "/" ]]; do
  storage_probe="$(dirname -- "${storage_probe}")"
done
preflight_args=(
  --storage-path "${storage_probe}"
  --minimum-cpus "${CTSTEG_MIN_CPUS}"
  --minimum-memory-gib "${CTSTEG_MIN_MEMORY_GIB}"
  --minimum-disk-gib "${CTSTEG_MIN_DISK_GIB}"
  --recommended-cpus "${CTSTEG_RECOMMENDED_CPUS}"
  --recommended-memory-gib "${CTSTEG_RECOMMENDED_MEMORY_GIB}"
  --recommended-disk-gib "${CTSTEG_RECOMMENDED_DISK_GIB}"
  --network-attempts "${CTSTEG_NETWORK_CHECK_ATTEMPTS}"
  --network-backoff-seconds "${CTSTEG_NETWORK_CHECK_BACKOFF_SECONDS}"
)

if [[ "${mode}" == "check" ]]; then
  exec python3 "${preflight_script}" "${preflight_args[@]}" --network
fi
if [[ "${CTSTEG_ALLOW_FLOATING_GIT_REF}" != "1" ]]; then
  [[ "${CTSTEG_GIT_REF}" =~ ^[0-9a-f]{40}$ ]] || {
    fail "CTSTEG_GIT_REF must be an exact 40-character commit SHA"
  }
fi

root_prefix=()
if ((EUID != 0)); then
  command -v sudo >/dev/null 2>&1 || {
    fail "root or passwordless sudo is required"
  }
  sudo -n true >/dev/null 2>&1 || {
    fail "passwordless sudo is not available"
  }
  root_prefix=(sudo -n)
fi

root_run() {
  "${root_prefix[@]}" "$@"
}

service_run() {
  root_run runuser -u "${CTSTEG_SERVICE_USER}" -- "$@"
}

verify_installation() {
  local current="${CTSTEG_INSTALL_ROOT}/current"
  local gate="${CTSTEG_DATA_ROOT}/gates/latest_runtime_gate.json"
  local failures=0
  root_run test -L "${current}" || {
    echo "missing current release symlink: ${current}" >&2
    failures=$((failures + 1))
  }
  root_run test -x "${current}/venv/bin/ctsteg" || {
    echo "missing ctsteg executable" >&2
    failures=$((failures + 1))
  }
  local installed_commit
  installed_commit="$(
    service_run git -C "${current}" rev-parse HEAD 2>/dev/null || true
  )"
  if [[ ! "${installed_commit}" =~ ^[0-9a-f]{40}$ ]]; then
    echo "current release is not a Git worktree" >&2
    failures=$((failures + 1))
  elif [[ "${CTSTEG_ALLOW_FLOATING_GIT_REF}" != "1" \
    && "${installed_commit}" != "${CTSTEG_GIT_REF}" ]]
  then
    echo "current release does not match CTSTEG_GIT_REF" >&2
    failures=$((failures + 1))
  fi
  if [[ "${CTSTEG_RUN_RUNTIME_GATE}" == "1" ]]; then
    root_run test -r "${gate}" || {
      echo "missing runtime gate report" >&2
      failures=$((failures + 1))
    }
  fi
  if [[ "${CTSTEG_INSTALL_MATLAB}" == "1" ]]; then
    root_run test -x "${CTSTEG_MATLAB_ROOT}/bin/matlab" || {
      echo "missing MATLAB executable" >&2
      failures=$((failures + 1))
    }
  fi
  if [[ "${CTSTEG_INSTALL_CONTOURLET}" == "1" ]]; then
    root_run test -f "${CTSTEG_INSTALL_ROOT}/toolboxes/contourlet/pdfbdec.m" || {
      echo "missing contourlet pdfbdec.m" >&2
      failures=$((failures + 1))
    }
    root_run test -f "${CTSTEG_INSTALL_ROOT}/toolboxes/contourlet/pdfbrec.m" || {
      echo "missing contourlet pdfbrec.m" >&2
      failures=$((failures + 1))
    }
  fi
  if [[ "${CTSTEG_RUN_RUNTIME_GATE}" == "1" ]] \
    && root_run test -x "${current}/venv/bin/python" \
    && root_run test -r "${gate}"
  then
    service_run \
      "${current}/venv/bin/python" \
      - \
      "${gate}" <<'PY' || failures=$((failures + 1))
from pathlib import Path
import sys
from ctsteg.runtime_gate_contract import validate_runtime_gate_report

validated = validate_runtime_gate_report(Path(sys.argv[1]))
print("runtime gate:", validated["status"])
PY
  fi
  if ((failures)); then
    return 1
  fi
  log "verification passed"
}

if [[ "${mode}" == "verify" ]]; then
  verify_installation
  exit $?
fi
if [[ "${mode}" == "ensure" ]]; then
  if verify_installation; then
    log "pinned server release is already ready"
    exit 0
  fi
  log "verification requires repair; entering idempotent apply mode"
  mode="apply"
fi

preflight_report="$(mktemp)"
bootstrap_tmp=""
repository_candidate=""
cleanup() {
  if [[ -n "${preflight_report:-}" && -f "${preflight_report}" ]]; then
    rm -f -- "${preflight_report}"
  fi
  if [[ -n "${bootstrap_tmp:-}" \
    && -d "${bootstrap_tmp}" \
    && "${bootstrap_tmp}" == /tmp/ctsteg.* ]]
  then
    root_run rm -rf -- "${bootstrap_tmp}"
  fi
  if [[ -n "${repository_candidate:-}" \
    && "${repository_candidate}" == "${CTSTEG_INSTALL_ROOT}"/.repository-*.partial \
    && -e "${repository_candidate}" ]]
  then
    root_run rm -rf -- "${repository_candidate}"
  fi
}
trap cleanup EXIT

python3 \
  "${preflight_script}" \
  "${preflight_args[@]}" \
  --network \
  >"${preflight_report}"
log "server preflight passed"

export DEBIAN_FRONTEND=noninteractive
ctsteg_retry_command \
  "Ubuntu package index" \
  root_run apt-get \
  -o Acquire::Retries=5 \
  -o DPkg::Lock::Timeout=120 \
  update
ctsteg_retry_command \
  "Ubuntu package installation" \
  root_run apt-get \
  -o Acquire::Retries=5 \
  -o DPkg::Lock::Timeout=120 \
  install \
  --no-install-recommends \
  -y \
  ca-certificates \
  curl \
  git \
  htop \
  jq \
  lsof \
  logrotate \
  procps \
  python3 \
  python3-pip \
  python3-venv \
  rsync \
  sysstat \
  tar \
  tmux \
  unzip \
  xz-utils \
  zip \
  zstd

if ! getent group "${CTSTEG_SERVICE_USER}" >/dev/null; then
  root_run groupadd --system "${CTSTEG_SERVICE_USER}"
fi
if ! id -u "${CTSTEG_SERVICE_USER}" >/dev/null 2>&1; then
  root_run useradd \
    --system \
    --gid "${CTSTEG_SERVICE_USER}" \
    --home-dir /var/lib/ctsteg \
    --create-home \
    --shell /usr/sbin/nologin \
    "${CTSTEG_SERVICE_USER}"
fi

for directory in \
  "${CTSTEG_INSTALL_ROOT}" \
  "${CTSTEG_INSTALL_ROOT}/releases" \
  "${CTSTEG_INSTALL_ROOT}/toolboxes" \
  "${CTSTEG_INSTALL_ROOT}/tools" \
  "${CTSTEG_DATA_ROOT}" \
  "${CTSTEG_DATA_ROOT}/bootstrap" \
  "${CTSTEG_DATA_ROOT}/cache" \
  "${CTSTEG_DATA_ROOT}/data" \
  "${CTSTEG_DATA_ROOT}/gates" \
  "${CTSTEG_DATA_ROOT}/inputs" \
  "${CTSTEG_DATA_ROOT}/monitor" \
  "${CTSTEG_DATA_ROOT}/provenance" \
  "${CTSTEG_DATA_ROOT}/results"
do
  root_run install \
    -d \
    -o "${CTSTEG_SERVICE_USER}" \
    -g "${CTSTEG_SERVICE_USER}" \
    -m 0750 \
    "${directory}"
done

root_run install \
  -m 0644 \
  "${preflight_report}" \
  "${CTSTEG_DATA_ROOT}/provenance/server-preflight.json"

bootstrap_tmp="$(mktemp -d -t ctsteg.XXXXXXXX)"

if [[ "${CTSTEG_INSTALL_MATLAB}" == "1" ]]; then
  # MathWorks publishes release/Ubuntu-specific runtime dependencies here.
  # The release directory is lower-case even though mpm accepts R2026a.
  release_lower="${CTSTEG_MATLAB_RELEASE,,}"
  release_lower="${release_lower%%u[0-9]*}"
  # shellcheck disable=SC1091
  source /etc/os-release
  dependencies_url="https://raw.githubusercontent.com/mathworks-ref-arch/container-images/main/matlab-deps/${release_lower}/ubuntu${VERSION_ID}/base-dependencies.txt"
  dependencies_file="${bootstrap_tmp}/matlab-base-dependencies.txt"
  ctsteg_retry_command \
    "MathWorks dependency manifest" \
    curl \
    --fail \
    --location \
    --connect-timeout 30 \
    --retry 3 \
    --retry-all-errors \
    --retry-delay 2 \
    --retry-max-time 180 \
    --output "${dependencies_file}" \
    "${dependencies_url}"
  mapfile -t matlab_dependencies < <(
    sed -e 's/#.*$//' -e '/^[[:space:]]*$/d' "${dependencies_file}"
  )
  ((${#matlab_dependencies[@]} > 0)) || {
    fail "MathWorks dependency list is empty"
  }
  ctsteg_retry_command \
    "MATLAB Ubuntu dependencies" \
    root_run apt-get \
    -o Acquire::Retries=5 \
    -o DPkg::Lock::Timeout=120 \
    install \
    --no-install-recommends \
    -y \
    "${matlab_dependencies[@]}"
fi

repository="${CTSTEG_INSTALL_ROOT}/repository.git"
if [[ ! -d "${repository}" ]]; then
  repository_candidate="${CTSTEG_INSTALL_ROOT}/.repository-${BASHPID}.partial"
  clone_repository_once() {
    if [[ -e "${repository}" ]]; then
      return 0
    fi
    [[ "${repository_candidate}" == "${CTSTEG_INSTALL_ROOT}"/.repository-*.partial ]] \
      || return 64
    if [[ -e "${repository_candidate}" ]]; then
      service_run rm -rf -- "${repository_candidate}" || return $?
    fi
    service_run \
      git clone \
      --mirror \
      "${CTSTEG_REPOSITORY_URL}" \
      "${repository_candidate}" \
      || return $?
    service_run mv "${repository_candidate}" "${repository}" || return $?
  }
  ctsteg_retry_command "Git repository clone" clone_repository_once
else
  configured_url="$(service_run git --git-dir="${repository}" remote get-url origin)"
  [[ "${configured_url}" == "${CTSTEG_REPOSITORY_URL}" ]] || {
    fail "existing repository origin does not match configured URL"
  }
fi
ctsteg_retry_command \
  "Git repository update" \
  service_run git --git-dir="${repository}" remote update --prune
commit="$(
  service_run \
    git \
    --git-dir="${repository}" \
    rev-parse \
    "${CTSTEG_GIT_REF}^{commit}"
)"
[[ "${commit}" =~ ^[0-9a-f]{40}$ ]] || {
  fail "configured git ref did not resolve to a commit"
}
if [[ "${CTSTEG_ALLOW_FLOATING_GIT_REF}" != "1" && "${commit}" != "${CTSTEG_GIT_REF}" ]]; then
  fail "resolved commit does not equal the locked CTSTEG_GIT_REF"
fi

release_dir="${CTSTEG_INSTALL_ROOT}/releases/${commit}"
if [[ ! -d "${release_dir}" ]]; then
  service_run \
    git \
    --git-dir="${repository}" \
    worktree \
    add \
    --detach \
    "${release_dir}" \
    "${commit}"
fi
resolved_release_commit="$(
  service_run git -C "${release_dir}" rev-parse HEAD
)"
[[ "${resolved_release_commit}" == "${commit}" ]] || {
  fail "existing release directory has a different commit"
}

tools_venv="${CTSTEG_INSTALL_ROOT}/tools/venv"
if [[ ! -x "${tools_venv}/bin/uv" ]]; then
  service_run python3 -m venv "${tools_venv}"
  ctsteg_retry_command \
    "uv installation" \
    service_run \
    "${tools_venv}/bin/python" \
    -m \
    pip \
    install \
    --disable-pip-version-check \
    "uv==${CTSTEG_UV_VERSION}"
fi
export UV_PYTHON_INSTALL_DIR="${CTSTEG_INSTALL_ROOT}/tools/python"
if [[ ! -x "${release_dir}/venv/bin/python" ]]; then
  ctsteg_retry_command \
    "Python ${CTSTEG_PYTHON_VERSION} installation" \
    service_run \
    env UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR}" \
    "${tools_venv}/bin/uv" \
    python \
    install \
    "${CTSTEG_PYTHON_VERSION}"
  service_run \
    env UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR}" \
    "${tools_venv}/bin/uv" \
    venv \
    --python "${CTSTEG_PYTHON_VERSION}" \
    "${release_dir}/venv"
fi
ctsteg_retry_command \
  "project dependency installation" \
  service_run \
  "${tools_venv}/bin/uv" \
  pip \
  install \
  --python "${release_dir}/venv/bin/python" \
  "${release_dir}[research,test]"

if [[ "${CTSTEG_RUN_TESTS}" == "1" ]]; then
  service_run \
    env PYTHONPATH="${release_dir}/src" \
    "${release_dir}/venv/bin/python" \
    -m unittest discover \
    -s "${release_dir}/tests" \
    -v
fi

if [[ -e "${CTSTEG_INSTALL_ROOT}/current" && ! -L "${CTSTEG_INSTALL_ROOT}/current" ]]; then
  fail "${CTSTEG_INSTALL_ROOT}/current exists and is not a symlink"
fi
current_temporary="${CTSTEG_INSTALL_ROOT}/.current-${commit}"
root_run ln -sfn "${release_dir}" "${current_temporary}"
root_run mv -Tf "${current_temporary}" "${CTSTEG_INSTALL_ROOT}/current"

if [[ "${CTSTEG_INSTALL_MATLAB}" == "1" ]]; then
  mpm="${CTSTEG_INSTALL_ROOT}/tools/mpm"
  if [[ ! -x "${mpm}" ]]; then
    ctsteg_retry_command \
      "MATLAB Package Manager download" \
      root_run curl \
      --fail \
      --location \
      --connect-timeout 30 \
      --retry 3 \
      --retry-all-errors \
      --retry-delay 2 \
      --retry-max-time 180 \
      --output "${mpm}" \
      https://www.mathworks.com/mpm/glnxa64/mpm
    root_run chmod 0755 "${mpm}"
  fi
  read -r -a matlab_products <<<"${CTSTEG_MATLAB_PRODUCTS}"
  ((${#matlab_products[@]} > 0)) || {
    fail "CTSTEG_MATLAB_PRODUCTS must contain at least MATLAB"
  }
  for product in "${matlab_products[@]}"; do
    [[ "${product}" =~ ^[A-Za-z0-9_.+()-]+$ ]] || {
      fail "unsafe MATLAB product identifier: ${product}"
    }
  done
  matlab_tmp="${CTSTEG_DATA_ROOT}/bootstrap/matlab-tmp"
  root_run install -d -m 0755 "${matlab_tmp}"
  mpm_arguments=(
    install
    "--release=${CTSTEG_MATLAB_RELEASE}"
    "--destination=${CTSTEG_MATLAB_ROOT}"
    "--products=${matlab_products[0]}"
  )
  if ((${#matlab_products[@]} > 1)); then
    mpm_arguments+=("${matlab_products[@]:1}")
  fi
  install_parallel_toolbox=0
  for product in "${matlab_products[@]}"; do
    if [[ "${product}" == "Parallel_Computing_Toolbox" ]]; then
      install_parallel_toolbox=1
    fi
  done
  if [[ "${CTSTEG_MATLAB_NO_GPU}" == "1" && "${install_parallel_toolbox}" == "1" ]]; then
    mpm_arguments+=(--no-gpu)
  fi
  ctsteg_retry_command_n \
    3 \
    "MATLAB product installation" \
    root_run env TMPDIR="${matlab_tmp}" "${mpm}" "${mpm_arguments[@]}"
  [[ -x "${CTSTEG_MATLAB_ROOT}/bin/matlab" ]] || {
    fail "mpm completed without a MATLAB executable"
  }
  root_run ln -sfn "${CTSTEG_MATLAB_ROOT}/bin/matlab" /usr/local/bin/matlab
  {
    "${mpm}" --version || true
    sha256sum "${mpm}"
  } | root_run tee "${CTSTEG_DATA_ROOT}/provenance/mpm.txt" >/dev/null
fi

if [[ "${CTSTEG_INSTALL_CONTOURLET}" == "1" ]]; then
  [[ -r "${CTSTEG_CONTOURLET_ARCHIVE}" ]] || {
    fail "Contourlet archive is not readable: ${CTSTEG_CONTOURLET_ARCHIVE}"
  }
  [[ "${CTSTEG_CONTOURLET_ARCHIVE_SHA256}" =~ ^[0-9a-f]{64}$ ]] || {
    fail "CTSTEG_CONTOURLET_ARCHIVE_SHA256 must be a lowercase SHA-256"
  }
  actual_toolbox_sha="$(sha256sum "${CTSTEG_CONTOURLET_ARCHIVE}" | awk '{print $1}')"
  [[ "${actual_toolbox_sha}" == "${CTSTEG_CONTOURLET_ARCHIVE_SHA256}" ]] || {
    fail "Contourlet archive SHA-256 mismatch"
  }
  toolbox_release="${CTSTEG_INSTALL_ROOT}/toolboxes/contourlet-${actual_toolbox_sha:0:16}"
  if [[ ! -d "${toolbox_release}" ]]; then
    toolbox_temporary="${bootstrap_tmp}/contourlet-extract"
    root_run mkdir "${toolbox_temporary}"
    root_run \
      unzip \
      -q \
      "${CTSTEG_CONTOURLET_ARCHIVE}" \
      -d "${toolbox_temporary}"
    root_run mv "${toolbox_temporary}" "${toolbox_release}"
    root_run chown -R "root:${CTSTEG_SERVICE_USER}" "${toolbox_release}"
    root_run chmod -R g=rX,o= "${toolbox_release}"
  fi
  pdfbdec_path="$(find "${toolbox_release}" -type f -name pdfbdec.m -print -quit)"
  [[ -n "${pdfbdec_path}" ]] || {
    fail "Contourlet archive does not contain pdfbdec.m"
  }
  toolbox_root="$(dirname -- "${pdfbdec_path}")"
  [[ -f "${toolbox_root}/pdfbrec.m" ]] || {
    fail "pdfbrec.m is not beside pdfbdec.m"
  }
  root_run ln \
    -sfn \
    "${toolbox_root}" \
    "${CTSTEG_INSTALL_ROOT}/toolboxes/contourlet"
  printf '%s  %s\n' \
    "${actual_toolbox_sha}" \
    "${CTSTEG_CONTOURLET_ARCHIVE}" \
    | root_run tee \
      "${CTSTEG_DATA_ROOT}/provenance/contourlet-archive.sha256" \
      >/dev/null
  printf '%s\n' "${toolbox_root}" \
    | root_run tee \
      "${CTSTEG_DATA_ROOT}/provenance/contourlet-path.txt" \
      >/dev/null
fi

if [[ "${CTSTEG_PREFETCH_USC_SIPI}" == "1" ]]; then
  service_run \
    "${release_dir}/venv/bin/python" \
    "${release_dir}/scripts/download_usc_sipi.py" \
    --output-dir "${CTSTEG_DATA_ROOT}/data/usc_sipi" \
    --skip-existing
fi

gate_dir="${CTSTEG_DATA_ROOT}/gates/${commit}"
if [[ "${CTSTEG_RUN_RUNTIME_GATE}" == "1" ]]; then
  if [[ -r "${gate_dir}/latest_runtime_gate.json" ]]; then
    if ! service_run \
      "${release_dir}/venv/bin/python" \
      - "${gate_dir}/latest_runtime_gate.json" <<'PY'
from pathlib import Path
import sys
from ctsteg.runtime_gate_contract import validate_runtime_gate_report

validate_runtime_gate_report(Path(sys.argv[1]))
PY
    then
      gate_dir="${CTSTEG_DATA_ROOT}/gates/${commit}-$(date -u +%Y%m%dT%H%M%SZ)"
    fi
  fi
  if [[ ! -r "${gate_dir}/latest_runtime_gate.json" ]]; then
    ctsteg_retry_command_n \
      "${CTSTEG_RUNTIME_GATE_ATTEMPTS}" \
      "runtime SIGKILL/resume gate" \
      service_run \
      "${release_dir}/venv/bin/ctsteg" \
      runtime-gate \
      --output-dir "${gate_dir}" \
      --workers 2 \
      --jobs 8 \
      --delay-seconds 0.35 \
      --timeout-seconds 60
  fi
  root_run ln \
    -sfn \
    "${gate_dir}/latest_runtime_gate.json" \
    "${CTSTEG_DATA_ROOT}/gates/latest_runtime_gate.json"
fi

root_run install \
  -m 0755 \
  "${release_dir}/scripts/bootstrap_ubuntu_server.sh" \
  /usr/local/sbin/ctsteg-bootstrap
root_run install \
  -d \
  -o root \
  -g root \
  -m 0755 \
  /usr/local/libexec/ctsteg
root_run install \
  -m 0644 \
  "${release_dir}/scripts/bootstrap_retry.sh" \
  /usr/local/libexec/ctsteg/bootstrap_retry.sh
root_run install \
  -m 0644 \
  "${release_dir}/scripts/server_preflight.py" \
  /usr/local/libexec/ctsteg/server_preflight.py
root_run install \
  -m 0644 \
  "${release_dir}/deploy/systemd/ctsteg-bootstrap.service" \
  /etc/systemd/system/ctsteg-bootstrap.service
root_run install \
  -m 0644 \
  "${release_dir}/deploy/systemd/ctsteg-monitor@.service" \
  /etc/systemd/system/ctsteg-monitor@.service
root_run install \
  -m 0644 \
  "${release_dir}/deploy/systemd/ctsteg-research@.service" \
  /etc/systemd/system/ctsteg-research@.service
root_run install \
  -m 0644 \
  "${release_dir}/deploy/logrotate/ctsteg-monitor" \
  /etc/logrotate.d/ctsteg-monitor
root_run install \
  -d \
  -o root \
  -g "${CTSTEG_SERVICE_USER}" \
  -m 0750 \
  /etc/ctsteg-research
if [[ ! -e "/etc/ctsteg-research/${CTSTEG_SERVICE_INSTANCE}.env" ]]; then
  root_run install \
    -o root \
    -g "${CTSTEG_SERVICE_USER}" \
    -m 0640 \
    "${release_dir}/deploy/systemd/research.env.example" \
    "/etc/ctsteg-research/${CTSTEG_SERVICE_INSTANCE}.env"
fi
if [[ "${config_file}" != "/etc/ctsteg-bootstrap.env" ]]; then
  root_run install \
    -o root \
    -g root \
    -m 0600 \
    "${config_file}" \
    /etc/ctsteg-bootstrap.env
fi
root_run systemctl daemon-reload
root_run systemctl enable ctsteg-bootstrap.service
if [[ "${CTSTEG_ENABLE_MONITOR_SERVICE}" == "1" ]]; then
  root_run systemctl enable "ctsteg-monitor@${CTSTEG_SERVICE_INSTANCE}.service"
fi
if [[ "${CTSTEG_ENABLE_RESEARCH_SERVICE}" == "1" ]]; then
  root_run systemctl enable "ctsteg-research@${CTSTEG_SERVICE_INSTANCE}.service"
fi

verify_installation
log "installed commit ${commit}"
log "monitor command: ${release_dir}/venv/bin/ctsteg research-status --output-root ${CTSTEG_DATA_ROOT}/results"
log "services are enabled for the next boot; start the research instance only after scientific inputs are locked"
