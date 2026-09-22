"""Shadow equivalence helpers for hardware governance.

The golden engine remains authoritative. These helpers normalize its decisions
and the V2 composition into a small comparable projection.
"""
from __future__ import annotations

from typing import Any

from .contracts import CatalogMatchStatus
from .hardware_decision import HardwareGovernanceDecisionComposer, HardwareGovernanceSignals


def golden_decision_projection(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "catalog_status": record.get("Catalog Match Status", ""),
        "category_presence_status": record.get("Category Presence Status", ""),
        "recommended_action": record.get("Recommended Action", ""),
        "parent_dependency_status": record.get("Parent Dependency Status", ""),
        "candidate_set_id": record.get("Candidate Set ID", ""),
    }


def v2_decision_projection(
    *,
    lifecycle_stage: str,
    reconciliation_action: str,
    catalog_status: CatalogMatchStatus,
    category,
) -> dict[str, Any]:
    from .contracts import AssetIdentity, GovernanceDecision

    result = HardwareGovernanceDecisionComposer().compose(
        decision=GovernanceDecision(asset_identity=AssetIdentity(serial=category.serial_number)),
        signals=HardwareGovernanceSignals(
            lifecycle_stage=lifecycle_stage,
            reconciliation_action=reconciliation_action,
            catalog_status=catalog_status,
            catalog_update_required=catalog_status == CatalogMatchStatus.NO_MATCH,
            category=category,
        ),
    )
    return {
        "catalog_status": catalog_status.value,
        "category_presence_status": category.category_presence_status,
        "recommended_action": result.recommendation,
        "parent_dependency_status": category.parent_dependency_status,
    }
