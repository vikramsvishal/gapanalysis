"""Append-only audit trail for the local enterprise edition."""
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
class AuditEvent:
    event_id: str
    event_type: str
    actor: str
    timestamp: str
    entity_type: str
    entity_id: str
    action: str
    details: dict[str, Any] = field(default_factory=dict)
    previous_event_hash: str | None = None
    event_hash: str = ""

    def public(self) -> dict[str, Any]:
        return asdict(self)


class AuditStore:
    """Append-only audit journal with hash chaining."""

    def __init__(self, state_path: Path | None = None):
        self.state_path = state_path or Path(__file__).resolve().parent / "runtime" / "audit.json"
        self._lock = threading.RLock()
        self._events: list[AuditEvent] = []
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            self._events = [AuditEvent(**x) for x in json.loads(self.state_path.read_text(encoding="utf-8"))]
        except (OSError, ValueError, TypeError):
            self._events = []

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps([x.public() for x in self._events], indent=2, default=str), encoding="utf-8")
        tmp.replace(self.state_path)

    def append(
        self,
        event_type: str,
        actor: str,
        entity_type: str,
        entity_id: str,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        with self._lock:
            previous = self._events[-1].event_hash if self._events else None
            event_id = "AUD-" + uuid.uuid4().hex[:12].upper()
            timestamp = _now()
            body = {
                "event_id": event_id,
                "event_type": event_type,
                "actor": actor,
                "timestamp": timestamp,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action": action,
                "details": details or {},
                "previous_event_hash": previous,
            }
            digest = hashlib.sha256(
                json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
            ).hexdigest()
            event = AuditEvent(**body, event_hash=digest)
            self._events.append(event)
            self._persist()
            return event

    def get(self, event_id: str) -> AuditEvent | None:
        return next((x for x in self._events if x.event_id == event_id), None)

    def for_entity(self, entity_type: str, entity_id: str) -> list[AuditEvent]:
        return [x for x in self._events if x.entity_type == entity_type and x.entity_id == entity_id]

    def list(self) -> list[AuditEvent]:
        return list(reversed(self._events))
