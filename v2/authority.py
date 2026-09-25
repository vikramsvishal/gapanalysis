"""Capability-scoped execution-authority control plane.

Authority is never changed by a migration-review decision alone. Activation is an
explicit human action bound to an immutable evidence-pack manifest and decision
hash. V1.4.1 remains the default and rollback target.
"""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .migration_decision import MigrationDecisionStore

DEFAULT_ENGINE = "V1.4.1"
V2_ENGINE = "V2"
ACTIVE_STATUSES = {"ACTIVE"}
ALLOWED_CAPABILITIES = {
    "NETWORK_RECONCILIATION",
    "SERVER_RECONCILIATION",
    "NETWORK_HARDWARE_GOVERNANCE",
    "SERVER_HARDWARE_GOVERNANCE",
    "NETWORK_OS_BULK_LOAD",
    "SERVER_OS_BULK_LOAD",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AuthorityState:
    capability: str
    engine: str = DEFAULT_ENGINE
    status: str = "ACTIVE"
    activated_at: str | None = None
    activated_by: str | None = None
    evidence_package_id: str | None = None
    evidence_manifest_sha256: str | None = None
    migration_decision_id: str | None = None
    migration_decision_sha256: str | None = None
    previous_engine: str | None = None
    updated_at: str = ""

    def public(self) -> dict[str, Any]:
        return asdict(self)


class AuthorityStore:
    """Persistent, capability-isolated authority state with explicit activation/rollback."""

    def __init__(self, decision_store: MigrationDecisionStore, evidence_store, state_path: Path | None = None):
        self.decision_store = decision_store
        self.evidence_store = evidence_store
        self.state_path = state_path or Path(__file__).resolve().parent / "runtime" / "authority.json"
        self._lock = threading.RLock()
        self._items: dict[str, AuthorityState] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            for item in json.loads(self.state_path.read_text(encoding="utf-8")):
                state = AuthorityState(**item)
                self._items[state.capability] = state
        except (OSError, ValueError, TypeError):
            self._items = {}

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps([x.public() for x in self._items.values()], indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.state_path)

    def get(self, capability: str) -> AuthorityState:
        if capability not in ALLOWED_CAPABILITIES:
            raise ValueError(f"Unsupported capability: {capability}")
        return self._items.get(
            capability,
            AuthorityState(capability=capability, updated_at=_now()),
        )

    def list(self) -> list[AuthorityState]:
        return [self.get(capability) for capability in sorted(ALLOWED_CAPABILITIES)]

    def activate(self, capability: str, decision_id: str, actor: str, rationale: str = "") -> AuthorityState:
        current = self.get(capability)
        if not actor.strip():
            raise ValueError("Activation actor is required")
        if not rationale.strip():
            raise ValueError("Activation rationale is required")
        decision = self.decision_store.get(decision_id)
        if decision is None:
            raise ValueError("Migration decision not found")
        if decision.decision != "APPROVE_AUTHORITY_REVIEW":
            raise ValueError("Only an APPROVE_AUTHORITY_REVIEW decision can be activated")
        package = self.evidence_store.get(decision.package_id)
        if package is None:
            raise ValueError("Migration evidence package not found")
        if package.capability != capability:
            raise ValueError("Migration evidence capability does not match requested authority capability")
        if package.manifest_sha256 != decision.package_manifest_sha256:
            raise ValueError("Migration decision is not bound to the current evidence-pack manifest")
        if decision.authority_changed:
            raise ValueError("Migration decision already records an authority change")
        if package.readiness.get("status") not in {"READY_FOR_AUTHORITY_REVIEW", "READY"}:
            raise ValueError("Migration evidence package is not ready for authority activation")
        with self._lock:
            state = AuthorityState(
                capability=capability,
                engine=V2_ENGINE,
                status="ACTIVE",
                activated_at=_now(),
                activated_by=actor,
                evidence_package_id=package.package_id,
                evidence_manifest_sha256=package.manifest_sha256,
                migration_decision_id=decision.decision_id,
                migration_decision_sha256=decision.decision_sha256,
                previous_engine=current.engine,
                updated_at=_now(),
            )
            self._items[capability] = state
            self._persist()
        return state

    def rollback(self, capability: str, actor: str, rationale: str = "") -> AuthorityState:
        current = self.get(capability)
        if not actor.strip():
            raise ValueError("Rollback actor is required")
        if not rationale.strip():
            raise ValueError("Rollback rationale is required")
        with self._lock:
            state = AuthorityState(
                capability=capability,
                engine=DEFAULT_ENGINE,
                status="ACTIVE",
                activated_at=None,
                activated_by=None,
                evidence_package_id=None,
                evidence_manifest_sha256=None,
                migration_decision_id=None,
                migration_decision_sha256=None,
                previous_engine=current.engine,
                updated_at=_now(),
            )
            self._items[capability] = state
            self._persist()
        return state
