"""Persistent governance for classifying V2 shadow divergences.

Classification is advisory only; V1.4.1 remains authoritative.
"""
from __future__ import annotations
import json, threading, uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUSES = ("EQUIVALENT", "INTENTIONAL_DIFFERENCE", "POLICY_QUESTION", "V2_DEFECT", "NOT_YET_MIGRATABLE")

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class ShadowClassification:
    classification_id: str
    result_id: str
    row_index: int
    field: str
    status: str = "NOT_YET_MIGRATABLE"
    rationale: str = ""
    owner: str = ""
    updated_at: str = field(default_factory=_now)

    def public(self) -> dict[str, Any]:
        return asdict(self)

class ShadowMigrationStore:
    def __init__(self, state_path: Path | None = None):
        self.state_path = state_path or Path(__file__).resolve().parent / "runtime" / "shadow_migration.json"
        self._lock = threading.RLock()
        self._items: dict[str, ShadowClassification] = {}
        self._load()

    def _load(self):
        if not self.state_path.exists(): return
        try:
            for item in json.loads(self.state_path.read_text(encoding="utf-8")):
                record = ShadowClassification(**item)
                self._items[record.classification_id] = record
        except (OSError, ValueError, TypeError):
            self._items = {}

    def _persist(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps([x.public() for x in self._items.values()], indent=2), encoding="utf-8")
        tmp.replace(self.state_path)

    def upsert(self, result_id: str, row_index: int, field: str, status: str, rationale: str = "", owner: str = "") -> ShadowClassification:
        if status not in STATUSES: raise ValueError(f"Unsupported shadow classification: {status}")
        key = f"{result_id}:{row_index}:{field}"
        with self._lock:
            existing = next((x for x in self._items.values() if f"{x.result_id}:{x.row_index}:{x.field}" == key), None)
            record = existing or ShadowClassification("SHD-" + uuid.uuid4().hex[:12].upper(), result_id, row_index, field)
            record.status, record.rationale, record.owner, record.updated_at = status, rationale, owner, _now()
            self._items[record.classification_id] = record
            self._persist()
            return record

    def for_result(self, result_id: str) -> list[ShadowClassification]:
        with self._lock:
            return [x for x in self._items.values() if x.result_id == result_id]

    def summary(self, result_id: str) -> dict[str, Any]:
        items = self.for_result(result_id)
        counts = {status: sum(x.status == status for x in items) for status in STATUSES}
        return {"result_id": result_id, "counts": counts, "classifications": [x.public() for x in items]}
