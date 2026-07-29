# Reproducible Ubuntu server deployment

## Scope

The server bundle prepares a pinned repository commit before scientific inputs
are available. It provides:

- read-only hardware, Ubuntu, privilege, disk, and network preflight;
- release-isolated Python 3.12 environments on Ubuntu 22.04 or 24.04;
- official MATLAB Package Manager installation of MATLAB R2026a;
- SHA-256-verified installation of the external Contourlet Toolbox archive;
- optional prefetch of documented USC-SIPI candidate images;
- all unit tests and the mandatory real-`SIGKILL` runtime gate;
- boot-time idempotent bootstrap and automatic research resume;
- a separate live resource/progress/ETA monitor.

Provisioning does not approve PDFB, select the final four pairs, or activate a
MATLAB license. Those remain explicit gates.

## Supported target

The locked server target is:

```text
Ubuntu 22.04 LTS or 24.04 LTS
x86-64 with AVX2
minimum:     16 logical CPUs, 32 GiB RAM, 250 GiB free persistent storage
recommended: 32 logical CPUs, 64 GiB RAM, 500 GiB free NVMe
```

MATLAB R2026a officially validates Ubuntu 22.04 and 24.04, recommends AVX2,
and strongly recommends SSD storage:

- <https://www.mathworks.com/support/requirements/matlab-linux.html>

The project uses Python worker processes for the 64/88 matrix. Parallel
Computing Toolbox is therefore not required on a single server. The Stage-0
PDFB audit requires MATLAB plus Minh Do's external Contourlet Toolbox. The
legacy `matlab/run_pair.m` path additionally uses Image Processing Toolbox, so
the default bootstrap prepares both licensed MathWorks products.

## Secret boundary

Never put a private SSH key, GitHub token, MathWorks password, license key, or
File Installation Key in:

- chat;
- the Git repository;
- `server.env`;
- `/etc/ctsteg-research/*.env`;
- a shell command line.

Use a temporary SSH public key for server access. MATLAB network-license
material belongs in a root-controlled credential file, such as
`/etc/ctsteg-credentials/network.lic`, or in the approved license-manager
address supplied through `MLM_LICENSE_FILE`. Individual-license activation is
a separate one-time MathWorks step.

MATLAB installation and MATLAB licensing are different checks. `mpm` can
prepare the binaries, but the bootstrap does not claim that `matlab -batch`
works until a valid license is configured.

## External Contourlet Toolbox

The project does not redistribute File Exchange submission 8837. Download
version 1.0.0.0 under its displayed terms, transfer the archive to:

```text
/srv/ctsteg/bootstrap/contourlet_toolbox.zip
```

Then record its digest:

```bash
sha256sum /srv/ctsteg/bootstrap/contourlet_toolbox.zip
```

Put only that digest and path in the bootstrap configuration. The installer
rejects a mismatch and verifies that `pdfbdec.m` and `pdfbrec.m` share the
resolved toolbox root.

File Exchange source:

- <https://www.mathworks.com/matlabcentral/fileexchange/8837-contourlet-toolbox>

## One-time installation

Copy and edit the non-secret configuration:

```bash
sudo install -m 0600 \
  deploy/bootstrap/server.env.example \
  /etc/ctsteg-bootstrap.env

sudoedit /etc/ctsteg-bootstrap.env
```

`CTSTEG_GIT_REF` must normally be the exact 40-character commit to deploy.
Floating branches are rejected so a reboot cannot silently change scientific
code.

Run the read-only preflight first:

```bash
./scripts/bootstrap_ubuntu_server.sh \
  --check \
  --config /etc/ctsteg-bootstrap.env
```

Apply only after `ready=true`:

```bash
sudo ./scripts/bootstrap_ubuntu_server.sh \
  --apply \
  --config /etc/ctsteg-bootstrap.env
```

Verify without changing packages, Git, or services:

```bash
sudo /usr/local/sbin/ctsteg-bootstrap \
  --verify \
  --config /etc/ctsteg-bootstrap.env
```

The installer is idempotent. Each Git commit gets its own worktree and virtual
environment under `/opt/ctsteg/releases/<commit>`. The `current` symlink moves
only after installation and tests pass.

On Ubuntu 22.04, the project does not depend on the system Python 3.10.
The bootstrap uses a pinned `uv` installer environment to obtain the configured
Python release.

## Retry and failure policy

Temporary operations are retried with recorded, bounded exponential backoff:

- package, Git, Python, and download operations: up to 8 attempts;
- each preflight HTTPS target: up to 4 attempts, checked concurrently;
- the real `SIGKILL`/resume runtime gate: up to 3 independent attempts;
- an operational research exit: up to 12 service starts per hour;
- a transient boot-time bootstrap failure: up to 12 starts per day.

The defaults are configurable with the `CTSTEG_RETRY_*`,
`CTSTEG_NETWORK_CHECK_*`, and `CTSTEG_RUNTIME_GATE_ATTEMPTS` settings in
`deploy/bootstrap/server.env.example`.

