"""Application boundary for the V2 local enterprise edition."""
from __future__ import annotations
from dataclasses import dataclass

from .agents import AgentRegistry, default_registry
from .jobs import JobManager
from .services import GovernanceService


@dataclass
class ApplicationService:
    """Application facade independent of Tkinter or HTTP transport."""

    agents: AgentRegistry | None = None
    governance: GovernanceService | None = None
    jobs: JobManager | None = None

    def __post_init__(self):
        self.governance = self.governance or GovernanceService()
        self.agents = self.agents or default_registry()
        self.jobs = self.jobs or JobManager(self.governance)

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
