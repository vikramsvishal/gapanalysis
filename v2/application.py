"""Application boundary for the V2 local enterprise edition."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from .agents import AgentRegistry, default_registry
from .jobs import JobManager
from .services import GovernanceService
from .results import ResultStore
from .shadow_migration import ShadowMigrationStore
from .migration_readiness import MigrationReadinessGate
from .migration_evidence import MigrationEvidencePackStore
from .migration_decision import MigrationDecisionStore
from .authority import AuthorityStore
from .evidence import EvidenceStore
from .exceptions import ExceptionStore
from .audit import AuditStore
from .approvals import ApprovalStore


@dataclass
class ApplicationService:
    """Application facade independent of Tkinter or HTTP transport."""

    agents: AgentRegistry | None = None
    governance: GovernanceService | None = None
    jobs: JobManager | None = None
    results: ResultStore | None = None
    evidence: EvidenceStore | None = None
    exceptions: ExceptionStore | None = None
    audit: AuditStore | None = None
    approvals: ApprovalStore | None = None

    def __post_init__(self):
        self.governance = self.governance or GovernanceService()
        self.agents = self.agents or default_registry()
        self.evidence = self.evidence or EvidenceStore()
        self.exceptions = self.exceptions or ExceptionStore()
        self.audit = self.audit or AuditStore()
        self.approvals = self.approvals or ApprovalStore()
        self.results = self.results or ResultStore(evidence_store=self.evidence)
        self.shadow_migration = ShadowMigrationStore()
        self.migration_readiness = MigrationReadinessGate()
        self.migration_evidence = MigrationEvidencePackStore()
        self.migration_decisions = MigrationDecisionStore()
        self.authority = AuthorityStore(self.migration_decisions, self.migration_evidence)
        if getattr(self.results, "evidence_store", None) is None:
            self.results.evidence_store = self.evidence
        self.jobs = self.jobs or JobManager(self.governance, result_store=self.results, exception_store=self.exceptions, audit_store=self.audit, approval_store=self.approvals)

    @property
    def version(self) -> str:
        return "2.0.0-alpha.3"

    @property
    def golden_version(self) -> str:
        return "1.4.1"

    def health(self) -> dict:
        return {"application":"CMDB_IS_GOVERNANCE","version":self.version,"golden_version":self.golden_version,"mode":"LOCAL","business_engine":"V1.4.1","status":"READY"}

    def legacy_operation(self, operation: str, *args, **kwargs):
        return self.governance.execute_legacy(operation, *args, **kwargs)

    def start_job(self, operation: str, payload: dict | None = None, actor: str = "local-user"):
        job = self.jobs.create(operation, payload, actor)
        self.audit.append("JOB", actor, "JOB", job.job_id, "STARTED", {"operation": operation})
        return job

    def get_job(self, job_id: str):
        return self.jobs.get(job_id)

    def list_jobs(self):
        return self.jobs.list()

    def get_result(self, result_id: str):
        return self.results.get(result_id)

    def get_shadow(self, result_id: str) -> dict | None:
        """Return persisted non-authoritative shadow diagnostics for a result."""
        result = self.results.get(result_id)
        if result is None or not isinstance(result.summary, dict):
            return None
        shadow = result.summary.get("shadow")
        if not isinstance(shadow, dict) or not shadow.get("enabled"):
            return None
        mismatches = shadow.get("mismatches", [])
        by_field: dict[str, dict[str, object]] = {}
        for mismatch in mismatches:
            for field, difference in (mismatch.get("differences") or {}).items():
                bucket = by_field.setdefault(field, {"field": field, "divergence_count": 0, "examples": []})
                bucket["divergence_count"] = int(bucket["divergence_count"]) + 1
                examples = bucket["examples"]
                if isinstance(examples, list) and len(examples) < 5:
                    examples.append({
                        "row_index": mismatch.get("row_index"),
                        "serial_number": mismatch.get("serial_number", ""),
                        "golden": difference.get("golden"),
                        "v2": difference.get("v2"),
                    })
        divergence_by_field = sorted(
            by_field.values(),
            key=lambda item: (-int(item["divergence_count"]), str(item["field"])),
        )
        return {
            "result_id": result_id,
            "authoritative_engine": shadow.get("authoritative_engine", "V1.4.1"),
            "row_count": shadow.get("row_count", 0),
            "match_count": shadow.get("match_count", 0),
            "mismatch_count": shadow.get("mismatch_count", 0),
            "mismatch_percentage": (
                round((shadow.get("mismatch_count", 0) / shadow.get("row_count", 0)) * 100, 2)
                if shadow.get("row_count") else 0.0
            ),
            "divergence_by_field": divergence_by_field,
            "mismatches": mismatches,
            "evidence_ids": result.evidence_ids,
        }

    def get_shadow_migration(self, result_id: str) -> dict:
        return self.shadow_migration.summary(result_id)

    def get_capability_migration_readiness(self) -> dict:
        results = self.results.list()
        shadows = {r.result_id: self.get_shadow(r.result_id) for r in results}
        classifications = {r.result_id: [x.public() for x in self.shadow_migration.for_result(r.result_id)] for r in results}
        return self.migration_readiness.evaluate_capabilities(results, shadows, classifications)

    def generate_migration_evidence(
        self, scope: str = "ALL", capability: str | None = None, result_ids: list[str] | None = None,
        actor: str = "local-user"
    ):
        """Freeze shadow, classification, readiness and audit evidence for review."""
        all_results = self.results.list()
        selected = [r for r in all_results if not result_ids or r.result_id in set(result_ids)]
        if capability:
            selected = [r for r in selected if self.migration_readiness_capability(r) == capability]
        selected = [r for r in selected if r.status == "COMPLETED"]
        selected_ids = [r.result_id for r in selected]
        shadows = {r.result_id: self.get_shadow(r.result_id) for r in selected}
        classifications = {r.result_id: [x.public() for x in self.shadow_migration.for_result(r.result_id)] for r in selected}
        readiness = self.migration_readiness.evaluate_capabilities(selected, shadows, classifications)
        if capability:
            readiness = next((x for x in readiness.get("capabilities", []) if x.get("capability") == capability), {
                "capability": capability, "status": "NOT_READY", "result_count": 0,
                "divergence_count": 0, "blocking_count": 0, "unclassified_count": 0,
            })
        else:
            readiness = {**readiness, "scope": scope}
        shadow_evidence_ids = []
        classification_ids = []
        for result in selected:
            shadow_evidence_ids.extend(
                [e.evidence_id for e in self.evidence.for_result(result.result_id) if e.kind == "HARDWARE_GOVERNANCE_SHADOW"]
            )
            classification_ids.extend(x["classification_id"] for x in classifications[result.result_id])
        audit_items = []
        for event in self.audit.list():
            if event.entity_type == "RESULT" and event.entity_id in selected_ids:
                audit_items.append(event)
        audit_event_ids = [x.event_id for x in audit_items]
        manifest = {
            "results": [r.public() for r in selected],
            "shadows": shadows,
            "classifications": classifications,
            "readiness": readiness,
            "audit": [x.public() for x in audit_items],
            "golden_version": self.golden_version,
            "application_version": self.version,
        }
        record = self.migration_evidence.create(
            scope=scope, capability=capability, result_ids=selected_ids,
            shadow_evidence_ids=sorted(set(shadow_evidence_ids)),
            classification_ids=sorted(set(classification_ids)),
            audit_event_ids=audit_event_ids, readiness=readiness, manifest=manifest,
        )
        self.audit.append("MIGRATION_EVIDENCE", actor, "MIGRATION_EVIDENCE", record.package_id, "GENERATED", {
            "scope": scope, "capability": capability, "result_count": len(selected_ids),
            "manifest_sha256": record.manifest_sha256, "authoritative_engine": self.golden_version,
        })
        return record

    def migration_evidence_manifest(self, package_id: str):
        return self.migration_evidence.manifest(package_id)

    def list_migration_evidence(self):
        return self.migration_evidence.list()

    def get_migration_evidence(self, package_id: str):
        return self.migration_evidence.get(package_id)

    def migration_readiness_capability(self, result) -> str:
        from .migration_readiness import capability
        return capability(result.operation, str((result.inputs or {}).get("domain", "")))

    def record_migration_decision(self, package_id: str, decision: str, actor: str, rationale: str = ""):
        package = self.migration_evidence.get(package_id)
        if package is None:
            raise ValueError("migration evidence pack not found")
        if package.readiness.get("status") not in ("READY_FOR_AUTHORITY_REVIEW", "READY"):
            raise ValueError("migration evidence pack is not ready for authority review")
        record = self.migration_decisions.record(package, decision, actor, rationale)
        self.audit.append("MIGRATION_DECISION", actor, "MIGRATION_EVIDENCE", package_id, decision, {
            "decision_id": record.decision_id, "decision_sha256": record.decision_sha256,
            "package_manifest_sha256": record.package_manifest_sha256, "authority_changed": False,
        })
        return record

    def list_authority(self):
        return self.authority.list()

    def get_authority(self, capability: str):
        return self.authority.get(capability)

    def activate_authority(self, capability: str, decision_id: str, actor: str, rationale: str = ""):
        state = self.authority.activate(capability, decision_id, actor, rationale)
        self.audit.append(
            "AUTHORITY", actor, "AUTHORITY", capability, "ACTIVATED",
            {
                "engine": state.engine,
                "previous_engine": state.previous_engine,
                "migration_decision_id": state.migration_decision_id,
                "migration_decision_sha256": state.migration_decision_sha256,
                "evidence_package_id": state.evidence_package_id,
                "evidence_manifest_sha256": state.evidence_manifest_sha256,
            },
        )
        return state

    def rollback_authority(self, capability: str, actor: str, rationale: str = ""):
        state = self.authority.rollback(capability, actor, rationale)
        self.audit.append(
            "AUTHORITY", actor, "AUTHORITY", capability, "ROLLED_BACK",
            {"engine": state.engine, "previous_engine": state.previous_engine, "rationale": rationale.strip()},
        )
        return state

    def get_migration_decision(self, decision_id: str):
        return self.migration_decisions.get(decision_id)

    def list_migration_decisions(self):
        return self.migration_decisions.list()

    def migration_package_decisions(self, package_id: str):
        return self.migration_decisions.for_package(package_id)

    def get_migration_readiness(self, result_id: str) -> dict:
        shadow = self.get_shadow(result_id)
        classifications = [x.public() for x in self.shadow_migration.for_result(result_id)]
        return self.migration_readiness.evaluate(shadow, classifications)

    def classify_shadow(self, result_id: str, row_index: int, field: str, status: str, rationale: str = "", owner: str = ""):
        record = self.shadow_migration.upsert(result_id, row_index, field, status, rationale, owner)
        self.audit.append(
            "SHADOW_MIGRATION", owner or "system", "RESULT", result_id, "CLASSIFIED",
            {"classification_id": record.classification_id, "row_index": row_index, "field": field, "status": status},
        )
        return record

    def get_job_result(self, job_id: str):
        return self.results.for_job(job_id)

    def list_results(self):
        return self.results.list()

    def get_evidence(self, evidence_id: str):
        return self.evidence.get(evidence_id)

    def result_evidence(self, result_id: str):
        return self.evidence.for_result(result_id)

    def list_evidence(self):
        return self.evidence.list()

    def get_exception(self, exception_id: str):
        return self.exceptions.get(exception_id)

    def result_exceptions(self, result_id: str):
        return self.exceptions.for_result(result_id)

    def list_exceptions(self):
        return self.exceptions.list()

    def resolve_exception(self, exception_id: str, actor: str, resolution: str, decision: str = "APPROVE"):
        record = self.exceptions.resolve(exception_id, actor, resolution, decision)
        self.audit.append(
            "EXCEPTION", actor, "EXCEPTION", exception_id, "RESOLVED",
            {"result_id": record.result_id, "resolution": resolution, "decision": record.decision},
        )
        return record

    def get_approval(self, approval_id: str):
        return self.approvals.get(approval_id)

    def result_approval(self, result_id: str):
        return self.approvals.for_result(result_id)

    def list_approvals(self):
        return self.approvals.list()

    def finalize_bulk_load(self, approval_id: str, actor: str = "local-user"):
        approval = self.approvals.get(approval_id)
        if approval is None:
            raise KeyError(approval_id)
        exceptions = self.exceptions.for_result(approval.result_id)
        result = self.governance.finalize_bulk_load(approval, exceptions, actor)

        decision_snapshot = [
            {
                "candidate_id": x.candidate_id,
                "exception_id": x.exception_id,
                "decision": x.decision,
                "resolution": x.resolution,
                "resolved_by": x.resolved_by,
            }
            for x in sorted(exceptions, key=lambda item: item.exception_id)
        ]
        decision_payload = json.dumps(decision_snapshot, sort_keys=True, separators=(",", ":"), default=str)
        decision_sha = hashlib.sha256(decision_payload.encode("utf-8")).hexdigest()
        evidence = self.evidence.capture_text(
            approval.result_id, "APPROVAL_DECISION_SNAPSHOT", approval.approval_id,
            approval.approval_id + "-decision-snapshot.json", decision_payload,
        )
        output_hashes = {}
        for output in result.get("outputs", []):
            path = output.get("path") if isinstance(output, dict) else None
            if path and Path(path).is_file():
                output_hashes[str(path)] = hashlib.sha256(Path(path).read_bytes()).hexdigest()

        self.results.update_summary(
            approval.result_id,
            {
                "status": result.get("status"),
                "approval_id": approval_id,
                "finalization": result,
            },
        )
        finalized = self.approvals.finalize(approval_id, actor, result, decision_snapshot_sha256=decision_sha, output_sha256=output_hashes)
        self.audit.append(
            "APPROVAL", actor, "APPROVAL", approval_id, "FINALIZED",
            {"result_id": approval.result_id, "approved_count": result.get("approved_count"), "decision_snapshot_sha256": decision_sha, "output_sha256": output_hashes, "evidence_id": evidence.evidence_id},
        )
        return finalized

    def get_audit(self, event_id: str):
        return self.audit.get(event_id)

    def entity_audit(self, entity_type: str, entity_id: str):
        return self.audit.for_entity(entity_type, entity_id)

    def list_audit(self):
        return self.audit.list()
