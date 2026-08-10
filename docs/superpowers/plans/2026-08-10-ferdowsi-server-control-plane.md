# Ferdowsi Server Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a private, repository-scoped GitHub Actions control plane that can operate the Ferdowsi research server from GitHub without exposing the public scientific repository to self-hosted-runner execution risk.

**Architecture:** A private repository `alirezaabbaszadeh/contourlet-steganography-control` owns the self-hosted runner and contains a small validated command dispatcher. The public scientific repository remains the source of scientific code and every scientific operation is pinned to an exact 40-character commit SHA. Server jobs are routed only to the dedicated label `ctsteg-ferdowsi-48` and arbitrary shell input is not accepted.

**Tech Stack:** GitHub Actions, Python 3.12, JSON, Bash, GitHub self-hosted Actions runner, Ubuntu 24.04.

## Global Constraints

- Control repository must be private.
- Self-hosted runner is repository-scoped to the private control repository only.
- Public scientific repository does not target the self-hosted runner.
- No SSH private key, server password, registration token, PAT, MATLAB credential, license key, or recovery key is committed or logged.
- Scientific operations require an exact 40-character hexadecimal commit SHA.
- Current server profile is 48 logical CPUs with a hard maximum of 44 scientific workers.
- Internal numerical workers remain single-threaded.
- Existing scientific/runtime/backup gates remain authoritative and cannot be bypassed by the control plane.
- Large scientific outputs stay on persistent server storage; GitHub receives bounded logs, summaries, checksums, and small artifacts only.

---

### Task 1: Create and Secure the Private Control Repository

**Files:**
- Create in control repo: `README.md`

**Interfaces:**
- Consumes: GitHub account ownership of `alirezaabbaszadeh`.
- Produces: private repository `alirezaabbaszadeh/contourlet-steganography-control` with Actions enabled.

- [ ] **Step 1: Create the repository as private**

Create `alirezaabbaszadeh/contourlet-steganography-control` with visibility `private`, no public template, and GitHub Actions enabled.

- [ ] **Step 2: Verify visibility before adding runner**

Confirm repository metadata reports `visibility=private`. Do not continue if it reports `public`.

- [ ] **Step 3: Add a minimal README**

```markdown
# Contourlet Steganography Server Control

Private control plane for the Ferdowsi FINAL-5J research server.

This repository contains no scientific datasets, SSH private keys, passwords,
runner registration tokens, MATLAB credentials, or license material.
```

- [ ] **Step 4: Commit**

Commit message:

```text
chore: initialize private server control repository
```

---

### Task 2: Implement Request Validation with Tests

**Files:**
- Create: `control/request.py`
- Create: `control/__init__.py`
- Create: `tests/test_request.py`
- Create: `pyproject.toml`

**Interfaces:**
- Consumes: JSON object loaded from workflow request file.
- Produces: `ControlRequest` dataclass and `parse_request(payload: dict) -> ControlRequest`.

- [ ] **Step 1: Write the failing tests**

```python
import unittest

from control.request import RequestError, parse_request

SHA = "a" * 40


class RequestTests(unittest.TestCase):
    def test_accepts_health_check(self):
        request = parse_request({
            "schema_version": 1,
            "command": "health_check",
            "scientific_repository": "alirezaabbaszadeh/contourlet-steganography-repro",
            "scientific_commit": SHA,
        })
        self.assertEqual(request.command, "health_check")
        self.assertEqual(request.scientific_commit, SHA)

    def test_rejects_unknown_command(self):
        with self.assertRaisesRegex(RequestError, "unknown command"):
            parse_request({
                "schema_version": 1,
                "command": "shell",
                "scientific_repository": "alirezaabbaszadeh/contourlet-steganography-repro",
                "scientific_commit": SHA,
            })

    def test_rejects_floating_ref(self):
        with self.assertRaisesRegex(RequestError, "40-character"):
            parse_request({
                "schema_version": 1,
                "command": "runtime_check",
                "scientific_repository": "alirezaabbaszadeh/contourlet-steganography-repro",
                "scientific_commit": "main",
            })

    def test_rejects_worker_count_above_44(self):
        with self.assertRaisesRegex(RequestError, "maximum worker count is 44"):
            parse_request({
                "schema_version": 1,
                "command": "worker_benchmark",
                "scientific_repository": "alirezaabbaszadeh/contourlet-steganography-repro",
                "scientific_commit": SHA,
                "workers": 45,
            })

    def test_rejects_unknown_field(self):
        with self.assertRaisesRegex(RequestError, "unknown fields"):
            parse_request({
                "schema_version": 1,
                "command": "health_check",
                "scientific_repository": "alirezaabbaszadeh/contourlet-steganography-repro",
                "scientific_commit": SHA,
                "shell": "id",
            })


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: FAIL because `control.request` does not exist.

- [ ] **Step 3: Implement minimal validator**

```python
from __future__ import annotations

