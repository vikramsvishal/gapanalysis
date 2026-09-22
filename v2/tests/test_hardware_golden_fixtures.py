import pandas as pd

from v2.hardware_equivalence import golden_decision_projection, v2_decision_projection
from v2.category_governance import CategoryDependencyGovernance
from v2.catalog_resolution import AuthoritativeHardwareCatalogResolver, CatalogResolutionRequest


def _catalog(model="C9300-48P", manufacturer="Cisco", opaque="HW-1"):
    return pd.DataFrame([
        {
            "manufacturer": manufacturer,
            "hardware_type": "Switch",
            "hardware_model": model,
            "subcategory": "Access Switch",
            "opaque_id": opaque,
        }
    ])


def _cmdb(lifecycle_stage="Operational", model="C9300-48P", serial="SN001", manufacturer="Cisco"):
    return pd.DataFrame([
        {
            "Configuration Item": "sw01",
            "Serial number": serial,
            "Manufacturer": manufacturer,
            "Model number": model,
            "Model ID": model,
            "Life Cycle Stage": lifecycle_stage,
        }
    ])


def _category(rows):
    columns = list(_category_row().keys())
    return pd.DataFrame(rows, columns=columns)


def _reconciliation(serial="SN001"):
    return pd.DataFrame([
        {"Serial number": serial, "Action": "Load To IS"}
    ])


def _golden(domain, tmp_path, category, catalog=None, lifecycle_stage="Operational",
            model="C9300-48P", serial="SN001"):
    from v2.legacy_adapter import load_golden

    golden = load_golden()
    cmdb_path = tmp_path / f"{domain}-cmdb.xlsx"
    category_path = tmp_path / f"{domain}-category.xlsx"
    catalog_path = tmp_path / f"{domain}-catalog.xlsx"

    _cmdb(lifecycle_stage, model, serial).to_excel(cmdb_path, index=False)
    category.to_excel(category_path, index=False)
    (catalog if catalog is not None else _catalog(model=model)).to_excel(catalog_path, index=False)

    return golden.run_hardware_governance(
        domain,
        str(cmdb_path),
        str(category_path),
        str(catalog_path),
        str(tmp_path),
        lambda *_: None,
        os_reconciliation=_reconciliation(serial),
        write_outputs=False,
    )


def _category_row(serial="SN001", opaque="CAT-1"):
    return {
        "network_serial_number": serial,
        "network_opaque_id": opaque,
        "network_lifecycle_status": "Production",
        "network_manufacturer": "Cisco",
        "network_hardware_type": "Switch",
        "network_hardware_model": "C9300-48P",
        "network_subcategory": "Access Switch",
    }


def test_golden_existing_category_is_load_os_only(tmp_path):
    raw = _golden(
        "network",
        tmp_path,
        _category([_category_row()]),
    )
    record = raw["decisions"].iloc[0].to_dict()
    projection = golden_decision_projection(record)

    assert projection["catalog_status"] == "EXACT MATCH"
    assert projection["category_presence_status"] == "FOUND IN CATEGORY"
    assert projection["recommended_action"] == "LOAD OS ONLY"
    assert projection["parent_dependency_status"] == "EXISTING PRODUCTION CATEGORY"


def test_golden_missing_category_requires_category_and_os(tmp_path):
    raw = _golden(
        "network",
        tmp_path,
        _category([]),
    )
    record = raw["decisions"].iloc[0].to_dict()
    projection = golden_decision_projection(record)

    assert projection["catalog_status"] == "EXACT MATCH"
    assert projection["category_presence_status"] == "MISSING FROM CATEGORY"
    assert projection["recommended_action"] == "LOAD CATEGORY AND OS"
    assert projection["parent_dependency_status"] == "PARENT CATEGORY LOAD REQUIRED"


def test_golden_duplicate_category_requires_review(tmp_path):
    raw = _golden(
        "network",
        tmp_path,
        _category([_category_row("SN001", "CAT-1"), _category_row("SN001", "CAT-2")]),
    )
    record = raw["decisions"].iloc[0].to_dict()
    projection = golden_decision_projection(record)

    assert projection["category_presence_status"] == "FOUND - DUPLICATE NORMALIZED SERIAL"
    assert projection["recommended_action"] == "CATEGORY DATA QUALITY REVIEW"
    assert projection["parent_dependency_status"] == "NOT APPLICABLE"


