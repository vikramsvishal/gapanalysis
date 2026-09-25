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
import hashlib
import json

import pandas as pd

from .approvals import ApprovalStore


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
    def __init__(self, service: Any, state_path: Path | None = None, result_store: Any | None = None, exception_store: Any | None = None, audit_store: Any | None = None, approval_store: ApprovalStore | None = None, execution_router: Any | None = None):
        self.service = service
        self.result_store = result_store
        self.exception_store = exception_store
        self.audit_store = audit_store
        self.approval_store = approval_store
        self.execution_router = execution_router
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
            shadow = None
            if self.execution_router is not None:
                route = self.execution_router.route(operation, payload)
                result = self.execution_router.execute(operation, payload, progress=progress)
                # Runtime shadowing: V1.4.1 remains authoritative while the
                # registered V2 executor evaluates the exact same resource inputs.
                if route.engine == "V1.4.1" and route.capability in self.execution_router.v2_executors:
                    try:
                        v2_result = self.execution_router.v2_executors[route.capability](
                            operation, payload, progress=progress
                        )
                        if isinstance(result, pd.DataFrame) and isinstance(v2_result, pd.DataFrame):
                            differences = []
                            columns = sorted(set(result.columns) | set(v2_result.columns))
                            max_rows = max(len(result), len(v2_result))
                            for row_index in range(max_rows):
                                row_diff = {}
                                for column in columns:
                                    golden_value = result.iloc[row_index][column] if row_index < len(result) and column in result.columns else None
                                    v2_value = v2_result.iloc[row_index][column] if row_index < len(v2_result) and column in v2_result.columns else None
                                    if pd.isna(golden_value) and pd.isna(v2_value):
                                        continue
                                    if str(golden_value) != str(v2_value):
                                        row_diff[column] = {"golden": str(golden_value), "v2": str(v2_value)}
                                if row_diff:
                                    serial = ""
                                    if row_index < len(result):
                                        for candidate in ("Serial Number", "serial_number", "Serial"):
                                            if candidate in result.columns:
                                                serial = str(result.iloc[row_index][candidate])
                                                break
                                    differences.append({"row_index": row_index, "serial_number": serial, "differences": row_diff})
                            shadow = {
                                "enabled": True,
                                "authoritative_engine": "V1.4.1",
                                "candidate_engine": "V2",
                                "row_count": max_rows,
                                "match_count": max_rows - len(differences),
                                "mismatch_count": len(differences),
                                "mismatches": differences[:500],
                            }
                        else:
                            shadow = {
                                "enabled": True,
                                "authoritative_engine": "V1.4.1",
                                "candidate_engine": "V2",
                                "status": "INCOMPARABLE_RESULT_TYPE",
                                "golden_type": type(result).__name__,
                                "v2_type": type(v2_result).__name__,
                            }
                    except Exception as shadow_exc:
                        shadow = {
                            "enabled": True,
                            "authoritative_engine": "V1.4.1",
                            "candidate_engine": "V2",
                            "status": "SHADOW_EXECUTION_FAILED",
                            "error": f"{type(shadow_exc).__name__}: {shadow_exc}",
                        }
            else:
                result = self.service.execute_operation(operation, payload, progress=progress)
            if isinstance(result, dict) and shadow is not None:
                result = dict(result)
                result["shadow"] = shadow
            shadow_evidence = None
            if result_record is not None and shadow and shadow.get("enabled"):
                shadow_payload = json.dumps(shadow, sort_keys=True, separators=(",", ":"), default=str)
                shadow_evidence = self.result_store.evidence_store.capture_text(
                    result_record.result_id,
                    "HARDWARE_GOVERNANCE_SHADOW",
                    result_record.result_id,
                    result_record.result_id + "-hardware-shadow.json",
                    shadow_payload,
                ) if getattr(self.result_store, "evidence_store", None) is not None else None
                if shadow_evidence is not None:
                    evidence_records.append(shadow_evidence)
                if self.audit_store is not None:
                    self.audit_store.append(
                        "SHADOW_ANALYSIS", self._jobs[job_id].actor, "RESULT",
                        result_record.result_id, "COMPLETED",
                        {
                            "authoritative_engine": shadow.get("authoritative_engine"),
                            "row_count": shadow.get("row_count"),
                            "match_count": shadow.get("match_count"),
                            "mismatch_count": shadow.get("mismatch_count"),
                            "evidence_id": shadow_evidence.evidence_id if shadow_evidence else None,
                        },
                    )
            exception_ids = []
            candidates = result.get("exception_candidates", []) if isinstance(result, dict) else []
            if result_record is not None and self.exception_store is not None:
                for candidate in candidates:
                    exc = self.exception_store.create(
                        result_record.result_id,
                        candidate["code"],
                        candidate["title"],
                        candidate["description"],
                        severity=candidate.get("severity", "REVIEW"),
                        recommendation=candidate.get("recommendation", ""),
                        evidence_ids=[x.evidence_id for x in evidence_records],
                        candidate_id=candidate.get("candidate_id"),
                        candidate=candidate.get("candidate") or {},
                    )
                    exception_ids.append(exc.exception_id)
                    if self.audit_store is not None:
                        self.audit_store.append(
                            "EXCEPTION", self._jobs[job_id].actor, "EXCEPTION", exc.exception_id,
                            "OPENED", {
                                "result_id": result_record.result_id,
                                "code": exc.code,
                                "candidate_id": exc.candidate_id,
                            },
                        )

            if candidates and self.approval_store is not None and result_record is not None:
                candidate_payload = json.dumps(candidates, sort_keys=True, separators=(",", ":"), default=str)
                candidate_sha = hashlib.sha256(candidate_payload.encode("utf-8")).hexdigest()
                approval = self.approval_store.create(
                    result_record.result_id,
                    str(result.get("domain", "")),
                    self._jobs[job_id].actor,
                    payload.get("resources") or {},
                    int(result.get("candidate_count", 0)),
                    [str(x.get("candidate_id")) for x in candidates if x.get("candidate_id")],
                    candidate_snapshot_sha256=candidate_sha,
                )
                result = dict(result)
                result["approval_id"] = approval.approval_id
                if self.audit_store is not None:
                    self.audit_store.append(
                        "APPROVAL", self._jobs[job_id].actor, "APPROVAL", approval.approval_id,
                        "CREATED", {
                            "result_id": result_record.result_id,
                            "candidate_count": approval.candidate_count,
                            "review_candidate_count": len(approval.review_candidate_ids),
                        },
                    )
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
                    exception_ids=exception_ids,
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