from dataclasses import dataclass
import re


COMMANDS = {
    "health_check",
    "runtime_check",
    "bootstrap_check",
    "worker_benchmark",
    "research_status",
    "run_final_5j",
}
REPOSITORY = "alirezaabbaszadeh/contourlet-steganography-repro"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class RequestError(ValueError):
    pass


@dataclass(frozen=True)
class ControlRequest:
    command: str
    scientific_repository: str
    scientific_commit: str
    workers: int | None = None


def parse_request(payload: dict) -> ControlRequest:
    if payload.get("schema_version") != 1:
        raise RequestError("schema_version must be 1")
    command = payload.get("command")
    if command not in COMMANDS:
        raise RequestError("unknown command")
    repository = payload.get("scientific_repository")
    if repository != REPOSITORY:
        raise RequestError("unexpected scientific repository")
    commit = payload.get("scientific_commit")
    if not isinstance(commit, str) or not SHA_RE.fullmatch(commit):
        raise RequestError("scientific_commit must be a 40-character hexadecimal SHA")

    allowed = {"schema_version", "command", "scientific_repository", "scientific_commit"}
    workers = None
    if command == "worker_benchmark":
        allowed.add("workers")
        workers = payload.get("workers")
        if not isinstance(workers, int) or isinstance(workers, bool) or workers < 1:
            raise RequestError("workers must be a positive integer")
        if workers > 44:
            raise RequestError("maximum worker count is 44")

    unknown = set(payload) - allowed
    if unknown:
        raise RequestError(f"unknown fields: {sorted(unknown)}")

    return ControlRequest(command, repository, commit, workers)
```

Create `control/__init__.py` as an empty package marker.

Create `pyproject.toml`:

```toml
[project]
name = "ctsteg-server-control"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: all five request-validation tests PASS.

- [ ] **Step 5: Commit**

```bash
git add control tests pyproject.toml
git commit -m "feat: validate server control requests"
```

---

### Task 3: Implement Shell-Free Operation Dispatch

**Files:**
- Create: `control/dispatch.py`
- Create: `tests/test_dispatch.py`

**Interfaces:**
- Consumes: validated `ControlRequest`.
- Produces: `build_operation(request: ControlRequest, checkout: str) -> list[str]` returning an argv list, never a shell string.

- [ ] **Step 1: Write failing tests**

```python
import unittest

from control.dispatch import build_operation
from control.request import parse_request

SHA = "b" * 40


class DispatchTests(unittest.TestCase):
    def request(self, command, **extra):
        return parse_request({
            "schema_version": 1,
            "command": command,
            "scientific_repository": "alirezaabbaszadeh/contourlet-steganography-repro",
            "scientific_commit": SHA,
            **extra,
        })

    def test_health_check_is_fixed_program(self):
        argv = build_operation(self.request("health_check"), "/opt/ctsteg/control-checkout")
        self.assertEqual(argv[0], "python3")
        self.assertNotIn("sh", argv)
        self.assertNotIn("bash", argv)

    def test_worker_count_is_single_numeric_argument(self):
        argv = build_operation(self.request("worker_benchmark", workers=44), "/opt/ctsteg/control-checkout")
        self.assertIn("44", argv)
        self.assertTrue(all(";" not in item for item in argv))
```

- [ ] **Step 2: Run tests and verify failure**

```bash
python -m unittest tests.test_dispatch -v
```

Expected: FAIL because `control.dispatch` does not exist.

- [ ] **Step 3: Implement fixed argv dispatch**

Implement exact mappings:

```python
from __future__ import annotations

from pathlib import Path

from control.request import ControlRequest


def build_operation(request: ControlRequest, checkout: str) -> list[str]:
    root = Path(checkout)
    if request.command == "health_check":
        return ["python3", str(root / "scripts/5j/server_health_snapshot.py")]
    if request.command == "runtime_check":
        return ["python3", str(root / "scripts/5j/runtime_preflight.py")]
    if request.command == "bootstrap_check":
        return [str(root / "scripts/bootstrap_ubuntu_server.sh"), "--check", "--config", "/etc/ctsteg-bootstrap.env"]
    if request.command == "worker_benchmark":
        return ["python3", str(root / "scripts/5j/run_engineering_worker_trial.py"), "--workers", str(request.workers)]
    if request.command == "research_status":
        return ["python3", str(root / "scripts/5j/research_status.py"), "--output-root", "/srv/ctsteg/results", "--json"]
    if request.command == "run_final_5j":
        return ["python3", str(root / "scripts/5j/run_research.py"), "--output-root", "/srv/ctsteg/results"]
    raise AssertionError("validated command has no dispatcher")
```

