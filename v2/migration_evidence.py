"""Migration evidence-pack control plane.

Evidence packs are immutable snapshots for human authority review. They never
change the V1.4.1 execution authority and are deliberately JSON-native so they
remain portable for later server deployment.
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


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass
class MigrationEvidencePack:
    package_id: str
    generated_at: str
    scope: str
    capability: str | None
    result_ids: list[str]
    shadow_evidence_ids: list[str]
    classification_ids: list[str]
    audit_event_ids: list[str]
    readiness: dict[str, Any]
    manifest_sha256: str
    status: str = "GENERATED"
    authoritative_engine: str = "V1.4.1"
    schema_version: str = "1.0"

    def public(self) -> dict[str, Any]:
        return asdict(self)


class MigrationEvidencePackStore:
    """Persist immutable migration evidence-pack metadata and manifests."""

    def __init__(self, state_path: Path | None = None):
        self.state_path = state_path or Path(__file__).resolve().parent / "runtime" / "migration_evidence_packs.json"
        self.manifest_dir = self.state_path.parent / "migration_evidence"
        self._lock = threading.RLock()
        self._items: dict[str, MigrationEvidencePack] = {}
        self._manifests: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            for item in payload.get("items", []):
                record = MigrationEvidencePack(**item)
                self._items[record.package_id] = record
            self._manifests = payload.get("manifests", {})
        except (OSError, ValueError, TypeError):
            self._items = {}
            self._manifests = {}

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {"items": [x.public() for x in self._items.values()], "manifests": self._manifests},
                indent=2,
                sort_keys=True,
                default=str,
            ),
            encoding="utf-8",
        )
        tmp.replace(self.state_path)

    def create(
        self,
        *,
        scope: str,
        capability: str | None,
        result_ids: list[str],
        shadow_evidence_ids: list[str],
        classification_ids: list[str],
        audit_event_ids: list[str],
        readiness: dict[str, Any],
        manifest: dict[str, Any],
    ) -> MigrationEvidencePack:
        manifest_payload = {
            "schema_version": "1.0",
            "scope": scope,
            "capability": capability,
            "result_ids": sorted(result_ids),
            "shadow_evidence_ids": sorted(shadow_evidence_ids),
            "classification_ids": sorted(classification_ids),
            "audit_event_ids": sorted(audit_event_ids),
            "readiness": readiness,
            "evidence": manifest,
        }
        package_id = "MIG-" + uuid.uuid4().hex[:12].upper()
        record = MigrationEvidencePack(
            package_id=package_id,
            generated_at=_now(),
            scope=scope,
            capability=capability,
            result_ids=sorted(result_ids),
            shadow_evidence_ids=sorted(shadow_evidence_ids),
            classification_ids=sorted(classification_ids),
            audit_event_ids=sorted(audit_event_ids),
            readiness=readiness,
            manifest_sha256=_sha256(manifest_payload),
        )
        with self._lock:
            self._items[package_id] = record
            self._manifests[package_id] = manifest_payload
            self._persist()
        return record

    def get(self, package_id: str) -> MigrationEvidencePack | None:
        with self._lock:
            return self._items.get(package_id)

    def manifest(self, package_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._manifests.get(package_id)

    def list(self) -> list[MigrationEvidencePack]:
        with self._lock:
            return list(self._items.values())
