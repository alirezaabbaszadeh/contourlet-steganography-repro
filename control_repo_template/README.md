# Contourlet Steganography Server Control

Private control plane for the Ferdowsi FINAL-5J research server.

This repository is intentionally separate from the public scientific repository. Its self-hosted runner is repository-scoped and accepts only validated control requests under `requests/*.json`.

It contains no scientific datasets, SSH private keys, server passwords, GitHub runner registration tokens, PATs, MATLAB credentials, license keys, or recovery material.

## Runner label

The Ferdowsi runner must have the dedicated label `ctsteg-ferdowsi-48` in addition to GitHub's standard `self-hosted`, `linux`, and `x64` labels.

## Routine control

Routine chat-driven operations are triggered by adding exactly one JSON file under `requests/`. The self-hosted workflow validates that HEAD changed exactly one request JSON, validates the command allowlist and exact scientific commit SHA, and then executes only fixed argv-based operations.

Scientific worker requests are capped at 44 for the current 48-vCPU server profile. Values above 44 are rejected before benchmark execution.

See `docs/RUNNER_OPERATIONS.md` for bootstrap, service, firewall, and removal procedures.
