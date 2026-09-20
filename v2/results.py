"""Persistent V2 result records.

The result store is an application-layer envelope around the protected
V1.4.1 engine output. It deliberately does not reinterpret or mutate the
golden engine's business decisions.
"""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ResultRecord:
    result_id: str
    job_id: str
    operation: str
    actor: str
    status: str
    created_at: str = field(default_factory=_now)
    completed_at: str | None = None
    inputs: dict[str, str] = field(default_factory=dict)
    summary: Any = None
    evidence_ids: list[str] = field(default_factory=list)
    exception_ids: list[str] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return asdict(self)


class ResultStore:
    def __init__(self, state_path: Path | None = None):
        self.state_path = state_path or (
            Path(__file__).resolve().parent / "runtime" / "results.json"
        )
        self._lock = threading.RLock()
        self._results: dict[str, ResultRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            for item in data:
                record = ResultRecord(**item)
                self._results[record.result_id] = record
        except (OSError, ValueError, TypeError):
            self._results = {}

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([x.public() for x in self._results.values()], indent=2, default=str),
            encoding="utf-8",
        )
        tmp.replace(self.state_path)

    def create(
        self,
        job_id: str,
        operation: str,
        actor: str,
        inputs: dict[str, str] | None = None,
    ) -> ResultRecord:
        record = ResultRecord(
            result_id="RES-" + uuid.uuid4().hex[:12].upper(),
            job_id=job_id,
            operation=operation,
            actor=actor,
            status="RUNNING",
            inputs=dict(inputs or {}),
        )
        with self._lock:
            self._results[record.result_id] = record
            self._persist()
        return record

    def complete(
        self,
        result_id: str,
        summary: Any,
        completed_at: str | None = None,
        evidence_ids: list[str] | None = None,
        exception_ids: list[str] | None = None,
    ) -> ResultRecord:
        with self._lock:
            record = self._results[result_id]
            record.status = "COMPLETED"
            record.completed_at = completed_at or _now()
            record.summary = summary
            record.evidence_ids = list(evidence_ids or [])
            record.exception_ids = list(exception_ids or [])
            self._persist()
            return record

    def fail(self, result_id: str, summary: Any = None) -> ResultRecord:
        with self._lock:
            record = self._results[result_id]
            record.status = "FAILED"
            record.completed_at = _now()
            record.summary = summary
            self._persist()
            return record

    def get(self, result_id: str) -> ResultRecord | None:
        with self._lock:
            return self._results.get(result_id)

    def for_job(self, job_id: str) -> ResultRecord | None:
        with self._lock:
            matches = [x for x in self._results.values() if x.job_id == job_id]
            return sorted(matches, key=lambda x: x.created_at, reverse=True)[0] if matches else None

    def list(self) -> list[ResultRecord]:
        with self._lock:
            return sorted(self._results.values(), key=lambda x: x.created_at, reverse=True)
