# Contourlet Steganography Server Control

Private control plane for the Ferdowsi FINAL-5J research server.

This repository is intentionally separate from the public scientific repository. Its self-hosted runner is repository-scoped and accepts only validated control requests under `requests/*.json`.

It contains no scientific datasets, SSH private keys, server passwords, GitHub runner registration tokens, PATs, MATLAB credentials, license keys, or recovery material.

## Runner label

The Ferdowsi runner must have the dedicated label `ctsteg-ferdowsi-8c16g` in addition to GitHub's standard `self-hosted`, `linux`, and `x64` labels.

## Routine control

Routine chat-driven operations are triggered by adding exactly one JSON file under `requests/`. The self-hosted workflow validates that HEAD changed exactly one request JSON, validates the command allowlist and exact scientific commit SHA, and then executes only fixed argv-based operations.

Scientific worker requests are capped at 7 for the current 8-core/16-GB/100-GB server profile. Values above 7 are rejected before benchmark execution.

See `docs/RUNNER_OPERATIONS.md` for bootstrap, service, firewall, and removal procedures.

## Template completeness and public-repository boundary

This directory is a self-contained seed for the **private** control repository.
It includes the `control/` package and its `tests/`; CI in the private repository
must pass before the Ferdowsi runner is registered. The public scientific
repository must not contain a workflow that targets the self-hosted
`ctsteg-ferdowsi-8c16g` runner.

The non-secret control configuration is bound to the current finalizer outputs:
`/srv/ctsteg/finalization/final-5j-bound.json`,
`final-5j-runtime-bindings.json`, and `input-readiness.json`. The engineering
manifest is consumed from the exact pinned scientific checkout at
`/srv/ctsteg/control/scientific-repo/data-manifests/5j/dry_run.csv`.
