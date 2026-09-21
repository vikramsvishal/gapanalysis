import pandas as pd
import pytest

from v2.category_governance import CategoryDependencyGovernance


def lifecycle(value):
    value = str(value or "").strip().lower()
    return "production" if value == "production" else value


def serial_key(value):
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def category():
    return pd.DataFrame([
        {
            "network_serial_number": "N-001",
            "network_opaque_id": "OP-1",
            "network_lifecycle_status": "Production",
            "network_manufacturer": "Cisco",
            "network_hardware_type": "Router",
            "network_hardware_model": "ASR1001-X",
            "network_subcategory": "Router",
        },
        {
            "network_serial_number": "N-002",
            "network_opaque_id": "OP-2",
            "network_lifecycle_status": "Production",
        },
        {
            "network_serial_number": "N-002",
            "network_opaque_id": "OP-3",
            "network_lifecycle_status": "Production",
        },
        {
            "network_serial_number": "N-003",
            "network_opaque_id": "OP-4",
            "network_lifecycle_status": "Retired",
        },
    ])


@pytest.fixture
def gov():
    return CategoryDependencyGovernance(lifecycle, serial_key)


def test_existing_production_category_means_os_only(gov):
    d = gov.evaluate("network", "N-001", category())
    assert d.recommended_action == "LOAD OS ONLY"
    assert d.parent_dependency_status == "EXISTING PRODUCTION CATEGORY"
    assert d.category_presence_status == "FOUND IN CATEGORY"
    assert d.parent_opaque_id == "OP-1"
    assert d.category_load_required is False


def test_missing_category_requires_parent_category_load(gov):
    d = gov.evaluate("network", "N-999", category())
    assert d.recommended_action == "LOAD CATEGORY AND OS"
    assert d.parent_dependency_status == "PARENT CATEGORY LOAD REQUIRED"
    assert d.category_load_required is True


def test_duplicate_normalized_serial_requires_review(gov):
    d = gov.evaluate("network", "N-002", category())
    assert d.recommended_action == "CATEGORY DATA QUALITY REVIEW"
    assert d.parent_dependency_status == "BLOCKED - DUPLICATE CATEGORY SERIAL"
    assert d.category_presence_status == "DUPLICATE NORMALIZED SERIAL"


def test_non_operational_category_does_not_satisfy_parent_dependency(gov):
    d = gov.evaluate("network", "N-003", category())
    assert d.recommended_action == "LOAD CATEGORY AND OS"


def test_invalid_domain_is_rejected(gov):
    with pytest.raises(ValueError):
        gov.evaluate("storage", "N-001", category())
