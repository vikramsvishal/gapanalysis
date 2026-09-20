"""Local job orchestration for the V2 enterprise edition.

Jobs are intentionally transport-agnostic. The first implementation uses an
in-process worker and JSON state so the local edition has a real lifecycle
without introducing a server/database prerequisite.
"""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_summary(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _safe_summary(v) for k, v in list(value.items())[:100]}
    if isinstance(value, (list, tuple)):
        return [_safe_summary(v) for v in value[:100]]
    # pandas objects expose useful shape/columns without serializing the payload.
    shape = getattr(value, "shape", None)
    columns = getattr(value, "columns", None)
    if shape is not None:
        return {
            "type": type(value).__name__,
            "shape": list(shape),
            "columns": [str(x) for x in list(columns)[:100]] if columns is not None else [],
        }
    return {"type": type(value).__name__, "repr": str(value)[:500]}


@dataclass
class JobRecord:
    job_id: str
    operation: str
    actor: str
    status: str = "QUEUED"
    progress: int = 0
    message: str = "Queued"
    created_at: str = field(default_factory=_now)
    started_at: str | None = None
    completed_at: str | None = None
    result: Any = None
    error: str | None = None

    def public(self) -> dict[str, Any]:
        return asdict(self)


class JobManager:
    def __init__(self, service: Any, state_path: Path | None = None, result_store: Any | None = None):
        self.service = service
        self.result_store = result_store
        self.state_path = state_path or (
            Path(__file__).resolve().parent / "runtime" / "jobs.json"
        )
        self._lock = threading.RLock()
        self._jobs: dict[str, JobRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            for item in data:
                record = JobRecord(**item)
                if record.status in {"RUNNING", "QUEUED"}:
                    record.status = "INTERRUPTED"
                    record.message = "Process restarted before job completion"
                self._jobs[record.job_id] = record
        except (OSError, ValueError, TypeError):
            # Corrupt runtime state must never prevent the application starting.
            self._jobs = {}

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        payload = [job.public() for job in self._jobs.values()]
        tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.state_path)

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)
            self._persist()

    def create(self, operation: str, payload: dict[str, Any] | None = None, actor: str = "local-user") -> JobRecord:
        job_id = "JOB-" + uuid.uuid4().hex[:12].upper()
        job = JobRecord(job_id=job_id, operation=operation, actor=actor)
        with self._lock:
            self._jobs[job_id] = job
            self._persist()
        threading.Thread(
            target=self._execute,
            args=(job_id, operation, payload or {}),
            name=f"gov-{job_id}",
            daemon=True,
        ).start()
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[JobRecord]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda x: x.created_at, reverse=True)

    def _execute(self, job_id: str, operation: str, payload: dict[str, Any]) -> None:
        self._update(job_id, status="RUNNING", progress=1, message="Starting", started_at=_now())
        result_record = None
        evidence_records = []
        try:
            if self.result_store is not None:
                result_record = self.result_store.create(job_id, operation, self._jobs[job_id].actor, (payload.get("resources") or {}))
                evidence_store = getattr(self.result_store, "evidence_store", None)
                resources = getattr(self.service, "resources", None)
                if evidence_store is not None and resources is not None:
                    for resource_id in (payload.get("resources") or {}).values():
                        resource = resources.get(resource_id)
                        if resource is not None:
                            evidence_records.append(evidence_store.capture_resource(result_record.result_id, resource))
            progress = lambda message, percent=0: self._update(
                job_id, progress=max(1, min(99, int(percent))), message=str(message)
            )
            result = self.service.execute_operation(operation, payload, progress=progress)
            self._update(
                job_id,
                status="COMPLETED",
                progress=100,
                message="Completed",
                completed_at=_now(),
                result=_safe_summary(result),
            )
            if result_record is not None:
                self.result_store.complete(
                    result_record.result_id,
                    _safe_summary(result),
                    evidence_ids=[x.evidence_id for x in evidence_records],
                    exception_ids=[],
                )
        except Exception as exc:  # job failures must be visible, not crash the API
            self._update(
                job_id,
                status="FAILED",
                progress=100,
                message="Execution failed",
                completed_at=_now(),
                error=f"{type(exc).__name__}: {exc}",
            )
            if result_record is not None:
                self.result_store.fail(
                    result_record.result_id,
                    {"error": f"{type(exc).__name__}: {exc}"},
                )
