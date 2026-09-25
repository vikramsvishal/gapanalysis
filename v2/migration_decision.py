"""Immutable authority-review decisions for migration evidence packs."""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DECISIONS = ("APPROVE_AUTHORITY_REVIEW", "REJECT", "DEFER")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass(frozen=True)
class MigrationDecisionRecord:
    decision_id: str
    package_id: str
    capability: str | None
    decision: str
    actor: str
    rationale: str
    decided_at: str
    package_manifest_sha256: str
    decision_sha256: str
    authoritative_engine_before: str = "V1.4.1"
    authority_changed: bool = False
    status: str = "RECORDED"

    def public(self) -> dict[str, Any]:
        return asdict(self)


class MigrationDecisionStore:
    """Append-only decision records; no record can change execution authority."""

    def __init__(self, state_path: Path | None = None):
        self.state_path = state_path or Path(__file__).resolve().parent / "runtime" / "migration_decisions.json"
        self._lock = threading.RLock()
        self._items: dict[str, MigrationDecisionRecord] = {}
        self._load()

    def _load(self):
        if not self.state_path.exists():
            return
        try:
            for item in json.loads(self.state_path.read_text(encoding="utf-8")):
                record = MigrationDecisionRecord(**item)
                self._items[record.decision_id] = record
        except (OSError, ValueError, TypeError):
            self._items = {}

    def _persist(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps([x.public() for x in self._items.values()], indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.state_path)

    def record(self, package, decision: str, actor: str, rationale: str = "") -> MigrationDecisionRecord:
        if decision not in DECISIONS:
            raise ValueError(f"Unsupported migration decision: {decision}")
        if not package:
            raise ValueError("Migration evidence package is required")
        if not rationale.strip():
            raise ValueError("Decision rationale is required")
        payload = {
            "package_id": package.package_id,
            "capability": package.capability,
            "decision": decision,
            "actor": actor,
            "rationale": rationale.strip(),
            "package_manifest_sha256": package.manifest_sha256,
            "authoritative_engine_before": package.authoritative_engine,
            "authority_changed": False,
        }
        record = MigrationDecisionRecord(
            decision_id="DEC-" + uuid.uuid4().hex[:12].upper(),
            decided_at=_now(),
            decision_sha256=_hash(payload),
            **payload,
        )
        with self._lock:
            self._items[record.decision_id] = record
            self._persist()
        return record

    def get(self, decision_id: str):
        return self._items.get(decision_id)

    def for_package(self, package_id: str):
        return [x for x in self._items.values() if x.package_id == package_id]

    def list(self):
        return list(self._items.values())