If an exact scientific script path differs in the pinned repository, adjust this mapping to the existing path before enabling that operation; do not fall back to arbitrary shell execution.

- [ ] **Step 4: Run tests**

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: all validation and dispatch tests PASS.

- [ ] **Step 5: Commit**

```bash
git add control/dispatch.py tests/test_dispatch.py
git commit -m "feat: add fixed server operation dispatch"
```

---

### Task 4: Add GitHub-Hosted CI for the Control Repository

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: pushes and pull requests to the private control repository.
- Produces: validation test status on `ubuntu-latest`; never uses self-hosted runner.

- [ ] **Step 1: Add CI workflow**

```yaml
name: control-ci

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m unittest discover -s tests -p 'test_*.py' -v
```

- [ ] **Step 2: Verify runner isolation statically**

Run:

```bash
grep -R "runs-on:" .github/workflows/ci.yml
```

Expected: only `ubuntu-latest`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: validate server control plane"
```

---

### Task 5: Add Dedicated Self-Hosted Health Check

**Files:**
- Create: `.github/workflows/server-health.yml`

**Interfaces:**
- Consumes: manual `workflow_dispatch` only.
- Produces: bounded host snapshot from runner labeled `ctsteg-ferdowsi-48`.

- [ ] **Step 1: Add manual health workflow**

```yaml
name: Ferdowsi server health

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  health:
    runs-on: [self-hosted, linux, x64, ctsteg-ferdowsi-48]
    timeout-minutes: 10
    steps:
      - name: Host identity
        shell: bash
        run: |
          set -euo pipefail
          echo "hostname=$(hostname)"
          echo "kernel=$(uname -srmo)"
          echo "cpus=$(nproc)"
          free -h
          df -hT /
          swapon --show || true
          command -v python3 && python3 --version
          command -v octave && octave --version | head -3
```

This workflow intentionally contains no user-provided command input.

- [ ] **Step 2: Verify event and labels**

Run:

```bash
grep -nE 'workflow_dispatch|self-hosted|ctsteg-ferdowsi-48|pull_request' .github/workflows/server-health.yml
```

Expected: `workflow_dispatch`, `self-hosted`, and `ctsteg-ferdowsi-48` are present; `pull_request` is absent.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/server-health.yml
git commit -m "feat: add Ferdowsi runner health check"
```

---

### Task 6: Register the Repository-Scoped Runner on the Ferdowsi Server

**Files:**
- Server path: `/home/ubuntu/actions-runner/`
- No registration token file is created.

**Interfaces:**
- Consumes: GitHub's one-time repository runner registration command generated in the private control repository settings.
- Produces: online runner labeled `ctsteg-ferdowsi-48` running as a service.

- [ ] **Step 1: Generate registration instructions in GitHub UI**

Open the private control repository's **Settings → Actions → Runners → New self-hosted runner**, choose **Linux** and **x64**, and use the GitHub-generated version, checksum, repository URL, and ephemeral registration token exactly as displayed.

- [ ] **Step 2: Execute the generated download and checksum commands on the server**

Run them as `ubuntu` in `/home/ubuntu/actions-runner`. Do not paste the registration token into chat or any repository file.

- [ ] **Step 3: Configure with the dedicated label**

Use the generated `./config.sh` command and add:

```text
--name ferdowsi-48 --labels ctsteg-ferdowsi-48 --unattended
```

Keep the runner repository-scoped to `alirezaabbaszadeh/contourlet-steganography-control`.

- [ ] **Step 4: Install and start service**

From `/home/ubuntu/actions-runner`:

```bash
sudo ./svc.sh install ubuntu
sudo ./svc.sh start
sudo ./svc.sh status
```

Expected: service is active and GitHub shows `ferdowsi-48` as online/idle.

- [ ] **Step 5: Run manual health workflow**

Dispatch `Ferdowsi server health` and verify log contains expected host identity: hostname `48`, 48 logical CPUs, approximately 124 GiB visible memory, no swap, Python 3.12, and Octave 8.4.

