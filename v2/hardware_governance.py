"""V2 hardware-governance domain seam.

The first extraction is deliberately an anti-corruption boundary: V1.4.1 remains
the decision oracle while V2 owns the stable request/result contract. Business
rules are migrated behind this seam only after golden regression coverage exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from pathlib import Path

import pandas as pd

from .catalog_resolution import AuthoritativeHardwareCatalogResolver, CatalogResolutionRequest
from .category_governance import CategoryDependencyGovernance
from .hardware_decision import HardwareGovernanceDecisionComposer, HardwareGovernanceSignals
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
    shadow: dict[str, Any] = field(default_factory=dict)

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

    def compose_decision(self, *, decision, signals: HardwareGovernanceSignals):
        """Compose resolved hardware signals without invoking the golden engine."""
        return HardwareGovernanceDecisionComposer().compose(decision=decision, signals=signals)

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
        shadow = self._shadow_compare(request, raw.get("decisions")) if all(Path(p).is_file() for p in (request.cmdb_path, request.category_path, request.catalog_path)) else {"enabled": False, "reason": "shadow inputs unavailable"}
        return HardwareGovernanceResult(
            domain=request.domain,
            decisions=raw.get("decisions"),
            category_load=raw.get("category_load"),
            candidate_ids=set(raw.get("candidate_ids", set())),
            outputs=list(raw.get("outputs", [])),
            engine="V1.4.1",
            shadow=shadow,
        )

    def _shadow_compare(self, request: HardwareGovernanceRequest, decisions: Any) -> dict[str, Any]:
        """Run V2 resolution beside V1.4.1 without changing authoritative results."""
        golden = load_golden()
        cmdb = golden.read_tabular(request.cmdb_path)
        category = golden.read_tabular(request.category_path)
        catalog = golden.read_tabular(request.catalog_path)
        serial_col = golden.find_col(cmdb, "Serial number")
        manufacturer_col = golden.find_col(cmdb, "Manufacturer")
        model_col = golden.find_col(cmdb, "Model number" if request.domain == "network" else "Model ID")
        life_col = golden.find_col(cmdb, "Life Cycle Stage")
        category_governance = CategoryDependencyGovernance(golden.lifecycle, golden.serial_key)
        resolver = AuthoritativeHardwareCatalogResolver(catalog)
        mismatches = []
        row_count = len(cmdb)
        for position, (_, row) in enumerate(cmdb.iterrows()):
            serial = str(row[serial_col] or "")
            model = str(row[model_col] or "")
            manufacturer = str(row[manufacturer_col] or "")
            category_decision = category_governance.evaluate(request.domain, serial, category)
            catalog_resolution = resolver.resolve(CatalogResolutionRequest(
                domain=request.domain, manufacturer=manufacturer, model=model,
                source_reference=f"CMDB row {position}",
            ))
            golden_record = decisions.iloc[position].to_dict() if hasattr(decisions, "iloc") and position < len(decisions) else {}
            golden_projection = {
                "catalog_status": golden_record.get("Catalog Match Status", ""),
                "category_presence_status": golden_record.get("Category Presence Status", ""),
                "recommended_action": golden_record.get("Recommended Action", ""),
                "parent_dependency_status": golden_record.get("Parent Dependency Status", ""),
            }
            v2_projection = v2_decision_projection(
                lifecycle_stage=golden.lifecycle(row[life_col]),
                reconciliation_action=golden_record.get("Reconciliation Action", ""),
                catalog_status=catalog_resolution.status,
                category=category_decision,
            )
            differences = {key: {"golden": golden_projection[key], "v2": v2_projection[key]}
                            for key in golden_projection if golden_projection[key] != v2_projection[key]}
            if differences:
                mismatches.append({
                    "row_index": position,
                    "serial_number": serial,
                    "golden": golden_projection,
                    "v2": v2_projection,
                    "differences": differences,
                })
        return {
            "enabled": True,
            "authoritative_engine": "V1.4.1",
            "row_count": row_count,
            "match_count": row_count - len(mismatches),
            "mismatch_count": len(mismatches),
            "mismatches": mismatches[:100],
        }
