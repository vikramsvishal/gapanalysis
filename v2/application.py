"""Application boundary for the V2 local enterprise edition."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from .agents import AgentRegistry, default_registry
from .domain import JobResult
from .legacy_adapter import load_golden


@dataclass
class ApplicationService:
    """Application facade independent of Tkinter."""

    agents: AgentRegistry | None = None
    golden: Any | None = None

    def __post_init__(self):
        self.agents = self.agents or default_registry()
        self.golden = self.golden or load_golden()

    @property
    def version(self) -> str:
        return "2.0.0-alpha.1"

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
        """Invoke an existing V1.4.1 operation through the V2 application seam."""
        allowed = {
            "reconcile_network": "reconcile_nw",
            "reconcile_server": "reconcile_server",
            "run_hardware_governance": "run_hardware_governance",
            "generate_bulk_load": "generate_bulk_load",
            "category_decisions_from_load": "category_decisions_from_load",
        }
        target = allowed.get(operation)
        if not target:
            raise ValueError(f"Unsupported governance operation: {operation}")
        return getattr(self.golden, target)(*args, **kwargs)
