"""Persistent governance exception records.

Exceptions are explicit human-review items. This layer does not reinterpret
V1.4.1 decisions; it records governed findings and their required disposition.
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
class ExceptionRecord:
    exception_id: str
    result_id: str
    code: str
    title: str
    description: str
    severity: str = "REVIEW"
    status: str = "OPEN"
    recommendation: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    candidate_id: str | None = None
    candidate: dict[str, Any] = field(default_factory=dict)
    decision: str | None = None
    created_at: str = field(default_factory=_now)
    resolved_at: str | None = None
    resolved_by: str | None = None
    resolution: str | None = None

    def public(self) -> dict[str, Any]:
        return asdict(self)


class ExceptionStore:
    def __init__(self, state_path: Path | None = None):
        self.state_path = state_path or Path(__file__).resolve().parent / "runtime" / "exceptions.json"
        self._lock = threading.RLock()
        self._items: dict[str, ExceptionRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            for item in json.loads(self.state_path.read_text(encoding="utf-8")):
                # Backward compatible with exception records created before
                # candidate-level approval was introduced.
                item.setdefault("candidate_id", None)
                item.setdefault("candidate", {})
                item.setdefault("decision", None)
                record = ExceptionRecord(**item)
                self._items[record.exception_id] = record
        except (OSError, ValueError, TypeError):
            self._items = {}

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps([x.public() for x in self._items.values()], indent=2, default=str), encoding="utf-8")
        tmp.replace(self.state_path)

    def create(
        self,
        result_id: str,
        code: str,
        title: str,
        description: str,
        *,
        severity: str = "REVIEW",
        recommendation: str = "",
        evidence_ids: list[str] | None = None,
        candidate_id: str | None = None,
        candidate: dict[str, Any] | None = None,
    ) -> ExceptionRecord:
        record = ExceptionRecord(
            exception_id="EXC-" + uuid.uuid4().hex[:12].upper(),
            result_id=result_id,
            code=code,
            title=title,
            description=description,
            severity=severity,
            recommendation=recommendation,
            evidence_ids=list(evidence_ids or []),
            candidate_id=candidate_id,
            candidate=dict(candidate or {}),
        )
        with self._lock:
            self._items[record.exception_id] = record
            self._persist()
        return record

    def resolve(self, exception_id: str, actor: str, resolution: str, decision: str = "APPROVE") -> ExceptionRecord:
        decision = str(decision).upper()
        if decision not in {"APPROVE", "REJECT"}:
            raise ValueError("decision must be APPROVE or REJECT")
        with self._lock:
            record = self._items[exception_id]
            record.status = "RESOLVED"
            record.decision = decision
            record.resolved_at = _now()
            record.resolved_by = actor
            record.resolution = resolution
            self._persist()
            return record

    def get(self, exception_id: str) -> ExceptionRecord | None:
        return self._items.get(exception_id)

    def for_result(self, result_id: str) -> list[ExceptionRecord]:
        return [x for x in self._items.values() if x.result_id == result_id]

    def list(self) -> list[ExceptionRecord]:
        return sorted(self._items.values(), key=lambda x: x.created_at, reverse=True)