---

### Task 7: Add Validated Server-Control Workflow

**Files:**
- Create: `.github/workflows/server-control.yml`
- Create: `control/run_request.py`
- Create: `requests/.gitkeep`

**Interfaces:**
- Consumes: manual path input naming a tracked JSON file under `requests/`.
- Produces: validated, exact-SHA server operation with bounded logs.

- [ ] **Step 1: Add request runner**

Implement `control/run_request.py` to:

1. Resolve the supplied request path under repository root and reject path traversal.
2. Load JSON.
3. Call `parse_request`.
4. Clone/fetch the scientific repository into `/srv/ctsteg/control/scientific-repo`.
5. Verify the requested commit exists and checkout detached `request.scientific_commit`.
6. Verify `git rev-parse HEAD` equals the requested SHA.
7. Call `build_operation` and execute with `subprocess.run(argv, check=False, shell=False, timeout=...)`.
8. Emit a JSON summary with request SHA-256, scientific commit, command, hostname, timestamps, and exit code.
9. Return the operation exit code.

No `shell=True` call is allowed.

- [ ] **Step 2: Add tests for path traversal and shell-free subprocess**

Create tests asserting `../request.json` is rejected and that dispatch uses an argv list. Mock `subprocess.run` and assert `shell=False`.

- [ ] **Step 3: Add manual control workflow**

```yaml
name: Ferdowsi server control

on:
  workflow_dispatch:
    inputs:
      request_path:
        description: Tracked JSON request under requests/
        required: true
        type: string

permissions:
  contents: read

jobs:
  control:
    runs-on: [self-hosted, linux, x64, ctsteg-ferdowsi-48]
    timeout-minutes: 180
    steps:
      - uses: actions/checkout@v4
      - name: Validate and run request
        env:
          REQUEST_PATH: ${{ inputs.request_path }}
        run: python3 -m control.run_request "$REQUEST_PATH"
```

- [ ] **Step 4: Run unit tests**

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add control tests requests .github/workflows/server-control.yml
git commit -m "feat: run validated server control requests"
```

---

### Task 8: Acceptance Test and Lock Down SSH Exposure

**Files:**
- Create: `docs/RUNNER_OPERATIONS.md`

**Interfaces:**
- Consumes: online self-hosted runner and successful health workflow.
- Produces: verified chat-to-GitHub-to-server control path and operational runbook.

- [ ] **Step 1: Verify health workflow from GitHub logs**

Confirm the job ran on `ferdowsi-48` and not `ubuntu-latest`.

- [ ] **Step 2: Verify request rejection**

Commit a request with `workers: 45` on a disposable branch or test fixture and verify validation rejects it before scientific execution.

- [ ] **Step 3: Verify exact-SHA checkout**

Run a `health_check` or `runtime_check` request pinned to an exact known commit and verify summary reports exactly that SHA.

- [ ] **Step 4: Document operations**

`docs/RUNNER_OPERATIONS.md` must document: runner label, private-repo scope, allowed commands, exact-SHA requirement, maximum 44 workers, how to view service status, how to disable/remove the runner, and the rule never to expose registration tokens or SSH credentials.

- [ ] **Step 5: Reduce SSH firewall exposure**

After runner control is proven, replace temporary `0.0.0.0/0` SSH source with the user's trusted public IP `/32` or disable external SSH when not needed. Do not rely on open SSH for routine ChatGPT control.

- [ ] **Step 6: Commit**

```bash
git add docs/RUNNER_OPERATIONS.md
git commit -m "docs: record server runner operations"
```

---

### Task 9: Prepare 48-vCPU Worker Autotuning as the Next Independent Plan

**Files:**
- No code change in this task.
- Follow-up plan will modify the scientific repository's worker autotuning files.

**Interfaces:**
- Consumes: working private control plane.
- Produces: reliable transport to run server benchmarks without manual command relay.

- [ ] **Step 1: Do not alter the current frozen worker code until its separate spec/plan is applied**

The existing 32-CPU/64-GiB worker profile is known to hard-code the old 28-worker ceiling. The next independent implementation plan will update that policy for the observed 48-CPU/124-GiB host, preserve four reserved CPUs, cap scientific workers at 44, and add a faster coarse-to-fine search strategy.

- [ ] **Step 2: Use the control plane for all real worker measurements**

Once the worker-autotuning plan is implemented, dispatch benchmark requests through the private runner and archive summaries before authorizing FINAL-5J.
