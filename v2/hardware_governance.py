"""V2 hardware-governance domain seam.

The first extraction is deliberately an anti-corruption boundary: V1.4.1 remains
the decision oracle while V2 owns the stable request/result contract. Business
rules are migrated behind this seam only after golden regression coverage exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

from .catalog_resolution import AuthoritativeHardwareCatalogResolver, CatalogResolutionRequest
from .category_governance import CategoryDependencyGovernance
from .legacy_adapter import load_golden


@dataclass(frozen=True)
class HardwareGovernanceRequest:
    domain: str
    cmdb_path: str
    category_path: str
    catalog_path: str
    output_dir: str
    write_outputs: bool = True


@dataclass
class HardwareGovernanceResult:
    domain: str
    decisions: Any = None
    category_load: Any = None
    candidate_ids: set[str] = field(default_factory=set)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[Any] = field(default_factory=list)
    engine: str = "V1.4.1"

    @property
    def decision_count(self) -> int:
        return len(self.decisions) if self.decisions is not None else 0

    @property
    def category_load_count(self) -> int:
        return len(self.category_load) if self.category_load is not None else 0


class HardwareGovernanceService:
    """Stable V2 boundary over the protected hardware-governance implementation."""

    SUPPORTED_DOMAINS = frozenset({"network", "server"})

    def __init__(self, engine: Any):
        self.engine = engine

    def resolve_category_dependency(self, domain: str, serial_number: str, category):
        """Resolve category presence independently from hardware identity matching."""
        golden = load_golden()
        governance = CategoryDependencyGovernance(golden.lifecycle, golden.serial_key)
        return governance.evaluate(domain, serial_number, category)

    def resolve_catalog_identity(
        self,
        catalog: pd.DataFrame,
        manufacturer: str,
        model: str,
        source_reference: str = "",
        domain: str = "network",
    ):
        """Resolve a hardware identity without making a governance/load decision."""
        resolver = AuthoritativeHardwareCatalogResolver(catalog)
        return resolver.resolve(
            CatalogResolutionRequest(
                domain=domain,
                manufacturer=manufacturer,
                model=model,
                source_reference=source_reference,
            )
        )

    def execute(
        self,
        request: HardwareGovernanceRequest,
        progress: Callable[[str, int], None] | None = None,
    ) -> HardwareGovernanceResult:
        if request.domain not in self.SUPPORTED_DOMAINS:
            raise ValueError("Hardware Governance requires domain=network or domain=server")

        raw = self.engine.run_hardware_governance(
            request.domain,
            request.cmdb_path,
            request.category_path,
            request.catalog_path,
            request.output_dir,
            progress or (lambda _message, _percent=0: None),
            write_outputs=request.write_outputs,
        )
        return HardwareGovernanceResult(
            domain=request.domain,
            decisions=raw.get("decisions"),
            category_load=raw.get("category_load"),
            candidate_ids=set(raw.get("candidate_ids", set())),
            outputs=list(raw.get("outputs", [])),
            engine="V1.4.1",
        )
