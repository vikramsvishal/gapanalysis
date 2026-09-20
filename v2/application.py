"""Application boundary for the V2 local enterprise edition."""
from __future__ import annotations
from dataclasses import dataclass

from .agents import AgentRegistry, default_registry
from .jobs import JobManager
from .services import GovernanceService
from .results import ResultStore
from .evidence import EvidenceStore
from .exceptions import ExceptionStore
from .audit import AuditStore


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

    def __post_init__(self):
        self.governance = self.governance or GovernanceService()
        self.agents = self.agents or default_registry()
        self.evidence = self.evidence or EvidenceStore()
        self.exceptions = self.exceptions or ExceptionStore()
        self.audit = self.audit or AuditStore()
        self.results = self.results or ResultStore(evidence_store=self.evidence)
        if getattr(self.results, "evidence_store", None) is None:
            self.results.evidence_store = self.evidence
        self.jobs = self.jobs or JobManager(self.governance, result_store=self.results)

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

    def resolve_exception(self, exception_id: str, actor: str, resolution: str):
        record = self.exceptions.resolve(exception_id, actor, resolution)
        self.audit.append("EXCEPTION", actor, "EXCEPTION", exception_id, "RESOLVED", {"result_id": record.result_id, "resolution": resolution})
        return record

    def get_audit(self, event_id: str):
        return self.audit.get(event_id)

    def entity_audit(self, entity_type: str, entity_id: str):
        return self.audit.for_entity(entity_type, entity_id)

    def list_audit(self):
        return self.audit.list()
