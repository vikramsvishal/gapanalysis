"""Immutable evidence/provenance records for governed executions."""
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


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    result_id: str
    kind: str
    source_type: str
    source_id: str
    source_name: str
    sha256: str
    captured_at: str = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceStore:
    """Append-only evidence registry.

    Existing records are never updated or deleted by this application layer.
    """

    def __init__(self, state_path: Path | None = None):
        self.state_path = state_path or Path(__file__).resolve().parent / "runtime" / "evidence.json"
        self._lock = threading.RLock()
        self._records: dict[str, EvidenceRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            for item in data:
                record = EvidenceRecord(**item)
                self._records[record.evidence_id] = record
        except (OSError, ValueError, TypeError):
            self._records = {}

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps([x.public() for x in self._records.values()], indent=2, default=str), encoding="utf-8")
        tmp.replace(self.state_path)

    def capture_resource(self, result_id: str, resource: Any) -> EvidenceRecord:
        """Capture provenance from an existing ResourceRecord without copying the file."""
        evidence = EvidenceRecord(
            evidence_id="EVD-" + uuid.uuid4().hex[:12].upper(),
            result_id=result_id,
            kind=resource.kind,
            source_type="RESOURCE",
            source_id=resource.resource_id,
            source_name=resource.file_name,
            sha256=resource.sha256,
            metadata={"size": resource.size, "status": resource.status},
        )
        with self._lock:
            self._records[evidence.evidence_id] = evidence
            self._persist()
        return evidence

    def capture_text(self, result_id: str, kind: str, source_id: str, source_name: str, value: str) -> EvidenceRecord:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        evidence = EvidenceRecord(
            evidence_id="EVD-" + uuid.uuid4().hex[:12].upper(),
            result_id=result_id,
            kind=kind,
            source_type="TEXT",
            source_id=source_id,
            source_name=source_name,
            sha256=digest,
            metadata={"length": len(value)},
        )
        with self._lock:
            self._records[evidence.evidence_id] = evidence
            self._persist()
        return evidence

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        return self._records.get(evidence_id)

    def for_result(self, result_id: str) -> list[EvidenceRecord]:
        return [x for x in self._records.values() if x.result_id == result_id]

    def list(self) -> list[EvidenceRecord]:
        return sorted(self._records.values(), key=lambda x: x.captured_at, reverse=True)
