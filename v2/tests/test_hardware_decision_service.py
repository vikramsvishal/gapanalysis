import pytest

from v2.category_governance import CategoryDependencyDecision
from v2.contracts import AssetIdentity, CatalogMatchStatus, GovernanceDecision
from v2.hardware_decision import HardwareGovernanceSignals
from v2.hardware_governance import HardwareGovernanceService


def test_hardware_governance_service_exposes_decision_composer():
    category = CategoryDependencyDecision(
        serial_number="S1",
        category_presence_status="FOUND IN CATEGORY",
        parent_dependency_status="EXISTING PRODUCTION CATEGORY",
        recommended_action="LOAD OS ONLY",
    )
    decision = GovernanceDecision(asset_identity=AssetIdentity(serial="S1"))
    result = HardwareGovernanceService(object()).compose_decision(
        decision=decision,
        signals=HardwareGovernanceSignals(
            lifecycle_stage="operational",
            reconciliation_action="Load To IS",
            catalog_status=CatalogMatchStatus.EXACT,
            catalog_update_required=False,
            category=category,
        ),
    )
    assert result.recommendation == "LOAD OS ONLY"
