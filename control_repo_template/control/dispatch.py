from __future__ import annotations

from pathlib import Path

from control.request import ControlRequest


CONTROL_CONFIG = "/etc/ctsteg-control.json"


def build_operation(request: ControlRequest, checkout: str) -> list[str]:
    argv = [
        "python3",
        "-m",
        "control.operations",
        request.command,
        "--checkout",
        str(Path(checkout)),
        "--config",
        CONTROL_CONFIG,
    ]
    if request.command == "worker_benchmark":
        if request.workers is None:
            raise AssertionError("validated worker benchmark is missing workers")
        argv.extend(["--workers", str(request.workers)])
    return argv
