from v2.category_governance import CategoryDependencyDecision
from v2.contracts import CatalogMatchStatus
from v2.hardware_equivalence import golden_decision_projection, v2_decision_projection


def test_existing_category_projection_matches_golden_shape():
    golden = {
        "Catalog Match Status": "EXACT MATCH",
        "Category Presence Status": "FOUND IN CATEGORY",
        "Recommended Action": "LOAD OS ONLY",
        "Parent Dependency Status": "EXISTING PRODUCTION CATEGORY",
        "Candidate Set ID": "CAND-1",
    }
    category = CategoryDependencyDecision(
        serial_number="S1",
        category_presence_status="FOUND IN CATEGORY",
        parent_dependency_status="EXISTING PRODUCTION CATEGORY",
        recommended_action="LOAD OS ONLY",
    )
    actual = v2_decision_projection(
        lifecycle_stage="operational",
        reconciliation_action="Load To IS",
        catalog_status=CatalogMatchStatus.EXACT,
        category=category,
    )
    expected = golden_decision_projection(golden)
    assert actual == {
        "catalog_status": expected["catalog_status"],
        "category_presence_status": expected["category_presence_status"],
        "recommended_action": expected["recommended_action"],
        "parent_dependency_status": expected["parent_dependency_status"],
    }


def test_missing_category_projection_matches_golden_shape():
    golden = {
        "Catalog Match Status": "EXACT MATCH",
        "Category Presence Status": "MISSING FROM CATEGORY",
        "Recommended Action": "LOAD CATEGORY AND OS",
        "Parent Dependency Status": "PARENT CATEGORY LOAD REQUIRED",
        "Candidate Set ID": "CAND-2",
    }
    category = CategoryDependencyDecision(
        serial_number="S2",
        category_presence_status="MISSING FROM CATEGORY",
        parent_dependency_status="PARENT CATEGORY LOAD REQUIRED",
        recommended_action="LOAD CATEGORY AND OS",
    )
    actual = v2_decision_projection(
        lifecycle_stage="operational",
        reconciliation_action="Load To IS",
        catalog_status=CatalogMatchStatus.EXACT,
        category=category,
    )
    expected = golden_decision_projection(golden)
    assert actual["recommended_action"] == expected["recommended_action"]
    assert actual["category_presence_status"] == expected["category_presence_status"]
    assert actual["parent_dependency_status"] == expected["parent_dependency_status"]


def test_duplicate_category_projection_is_review():
    category = CategoryDependencyDecision(
        serial_number="S3",
        category_presence_status="FOUND - DUPLICATE NORMALIZED SERIAL",
        parent_dependency_status="BLOCKED - DUPLICATE CATEGORY SERIAL",
        recommended_action="CATEGORY DATA QUALITY REVIEW",
    )
    actual = v2_decision_projection(
        lifecycle_stage="operational",
        reconciliation_action="Load To IS",
        catalog_status=CatalogMatchStatus.EXACT,
        category=category,
    )
    assert actual["recommended_action"] == "CATEGORY DATA QUALITY REVIEW"