def test_golden_non_operational_has_no_load_action(tmp_path):
    raw = _golden(
        "network",
        tmp_path,
        _category([_category_row()]),
        lifecycle_stage="End of Life",
    )
    record = raw["decisions"].iloc[0].to_dict()
    projection = golden_decision_projection(record)

    assert projection["recommended_action"] == "NO LOAD ACTION"
    assert projection["parent_dependency_status"] == "NOT APPLICABLE"


def test_golden_non_exact_catalog_does_not_override_category_recommendation(tmp_path):
    catalog = _catalog(model="C9300-48X", opaque="HW-2")
    raw = _golden(
        "network",
        tmp_path,
        _category([_category_row()]),
        catalog=catalog,
    )
    record = raw["decisions"].iloc[0].to_dict()
    projection = golden_decision_projection(record)

    assert projection["catalog_status"] != "EXACT MATCH"
    assert projection["recommended_action"] == "LOAD OS ONLY"


def _v2_shadow_projection(domain, category, catalog, model="C9300-48P", serial="SN001", lifecycle_stage="Operational"):
    from v2.legacy_adapter import load_golden
    golden = load_golden()
    category_governance = CategoryDependencyGovernance(golden.lifecycle, golden.serial_key)
    category_decision = category_governance.evaluate(domain, serial, category)
    catalog_resolution = AuthoritativeHardwareCatalogResolver(catalog).resolve(
        CatalogResolutionRequest(domain=domain, manufacturer="Cisco", model=model, source_reference="fixture")
    )
    return v2_decision_projection(
        lifecycle_stage=golden.lifecycle(lifecycle_stage),
        reconciliation_action="Load To IS",
        catalog_status=catalog_resolution.status,
        category=category_decision,
    )

def test_shadow_exact_existing_category_matches_golden(tmp_path):
    category = _category([_category_row()])
    catalog = _catalog()
    golden = _golden("network", tmp_path, category, catalog=catalog)
    expected = golden_decision_projection(golden["decisions"].iloc[0].to_dict())
    actual = _v2_shadow_projection("network", category, catalog)
    assert actual["catalog_status"] == expected["catalog_status"]
    assert actual["category_presence_status"] == expected["category_presence_status"]
    assert actual["recommended_action"] == expected["recommended_action"]
    assert actual["parent_dependency_status"] == expected["parent_dependency_status"]

def test_shadow_exact_missing_category_matches_golden(tmp_path):
    category = _category([])
    catalog = _catalog()
    golden = _golden("network", tmp_path, category, catalog=catalog)
    expected = golden_decision_projection(golden["decisions"].iloc[0].to_dict())
    actual = _v2_shadow_projection("network", category, catalog)
    assert actual["catalog_status"] == expected["catalog_status"]
    assert actual["category_presence_status"] == expected["category_presence_status"]
    assert actual["recommended_action"] == expected["recommended_action"]
    assert actual["parent_dependency_status"] == expected["parent_dependency_status"]

def test_shadow_exact_duplicate_category_matches_golden(tmp_path):
    category = _category([_category_row("SN001", "CAT-1"), _category_row("SN001", "CAT-2")])
    catalog = _catalog()
    golden = _golden("network", tmp_path, category, catalog=catalog)
    expected = golden_decision_projection(golden["decisions"].iloc[0].to_dict())
    actual = _v2_shadow_projection("network", category, catalog)
    assert actual["catalog_status"] == expected["catalog_status"]
    assert actual["category_presence_status"] == expected["category_presence_status"]
    assert actual["recommended_action"] == expected["recommended_action"]
    assert actual["parent_dependency_status"] == expected["parent_dependency_status"]

def test_shadow_non_exact_catalog_is_explicitly_divergent(tmp_path):
    category = _category([_category_row()])
    catalog = _catalog(model="C9300-48X", opaque="HW-2")
    golden = _golden("network", tmp_path, category, catalog=catalog)
    expected = golden_decision_projection(golden["decisions"].iloc[0].to_dict())
    actual = _v2_shadow_projection("network", category, catalog)
    assert expected["recommended_action"] == "LOAD OS ONLY"
    assert actual["recommended_action"] == "CATALOG UPDATE REQUIRED"
    assert expected["recommended_action"] != actual["recommended_action"]
