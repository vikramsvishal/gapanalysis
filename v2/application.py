"""Application boundary for the V2 local enterprise edition."""
from __future__ import annotations
from dataclasses import dataclass

from .agents import AgentRegistry, default_registry
from .jobs import JobManager
from .services import GovernanceService
from .results import ResultStore
from .evidence import EvidenceStore


@dataclass
class ApplicationService:
    """Application facade independent of Tkinter or HTTP transport."""

    agents: AgentRegistry | None = None
    governance: GovernanceService | None = None
    jobs: JobManager | None = None
    results: ResultStore | None = None
    evidence: EvidenceStore | None = None

    def __post_init__(self):
        self.governance = self.governance or GovernanceService()
        self.agents = self.agents or default_registry()
        self.evidence = self.evidence or EvidenceStore()
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
        return self.jobs.create(operation, payload, actor)

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
