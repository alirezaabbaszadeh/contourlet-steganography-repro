"""Durable, content-addressed execution primitives for research workloads.

The cache object is the source of truth.  Human-readable run state is rebuilt
from validated objects after an interruption, so a crash between committing an
object and updating ``state.json`` cannot cause the scientific work to repeat.
"""

from __future__ import annotations

from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import errno
import json
import multiprocessing
import os
from pathlib import Path
import re
import socket
import sys
from typing import Any, Callable, Iterator, Mapping, Sequence
import uuid

from .provenance import canonical_json_bytes, sha256_bytes, sha256_file, sha256_json


RUNTIME_SCHEMA = 1
_OBJECT_ID = re.compile(r"^[0-9a-f]{64}$")
_THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fsync_directory(path: Path) -> None:
    if os.name != "posix":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_bytes(path: str | Path, payload: bytes) -> None:
    """Write one file durably, then publish it with ``os.replace``."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        f".{destination.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
    )
    with temporary.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, destination)
    _fsync_directory(destination.parent)


def atomic_write_text(path: str | Path, payload: str) -> None:
    atomic_write_bytes(path, payload.encode("utf-8"))


def atomic_write_json(path: str | Path, payload: object) -> None:
    data = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    atomic_write_text(path, data + "\n")


def read_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def content_object_id(kind: str, material: Mapping[str, Any]) -> str:
    """Return the full SHA-256 address for one deterministic work unit."""

    if not kind or not kind.isascii():
        raise ValueError("content object kind must be non-empty ASCII")
    return sha256_json(
        {
            "runtime_schema": RUNTIME_SCHEMA,
            "kind": kind,
            "material": dict(material),
        }
    )


def _validated_object_id(object_id: str) -> str:
    if not _OBJECT_ID.fullmatch(object_id):
        raise ValueError("object_id must be a lowercase SHA-256 digest")
    return object_id


@dataclass(frozen=True)
class CacheVerification:
    object_id: str
    valid: bool
    reason: str | None
    path: Path
    file_count: int = 0
    byte_count: int = 0


class ContentStore:
    """Append-only object store with atomic directory publication."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        for child in ("objects", "attempts", "quarantine"):
            (self.root / child).mkdir(parents=True, exist_ok=True)

    def object_path(self, object_id: str) -> Path:
        digest = _validated_object_id(object_id)
        return self.root / "objects" / digest[:2] / digest[2:]

    def attempt_parent(self, object_id: str) -> Path:
        digest = _validated_object_id(object_id)
        return self.root / "attempts" / digest[:2] / digest[2:]

    def begin_attempt(self, object_id: str) -> Path:
        parent = self.attempt_parent(object_id)
        parent.mkdir(parents=True, exist_ok=True)
        attempt = parent / (
            f"{utc_now().replace(':', '').replace('-', '')}-"
            f"p{os.getpid()}-{uuid.uuid4().hex}"
        )
        attempt.mkdir()
        atomic_write_json(
            attempt / "ATTEMPT.json",
            {
                "schema": RUNTIME_SCHEMA,
                "object_id": object_id,
                "attempt_id": attempt.name,
                "started_at": utc_now(),
                "pid": os.getpid(),
                "host": socket.gethostname(),
            },
        )
        return attempt

    @staticmethod
    def _inventory(directory: Path) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(directory).as_posix()
            if relative in {"_inventory.json", "COMPLETED.json"}:
                continue
            records.append(
                {
                    "path": relative,
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        return records

    def verify(self, object_id: str, *, deep: bool = True) -> CacheVerification:
        path = self.object_path(object_id)
        if not path.is_dir():
            return CacheVerification(object_id, False, "object_missing", path)
        marker_path = path / "COMPLETED.json"
        inventory_path = path / "_inventory.json"
        if not marker_path.is_file() or not inventory_path.is_file():
            return CacheVerification(
                object_id,
                False,
                "completion_marker_or_inventory_missing",
                path,
            )
        try:
            marker = read_json(marker_path)
            inventory_payload = read_json(inventory_path)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            return CacheVerification(
                object_id,
                False,
                f"metadata_unreadable:{type(error).__name__}",
                path,
            )
        if marker.get("object_id") != object_id:
            return CacheVerification(object_id, False, "object_id_mismatch", path)
        if sha256_json(inventory_payload) != marker.get("inventory_sha256"):
            return CacheVerification(object_id, False, "inventory_hash_mismatch", path)
        records = inventory_payload.get("files")
        if not isinstance(records, list):
            return CacheVerification(object_id, False, "inventory_invalid", path)
        recorded_paths: list[str] = []
        for record in records:
            if not isinstance(record, dict):
                return CacheVerification(
                    object_id,
                    False,
                    "inventory_record_invalid",
                    path,
                )
            relative = record.get("path")
            if not isinstance(relative, str):
                return CacheVerification(
                    object_id,
                    False,
                    "inventory_path_invalid",
                    path,
                )
            candidate = (path / relative).resolve()
            try:
                candidate.relative_to(path.resolve())
            except ValueError:
                return CacheVerification(
                    object_id,
                    False,
                    "inventory_path_escape",
                    path,
                )
            recorded_paths.append(relative)
        if len(recorded_paths) != len(set(recorded_paths)):
            return CacheVerification(
                object_id,
                False,
                "inventory_duplicate_path",
                path,
            )
        actual_paths = {
            candidate.relative_to(path).as_posix()
            for candidate in path.rglob("*")
            if candidate.is_file()
            and candidate.name not in {"_inventory.json", "COMPLETED.json"}
        }
        if actual_paths != set(recorded_paths):
            return CacheVerification(
                object_id,
                False,
                "inventory_file_set_mismatch",
                path,
            )
        task_path = path / "task.json"
        if task_path.is_file():
            try:
                task_payload = read_json(task_path)
            except (OSError, UnicodeError, json.JSONDecodeError):
                return CacheVerification(
                    object_id,
                    False,
                    "task_metadata_unreadable",
                    path,
                )
            if sha256_json(task_payload) != marker.get("task_material_sha256"):
                return CacheVerification(
                    object_id,
                    False,
                    "task_material_hash_mismatch",
                    path,
                )
        byte_count = 0
        if deep:
            for record, relative in zip(records, recorded_paths, strict=True):
                candidate = (path / relative).resolve()
                if not candidate.is_file():
                    return CacheVerification(
                        object_id,
                        False,
                        f"file_missing:{relative}",
                        path,
                    )
                size = candidate.stat().st_size
                if size != record.get("size"):
                    return CacheVerification(
                        object_id,
                        False,
                        f"file_size_mismatch:{relative}",
                        path,
                    )
                if sha256_file(candidate) != record.get("sha256"):
                    return CacheVerification(
                        object_id,
                        False,
                        f"file_hash_mismatch:{relative}",
                        path,
                    )
                byte_count += size
        else:
            byte_count = sum(
                int(record.get("size", 0))
                for record in records
                if isinstance(record, dict)
            )
        return CacheVerification(
            object_id,
            True,
            None,
            path,
            file_count=len(records),
            byte_count=byte_count,
        )

    def _quarantine_invalid(self, object_id: str, reason: str) -> Path:
        source = self.object_path(object_id)
        destination = self.root / "quarantine" / (
            f"{object_id}-{utc_now().replace(':', '').replace('-', '')}-"
            f"{uuid.uuid4().hex}"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
        atomic_write_json(
            destination / "QUARANTINED.json",
            {
                "schema": RUNTIME_SCHEMA,
                "object_id": object_id,
                "reason": reason,
                "quarantined_at": utc_now(),
            },
        )
        _fsync_directory(destination.parent)
        return destination

    def commit_attempt(
        self,
        object_id: str,
        attempt: str | Path,
        *,
        task_material_sha256: str,
    ) -> CacheVerification:
        """Publish a complete attempt as an immutable cache object."""

        attempt_path = Path(attempt).resolve()
        expected_parent = self.attempt_parent(object_id).resolve()
        try:
            attempt_path.relative_to(expected_parent)
        except ValueError as error:
            raise ValueError("attempt is outside the object's attempt directory") from error
        existing = self.verify(object_id, deep=True)
        if existing.valid:
            atomic_write_json(
                attempt_path / "DUPLICATE.json",
                {
                    "schema": RUNTIME_SCHEMA,
                    "object_id": object_id,
                    "existing_path": str(existing.path),
                    "recorded_at": utc_now(),
                },
            )
            return existing
        if existing.path.exists():
            self._quarantine_invalid(
                object_id,
                existing.reason or "unknown_validation_failure",
            )

        files = self._inventory(attempt_path)
        inventory = {
            "schema": RUNTIME_SCHEMA,
            "object_id": object_id,
            "files": files,
        }
        atomic_write_json(attempt_path / "_inventory.json", inventory)
        marker = {
            "schema": RUNTIME_SCHEMA,
            "object_id": object_id,
            "task_material_sha256": task_material_sha256,
            "inventory_sha256": sha256_json(inventory),
            "completed_at": utc_now(),
            "file_count": len(files),
            "byte_count": sum(int(item["size"]) for item in files),
        }
        atomic_write_json(attempt_path / "COMPLETED.json", marker)
        destination = self.object_path(object_id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(attempt_path, destination)
        _fsync_directory(destination.parent)
        verification = self.verify(object_id, deep=True)
        if not verification.valid:
            raise RuntimeError(
                f"committed object failed validation: {verification.reason}"
            )
        return verification

    def record_failure(
        self,
        attempt: str | Path,
        *,
        object_id: str,
        error: BaseException,
        traceback_text: str,
    ) -> None:
        atomic_write_json(
            Path(attempt) / "FAILED.json",
            {
                "schema": RUNTIME_SCHEMA,
                "object_id": object_id,
                "failed_at": utc_now(),
                "error_type": type(error).__name__,
                "error": str(error),
                "traceback": traceback_text,
            },
        )


def _boot_id() -> str | None:
    path = Path("/proc/sys/kernel/random/boot_id")
    try:
        return path.read_text(encoding="ascii").strip()
    except OSError:
        return None


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as error:
        return error.errno == errno.EPERM
    return True


class RunLock:
    """Single-run lock that preserves stale and released lock evidence."""

    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir).resolve()
        self.lock_path = self.run_dir / "run.lock"
        self.token = uuid.uuid4().hex
        self.payload: dict[str, object] | None = None

    def _archive_existing(self, existing: Mapping[str, Any], reason: str) -> None:
        history = self.run_dir / "locks" / "stale"
        history.mkdir(parents=True, exist_ok=True)
        destination = history / (
            f"{utc_now().replace(':', '').replace('-', '')}-"
            f"{uuid.uuid4().hex}.json"
        )
        os.replace(self.lock_path, destination)
        payload = dict(existing)
        payload.update({"archived_at": utc_now(), "archive_reason": reason})
        atomic_write_json(destination, payload)

    def acquire(self) -> "RunLock":
        self.run_dir.mkdir(parents=True, exist_ok=True)
        if self.lock_path.exists():
            try:
                existing = read_json(self.lock_path)
            except (OSError, UnicodeError, json.JSONDecodeError):
                existing = {}
            same_host = existing.get("host") == socket.gethostname()
            same_boot = existing.get("boot_id") == _boot_id()
            pid = existing.get("pid")
            if (
                same_host
                and same_boot
                and isinstance(pid, int)
                and _pid_is_alive(pid)
            ):
                raise RuntimeError(
                    f"run is already active as pid {pid} on {existing.get('host')}"
                )
            self._archive_existing(existing, "owner_not_alive_or_previous_boot")

        payload = {
            "schema": RUNTIME_SCHEMA,
            "token": self.token,
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "boot_id": _boot_id(),
            "python": sys.version,
            "acquired_at": utc_now(),
        }
        encoded = (
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
        ).encode("utf-8")
        descriptor = os.open(
            self.lock_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            os.write(descriptor, encoded)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        _fsync_directory(self.run_dir)
        self.payload = payload
        return self

    def release(self) -> None:
        if self.payload is None or not self.lock_path.exists():
            return
        try:
            current = read_json(self.lock_path)
        except (OSError, UnicodeError, json.JSONDecodeError):
            return
        if current.get("token") != self.token:
            raise RuntimeError("run lock ownership changed before release")
        history = self.run_dir / "locks" / "released"
        history.mkdir(parents=True, exist_ok=True)
        destination = history / (
            f"{utc_now().replace(':', '').replace('-', '')}-"
            f"{self.token}.json"
        )
        os.replace(self.lock_path, destination)
        current.update({"released_at": utc_now()})
        atomic_write_json(destination, current)
        self.payload = None

    def __enter__(self) -> "RunLock":
        return self.acquire()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()


def _system_available_memory() -> int | None:
    if not hasattr(os, "sysconf"):
        return None
    try:
        pages = int(os.sysconf("SC_AVPHYS_PAGES"))
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError):
        return None
    return pages * page_size


def _cgroup_available_memory() -> int | None:
    maximum_path = Path("/sys/fs/cgroup/memory.max")
    current_path = Path("/sys/fs/cgroup/memory.current")
    try:
        maximum_raw = maximum_path.read_text(encoding="ascii").strip()
        if maximum_raw == "max":
            return None
        maximum = int(maximum_raw)
        current = int(current_path.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return None
    return max(0, maximum - current)


def available_memory_bytes() -> int | None:
    candidates = [
        value
        for value in (_system_available_memory(), _cgroup_available_memory())
        if value is not None
    ]
    return min(candidates) if candidates else None


def resolve_worker_count(
    requested: int,
    *,
    job_count: int,
    reserve_cpus: int = 4,
    reserve_memory_gib: float = 12.0,
    worker_memory_gib: float = 3.0,
    hard_cap: int = 16,
) -> tuple[int, dict[str, object]]:
    """Resolve a bounded worker count from CPU and available-memory limits."""

    if requested < 0:
        raise ValueError("workers must be zero (auto) or positive")
    if job_count < 1:
        raise ValueError("job_count must be positive")
    if reserve_cpus < 0 or reserve_memory_gib < 0 or worker_memory_gib <= 0:
        raise ValueError("worker resource reservations are invalid")
    if hard_cap < 1:
        raise ValueError("hard_cap must be positive")
    cpu_total = os.cpu_count() or 1
    cpu_limit = max(1, cpu_total - reserve_cpus)
    available = available_memory_bytes()
    memory_limit: int | None = None
    if available is not None:
        reserve = int(reserve_memory_gib * 1024**3)
        per_worker = int(worker_memory_gib * 1024**3)
        memory_limit = max(0, (available - reserve) // per_worker)
    auto_limit = min(
        job_count,
        hard_cap,
        cpu_limit,
        memory_limit if memory_limit is not None else hard_cap,
    )
    resolved = auto_limit if requested == 0 else requested
    maximum = min(
        job_count,
        hard_cap,
        cpu_limit,
        memory_limit if memory_limit is not None else hard_cap,
    )
    if maximum < 1:
        raise ValueError(
            "safe worker bound is zero after CPU/RAM reservations; "
            "free memory or lower the reservations"
        )
    if resolved > maximum:
        raise ValueError(
            f"requested {resolved} workers, but the safe bound is {maximum}"
        )
    facts = {
        "requested": requested,
        "resolved": resolved,
        "cpu_total": cpu_total,
        "cpu_reserve": reserve_cpus,
        "cpu_limit": cpu_limit,
        "available_memory_bytes": available,
        "memory_reserve_gib": reserve_memory_gib,
        "estimated_worker_memory_gib": worker_memory_gib,
        "memory_limit": memory_limit,
        "hard_cap": hard_cap,
        "job_count": job_count,
    }
    return resolved, facts


@contextmanager
def single_threaded_worker_environment() -> Iterator[None]:
    """Prevent nested BLAS/OpenMP parallelism in spawned workers."""

    previous = {name: os.environ.get(name) for name in _THREAD_VARIABLES}
    try:
        for name in _THREAD_VARIABLES:
            os.environ[name] = "1"
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@dataclass(frozen=True)
class DurableTask:
    object_id: str
    kind: str
    label: str
    payload: Mapping[str, Any]

    def to_dict(self) -> dict[str, object]:
        _validated_object_id(self.object_id)
        return {
            "schema": RUNTIME_SCHEMA,
            "object_id": self.object_id,
            "kind": self.kind,
            "label": self.label,
            "payload": dict(self.payload),
        }


WorkerFunction = Callable[[Mapping[str, Any], str], Mapping[str, Any]]


class DurableTaskRunner:
    """Execute independent content tasks while checkpointing every completion."""

    def __init__(
        self,
        *,
        cache_dir: str | Path,
        run_dir: str | Path,
        workers: int,
    ):
        if workers < 1:
            raise ValueError("workers must be positive")
        self.cache_dir = Path(cache_dir).resolve()
        self.run_dir = Path(run_dir).resolve()
        self.workers = workers
        self.store = ContentStore(self.cache_dir)
        self.state_path = self.run_dir / "state.json"
        self.events_dir = self.run_dir / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)

    def _event(self, event: Mapping[str, Any]) -> None:
        existing = sorted(self.events_dir.glob("*.json"))
        sequence = len(existing) + 1
        atomic_write_json(
            self.events_dir / f"{sequence:06d}-{uuid.uuid4().hex}.json",
            {
                "schema": RUNTIME_SCHEMA,
                "sequence": sequence,
                "recorded_at": utc_now(),
                **dict(event),
            },
        )

    def _load_state(self) -> dict[str, Any]:
        if self.state_path.is_file():
            try:
                state = read_json(self.state_path)
            except (OSError, UnicodeError, json.JSONDecodeError):
                state = {}
        else:
            state = {}
        if not isinstance(state, dict):
            state = {}
        state.setdefault("schema", RUNTIME_SCHEMA)
        state.setdefault("created_at", utc_now())
        state.setdefault("stages", {})
        return state

    def _write_stage_state(
        self,
        state: dict[str, Any],
        *,
        stage: str,
        records: Mapping[str, Mapping[str, Any]],
        status: str,
    ) -> None:
        state["updated_at"] = utc_now()
        state["stages"][stage] = {
            "status": status,
            "workers": self.workers,
            "tasks": dict(records),
            "counts": {
                item_status: sum(
                    1
                    for record in records.values()
                    if record.get("status") == item_status
                )
                for item_status in ("cached", "completed", "failed", "pending")
            },
        }
        atomic_write_json(self.state_path, state)

    def run(
        self,
        tasks: Sequence[DurableTask],
        *,
        stage: str,
        worker: WorkerFunction,
    ) -> dict[str, Any]:
        if not tasks:
            raise ValueError("durable task stage must not be empty")
        identifiers = [task.object_id for task in tasks]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("durable task stage contains duplicate object ids")
        state = self._load_state()
        records: dict[str, dict[str, Any]] = {}
        pending: list[DurableTask] = []
        for task in tasks:
            verification = self.store.verify(task.object_id, deep=True)
            if verification.valid:
                records[task.object_id] = {
                    "label": task.label,
                    "kind": task.kind,
                    "status": "cached",
                    "path": str(verification.path),
                    "bytes": verification.byte_count,
                }
            else:
                records[task.object_id] = {
                    "label": task.label,
                    "kind": task.kind,
                    "status": "pending",
                    "cache_validation": verification.reason,
                }
                pending.append(task)
        self._write_stage_state(
            state,
            stage=stage,
            records=records,
            status="running" if pending else "complete",
        )
        self._event(
            {
                "event": "stage_started",
                "stage": stage,
                "task_count": len(tasks),
                "cache_hits": len(tasks) - len(pending),
                "pending": len(pending),
            }
        )
        if not pending:
            return {
                "stage": stage,
                "task_count": len(tasks),
                "cached": len(tasks),
                "completed": 0,
                "failed": 0,
                "records": records,
            }

        context = multiprocessing.get_context("spawn")
        executor = ProcessPoolExecutor(
            max_workers=min(self.workers, len(pending)),
            mp_context=context,
        )
        futures: dict[Future[Mapping[str, Any]], DurableTask] = {}
        try:
            with single_threaded_worker_environment():
                for task in pending:
                    futures[
                        executor.submit(worker, task.to_dict(), str(self.cache_dir))
                    ] = task
            for future in as_completed(futures):
                task = futures[future]
                try:
                    result = dict(future.result())
                except BaseException as error:
                    result = {
                        "status": "failed",
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }
                task_status = str(result.get("status", "failed"))
                if task_status not in {"completed", "cached", "failed"}:
                    task_status = "failed"
                records[task.object_id] = {
                    "label": task.label,
                    "kind": task.kind,
                    "status": task_status,
                    **result,
                }
                self._write_stage_state(
                    state,
                    stage=stage,
                    records=records,
                    status="running",
                )
                self._event(
                    {
                        "event": "task_finished",
                        "stage": stage,
                        "object_id": task.object_id,
                        "label": task.label,
                        "status": task_status,
                    }
                )
        except BaseException:
            for future in futures:
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            self._write_stage_state(
                state,
                stage=stage,
                records=records,
                status="interrupted",
            )
            self._event({"event": "stage_interrupted", "stage": stage})
            raise
        else:
            executor.shutdown(wait=True)

        failed = sum(record.get("status") == "failed" for record in records.values())
        final_status = "failed" if failed else "complete"
        self._write_stage_state(
            state,
            stage=stage,
            records=records,
            status=final_status,
        )
        self._event(
            {
                "event": "stage_finished",
                "stage": stage,
                "status": final_status,
                "failed": failed,
            }
        )
        return {
            "stage": stage,
            "task_count": len(tasks),
            "cached": sum(
                record.get("status") == "cached" for record in records.values()
            ),
            "completed": sum(
                record.get("status") == "completed" for record in records.values()
            ),
            "failed": failed,
            "records": records,
        }


def task_material_sha256(task: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(dict(task)))
