"""Application boundary for the V2 local enterprise edition."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from .agents import AgentRegistry, default_registry
from .services import GovernanceService


@dataclass
class ApplicationService:
    """Application facade independent of Tkinter or HTTP transport."""

    agents: AgentRegistry | None = None
    governance: GovernanceService | None = None

    def __post_init__(self):
        self.governance = self.governance or GovernanceService()
        self.agents = self.agents or default_registry()

    @property
    def version(self) -> str:
        return "2.0.0-alpha.2"

    @property
    def golden_version(self) -> str:
        return "1.4.1"

    def health(self) -> dict:
        return {
            "application": "CMDB_IS_GOVERNANCE",
            "version": self.version,
            "golden_version": self.golden_version,
            "mode": "LOCAL",
            "business_engine": "V1.4.1",
            "status": "READY",
        }

    def legacy_operation(self, operation: str, *args, **kwargs):
        """Compatibility operation routed through the V2 service boundary."""
        allowed = {
            "reconcile_network": self.governance.reconcile_network,
            "reconcile_server": self.governance.reconcile_server,
            "run_hardware_governance": self.governance.run_hardware_governance,
            "generate_bulk_load": self.governance.generate_bulk_load,
            "category_decisions_from_load": self.governance.category_decisions_from_load,
        }
        target = allowed.get(operation)
        if not target:
            raise ValueError(f"Unsupported governance operation: {operation}")
        return target(*args, **kwargs)
