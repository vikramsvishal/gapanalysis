import pytest

from v2.category_governance import CategoryDependencyDecision
from v2.contracts import AssetIdentity, CatalogMatchStatus, DecisionStatus, GovernanceDecision
from v2.hardware_decision import HardwareGovernanceDecisionComposer, HardwareGovernanceSignals


def category(action):
    return CategoryDependencyDecision(
        serial_number="S1",
        category_presence_status="FOUND IN CATEGORY" if action == "LOAD OS ONLY" else "MISSING FROM CATEGORY",
        parent_dependency_status=(
            "EXISTING PRODUCTION CATEGORY"
            if action == "LOAD OS ONLY"
            else "PARENT CATEGORY LOAD REQUIRED"
        ),
        recommended_action=action,
    )


def compose(action="LOAD OS ONLY", catalog=CatalogMatchStatus.EXACT, lifecycle="operational", recon="Load To IS"):
    d = GovernanceDecision(asset_identity=AssetIdentity(serial="S1"))
    return HardwareGovernanceDecisionComposer().compose(
        decision=d,
        signals=HardwareGovernanceSignals(
            lifecycle_stage=lifecycle,
            reconciliation_action=recon,
            catalog_status=catalog,
            catalog_update_required=catalog == CatalogMatchStatus.NO_MATCH,
            category=category(action),
        ),
    )


def test_existing_category_is_load_os_only():
    d = compose()
    assert d.action == DecisionStatus.LOAD
    assert d.recommendation == "LOAD OS ONLY"
    assert d.required_values["category_load_required"] is False


def test_missing_category_requires_category_and_os():
    d = compose("LOAD CATEGORY AND OS")
    assert d.action == DecisionStatus.LOAD
    assert d.recommendation == "LOAD CATEGORY AND OS"
    assert d.required_values["category_load_required"] is True


def test_duplicate_category_is_review():
    d = compose("CATEGORY DATA QUALITY REVIEW")
    assert d.action == DecisionStatus.REVIEW
    assert d.approval_required is True


def test_no_catalog_match_requires_catalog_update():
    d = compose(catalog=CatalogMatchStatus.NO_MATCH)
    assert d.action == DecisionStatus.CATALOG_UPDATE_REQUIRED
    assert d.recommendation == "CATALOG UPDATE REQUIRED"


def test_ambiguous_catalog_is_review_not_load():
    d = compose(catalog=CatalogMatchStatus.AMBIGUOUS)
    assert d.action == DecisionStatus.REVIEW
    assert d.approval_required is True


@pytest.mark.parametrize("lifecycle,recon", [
    ("retired", "Load To IS"),
    ("operational", "No Action"),
])
def test_out_of_scope_record_is_no_action(lifecycle, recon):
    d = compose(lifecycle=lifecycle, recon=recon)
    assert d.action == DecisionStatus.NO_ACTION
    assert d.recommendation == "NO LOAD ACTION"
