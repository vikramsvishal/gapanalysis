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
