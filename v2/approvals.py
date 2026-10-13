"""Persistent approval packages for governed OS bulk-load candidates.

The approval store is deliberately separate from V1.4.1. It controls lifecycle
and human disposition; it does not reinterpret golden-engine decisions.
"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def candidate_id(domain: str, row_index: Any, candidate: dict[str, Any]) -> str:
    payload = json.dumps(
        {"domain": domain, "row_index": str(row_index), "candidate": candidate},
        sort_keys=True,
        default=str,
    )
    return "CAND-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16].upper()


@dataclass
class ApprovalRecord:
    approval_id: str
    result_id: str
    operation: str
    domain: str
    actor: str
    resource_inputs: dict[str, str] = field(default_factory=dict)
    candidate_count: int = 0
    review_candidate_ids: list[str] = field(default_factory=list)
    status: str = "PENDING_REVIEW"
    created_at: str = field(default_factory=_now)
    completed_at: str | None = None
    finalized_by: str | None = None
    final_result: dict[str, Any] | None = None
    candidate_snapshot_sha256: str = ""
    decision_snapshot_sha256: str = ""
    output_sha256: dict[str, str] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return asdict(self)


class ApprovalStore:
    def __init__(self, state_path: Path | None = None):
        self.state_path = state_path or Path(__file__).resolve().parent / "runtime" / "approvals.json"
        self._lock = threading.RLock()
        self._items: dict[str, ApprovalRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            for item in json.loads(self.state_path.read_text(encoding="utf-8")):
                record = ApprovalRecord(**item)
                self._items[record.approval_id] = record
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
        domain: str,
        actor: str,
        resource_inputs: dict[str, str],
        candidate_count: int,
        review_candidate_ids: list[str],
        candidate_snapshot_sha256: str = "",
    ) -> ApprovalRecord:
        record = ApprovalRecord(
            approval_id="APR-" + uuid.uuid4().hex[:12].upper(),
            result_id=result_id,
            operation="generate_bulk_load",
            domain=domain,
            actor=actor,
            resource_inputs=dict(resource_inputs),
            candidate_count=int(candidate_count),
            review_candidate_ids=list(review_candidate_ids),
            candidate_snapshot_sha256=candidate_snapshot_sha256,
        )
        with self._lock:
            self._items[record.approval_id] = record
            self._persist()
        return record

    def get(self, approval_id: str) -> ApprovalRecord | None:
        with self._lock:
            return self._items.get(approval_id)

    def for_result(self, result_id: str) -> ApprovalRecord | None:
        with self._lock:
            matches = [x for x in self._items.values() if x.result_id == result_id]
            return sorted(matches, key=lambda x: x.created_at, reverse=True)[0] if matches else None

    def list(self) -> list[ApprovalRecord]:
        with self._lock:
            return sorted(self._items.values(), key=lambda x: x.created_at, reverse=True)

    def finalize(
        self,
        approval_id: str,
        actor: str,
        final_result: dict[str, Any],
        decision_snapshot_sha256: str = "",
        output_sha256: dict[str, str] | None = None,
    ) -> ApprovalRecord:
        with self._lock:
            record = self._items[approval_id]
            record.status = "FINALIZED"
            record.completed_at = _now()
            record.finalized_by = actor
            record.final_result = dict(final_result)
            record.decision_snapshot_sha256 = decision_snapshot_sha256
            record.output_sha256 = dict(output_sha256 or {})
            self._persist()
            return record