The limits are intentional. Exit `2` (scientific/environment blocker) and exit
`64` (configuration or integrity error) are not restarted. A bad checksum,
missing license, invalid manifest, or failed scientific gate therefore cannot
be hidden by an infinite retry loop. Each failed attempt remains in the
journal or the corresponding runtime attempt directory.

## MATLAB installation behavior

The bootstrap downloads the latest official `mpm` binary from:

```text
https://www.mathworks.com/mpm/glnxa64/mpm
```

It obtains the release/Ubuntu dependency list from MathWorks' reference
container repository and runs:

```text
mpm install --release=R2026a \
  --destination=/opt/matlab/R2026a \
  --products=MATLAB Image_Processing_Toolbox
```

`mpm` skips already installed products. Its binary hash and version are saved
under `/srv/ctsteg/provenance/`.

Official MPM references:

- <https://www.mathworks.com/help/install/ug/get-mpm-os-command-line.html>
- <https://www.mathworks.com/help/install/ug/mpminstall.html>

## Data boundary

`CTSTEG_PREFETCH_USC_SIPI=1` downloads and validates the documented candidate
images into `/srv/ctsteg/data/usc_sipi`. Existing valid images are reused.

This is only a warm cache. It does not:

- identify the article's ambiguous “Jet” label;
- decide cover-secret pairing;
- create the four-row `traceability_core` manifest;
- create the calibration-only stability profile;
- authorize a final run.

## Boot sequence

The installer enables these units:

```text
ctsteg-bootstrap.service
ctsteg-monitor@final.service
ctsteg-research@final.service   # only when explicitly enabled
```

At boot:

1. network and persistent filesystems become ready;
2. bootstrap runs a fast verification and enters idempotent repair/install
   only if the pinned release is incomplete;
3. the monitor starts;
4. the research service runs the same idempotent command;
5. complete cache objects are reused and only interrupted work repeats.

The research service does not restart a scientific clean-gate stop. It does
restart operational failures within a bounded systemd start limit. The
bootstrap service follows the same distinction: transient exit codes restart,
while permanent codes `2` and `64` stop for operator correction.

Keep `CTSTEG_ENABLE_RESEARCH_SERVICE=0` until the approved adapter/config,
four-row manifest, and stability artifact exist. Enabling a service must not
bypass scientific gates.

## Live status and ETA

The monitor writes:

```text
/srv/ctsteg/monitor/latest.json
/srv/ctsteg/monitor/samples.jsonl
```

The sample history is rotated daily, compressed, and retained for 30
rotations. `latest.json` always remains the current atomic snapshot.

Human-readable status:

```bash
/opt/ctsteg/current/venv/bin/ctsteg research-status \
  --output-root /srv/ctsteg/results
```

Interactive watch:

```bash
/opt/ctsteg/current/venv/bin/ctsteg research-status \
  --output-root /srv/ctsteg/results \
  --watch \
  --interval-seconds 5
```

Machine-readable status:

```bash
/opt/ctsteg/current/venv/bin/ctsteg research-status \
  --output-root /srv/ctsteg/results \
  --json
```

The status distinguishes:

- algorithm CPU as a percentage of one core;
- algorithm CPU as a percentage of allocated worker capacity;
- whole-host CPU busy percentage and I/O wait;
- algorithm RSS and whole-host memory pressure;
- process-tree read/write throughput and filesystem free space;
- mandatory, selected-after-trigger, and absolute-maximum progress;
- observed tasks/hour and completion ETA.

ETA remains `warming up` until duration evidence exists. After at least two
current-stage completions it uses real stage throughput. Future-stage estimates
use medians from completed content objects and are labelled with lower
confidence.

`using_allocated_cpu` means the process tree is using at least 85% of the CPU
capacity allowed by the selected worker count. `io_wait_limited` and
`memory_pressure` identify why CPU may legitimately be below that level.

Live telemetry is outside each research run directory. It cannot alter object
IDs, scientific payloads, `checksums.sha256`, or archive reuse.

## Operations

```bash
sudo systemctl status ctsteg-bootstrap.service
sudo systemctl status ctsteg-monitor@final.service
sudo systemctl status ctsteg-research@final.service

sudo journalctl -u ctsteg-bootstrap.service -n 200 --no-pager
sudo journalctl -u ctsteg-monitor@final.service -f
sudo journalctl -u ctsteg-research@final.service -f
```

Start the final service only after its inputs are locked:

```bash
sudo systemctl enable --now ctsteg-research@final.service
```

Disabling a service does not delete results or cache objects.

## No-sudo outcome

The read-only preflight reports whether the SSH user is root, has
passwordless sudo, needs an interactive sudo password, or has no sudo.

True unattended boot installation needs one administrator-authorized system
setup. Without it, project files can be installed in a user directory, but a
reliable boot service, service user, protected `/opt` and `/srv` paths, and
system package/MATLAB dependency installation cannot be guaranteed. The
bootstrap therefore fails closed instead of pretending a login-only user
service is equivalent.

## GitHub boundary

The server bootstrap reads a public repository commit. It does not store a
GitHub write token and does not automatically push scientific results.
Publishing code, reports, and a large release archive is a separate,
reviewable step after checksum validation.
