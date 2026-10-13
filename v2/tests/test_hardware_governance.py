from pathlib import Path

import pytest

from v2.hardware_governance import (
    HardwareGovernanceRequest,
    HardwareGovernanceService,
)


class FakeEngine:
    def __init__(self):
        self.calls = []

    def run_hardware_governance(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return {
            "decisions": ["d1", "d2"],
            "category_load": ["c1"],
            "candidate_ids": {"CAND-1"},
            "outputs": [{"path": "out.xlsx"}],
        }


def test_hardware_governance_domain_contract_delegates_without_reinterpretation(tmp_path: Path):
    engine = FakeEngine()
    service = HardwareGovernanceService(engine)
    request = HardwareGovernanceRequest(
        domain="network",
        cmdb_path="cmdb.xlsx",
        category_path="category.xlsx",
        catalog_path="catalog.xlsx",
        output_dir=str(tmp_path),
    )

    result = service.execute(request)

    assert result.domain == "network"
    assert result.engine == "V1.4.1"
    assert result.decision_count == 2
    assert result.category_load_count == 1
    assert result.candidate_ids == {"CAND-1"}
    assert engine.calls[0][0][:5] == (
        "network", "cmdb.xlsx", "category.xlsx", "catalog.xlsx", str(tmp_path)
    )
    assert engine.calls[0][1]["write_outputs"] is True


@pytest.mark.parametrize("domain", ["", "storage", "Network", "serverless"])
def test_hardware_governance_rejects_unknown_domain(tmp_path: Path, domain: str):
    request = HardwareGovernanceRequest(
        domain=domain,
        cmdb_path="cmdb.xlsx",
        category_path="category.xlsx",
        catalog_path="catalog.xlsx",
        output_dir=str(tmp_path),
    )
    with pytest.raises(ValueError, match="domain=network or domain=server"):
        HardwareGovernanceService(FakeEngine()).execute(request)

def test_hardware_governance_exposes_shadow_without_changing_golden(tmp_path):
    import pandas as pd
    from v2.legacy_adapter import load_golden

    cmdb = pd.DataFrame([{
        "Configuration Item": "sw01",
        "Serial number": "SN001",
        "Manufacturer": "Cisco",
        "Model number": "C9300-48P",
        "Model ID": "C9300-48P",
        "Life Cycle Stage": "Operational",
    }])
    category = pd.DataFrame([{
        "network_serial_number": "SN001",
        "network_opaque_id": "CAT-1",
        "network_lifecycle_status": "Production",
        "network_manufacturer": "Cisco",
        "network_hardware_type": "Switch",
        "network_hardware_model": "C9300-48P",
        "network_subcategory": "Access Switch",
    }])
    catalog = pd.DataFrame([{
        "manufacturer": "Cisco",
        "hardware_type": "Switch",
        "hardware_model": "C9300-48P",
        "subcategory": "Access Switch",
        "opaque_id": "HW-1",
    }])
    cmdb_path, category_path, catalog_path = [tmp_path / name for name in ("cmdb.xlsx", "category.xlsx", "catalog.xlsx")]
    cmdb.to_excel(cmdb_path, index=False)
    category.to_excel(category_path, index=False)
    catalog.to_excel(catalog_path, index=False)

    golden = load_golden()
    raw = golden.run_hardware_governance(
        "network", str(cmdb_path), str(category_path), str(catalog_path),
        str(tmp_path), lambda *_: None,
        os_reconciliation=pd.DataFrame([{"Serial number": "SN001", "Action": "Load To IS"}]),
        write_outputs=False,
    )

    class Engine:
        def run_hardware_governance(self, *args, **kwargs):
            return raw

    result = HardwareGovernanceService(Engine()).execute(
        HardwareGovernanceRequest("network", str(cmdb_path), str(category_path), str(catalog_path), str(tmp_path), False)
    )

    assert result.engine == "V1.4.1"
    assert result.decisions.equals(raw["decisions"])
    assert result.shadow["enabled"] is True
    assert result.shadow["mismatch_count"] == 0


def test_hardware_governance_sanitizes_serial_placeholders_without_mutating_sources(tmp_path):
    import pandas as pd

    cmdb_path = tmp_path / "cmdb.xlsx"
    category_path = tmp_path / "category.xlsx"
    catalog_path = tmp_path / "catalog.xlsx"
    original_cmdb = pd.DataFrame([{
        "Configuration Item": "sw01",
        "Serial number": "N/A Virtual",
        "Manufacturer": "Cisco",
        "Model number": "C9300-48P",
        "Life Cycle Stage": "Operational",
    }])
    original_category = pd.DataFrame([{
        "network_serial_number": "NA",
        "network_opaque_id": "CAT-1",
        "network_lifecycle_status": "Production",
    }])
    original_catalog = pd.DataFrame([{
        "manufacturer": "Cisco", "hardware_type": "Switch",
        "hardware_model": "C9300-48P", "subcategory": "Access Switch", "opaque_id": "HW-1",
    }])
    original_cmdb.to_excel(cmdb_path, index=False)
    original_category.to_excel(category_path, index=False)
    original_catalog.to_excel(catalog_path, index=False)

    class InspectingEngine:
        def run_hardware_governance(self, domain, cmdb, category, catalog, outdir, *args, **kwargs):
            assert domain == "network"
            assert pd.read_excel(cmdb, keep_default_na=False).loc[0, "Serial number"] == ""
            assert pd.read_excel(category, keep_default_na=False).loc[0, "network_serial_number"] == ""
            return {
                "decisions": pd.DataFrame(),
                "category_load": pd.DataFrame(),
                "candidate_ids": set(),
                "outputs": [],
            }

    request = HardwareGovernanceRequest(
        "network", str(cmdb_path), str(category_path), str(catalog_path),
        str(tmp_path / "outputs"), False,
    )
    result = HardwareGovernanceService(InspectingEngine()).execute(request)

    assert result.engine == "V1.4.1"
    assert pd.read_excel(cmdb_path).loc[0, "Serial number"] == "N/A Virtual"
    assert pd.read_excel(category_path, keep_default_na=False).loc[0, "network_serial_number"] == "NA"


def test_direct_hardware_governance_sanitizes_serial_inputs_without_mutating_sources(tmp_path):
    import pandas as pd
    from v2.services import GovernanceService

    cmdb = tmp_path / "cmdb.xlsx"
    category = tmp_path / "category.xlsx"
    pd.DataFrame([{"Configuration Item": "sw01", "Serial number": "N/A Virtual"}]).to_excel(cmdb, index=False)
    pd.DataFrame([{"network_serial_number": "NA", "network_opaque_id": "CAT-1"}]).to_excel(category, index=False)
    observed = {}

    class InspectingEngine:
        def read_tabular(self, path):
            return pd.read_excel(path)

        def run_hardware_governance(self, domain, cmdb_path, category_path, catalog_path, outdir, *args, **kwargs):
            observed["cmdb"] = pd.read_excel(cmdb_path, keep_default_na=False)
            observed["category"] = pd.read_excel(category_path, keep_default_na=False)
            return {"ok": True}

    result = GovernanceService(engine=InspectingEngine()).run_hardware_governance(
        "network", str(cmdb), str(category), str(tmp_path / "catalog.xlsx"), str(tmp_path / "out")
    )

    assert result == {"ok": True}
    assert observed["cmdb"].loc[0, "Serial number"] == ""
    assert observed["category"].loc[0, "network_serial_number"] == ""
    assert pd.read_excel(cmdb, keep_default_na=False).loc[0, "Serial number"] == "N/A Virtual"
    assert pd.read_excel(category, keep_default_na=False).loc[0, "network_serial_number"] == "NA"


def test_direct_hardware_governance_does_not_join_blank_serials(tmp_path):
    import pandas as pd
    from v2.services import GovernanceService

    reconciliation = pd.DataFrame([
        {"Configuration Item": "sw-placeholder", "Serial number": "N/A Virtual", "Action": "Load To IS"},
        {"Configuration Item": "sw-blank", "Serial number": "", "Action": "Load To IS"},
        {"Configuration Item": "sw-real", "Serial number": "SN-123", "Action": "Load To IS"},
    ])
    observed = {}

    class InspectingEngine:
        def run_hardware_governance(self, *args, **kwargs):
            frame = args[6] if len(args) > 6 else kwargs["os_reconciliation"]
            observed["frame"] = frame.copy()
            return {"ok": True}

    service = GovernanceService(engine=InspectingEngine())
    result = service.run_hardware_governance(
        "network", "missing-cmdb.xlsx", "missing-category.xlsx",
        "missing-catalog.xlsx", str(tmp_path), lambda *_: None,
        reconciliation, "missing-is-os.xlsx", False,
    )

    assert result == {"ok": True}
    assert observed["frame"]["Serial number"].tolist() == ["SN-123"]
    assert reconciliation["Serial number"].tolist() == ["N/A Virtual", "", "SN-123"]

    # Keyword invocation receives the same fail-closed protection.
    service.run_hardware_governance(
        "network", "missing-cmdb.xlsx", "missing-category.xlsx",
        "missing-catalog.xlsx", str(tmp_path), lambda *_: None,
        os_reconciliation=reconciliation,
    )
    assert observed["frame"]["Serial number"].tolist() == ["SN-123"]


def test_real_golden_engine_never_joins_placeholder_serial_to_blank_candidate(tmp_path):
    import pandas as pd
    from v2.services import GovernanceService

    cmdb_path = tmp_path / "cmdb-real.xlsx"
    category_path = tmp_path / "category-real.xlsx"
    catalog_path = tmp_path / "catalog-real.xlsx"
    pd.DataFrame([
        {
            "Configuration Item": "sw-placeholder",
            "Serial number": "N/A Virtual",
            "Manufacturer": "Cisco",
            "Model number": "C9300-48P",
            "Life Cycle Stage": "Operational",
        },
        {
            "Configuration Item": "sw-real",
            "Serial number": "SN-REAL-123",
            "Manufacturer": "Cisco",
            "Model number": "C9300-48P",
            "Life Cycle Stage": "Operational",
        },
    ]).to_excel(cmdb_path, index=False)
    pd.DataFrame([
        {
            "network_serial_number": "SN-REAL-123",
            "network_opaque_id": "CAT-REAL",
            "network_lifecycle_status": "Production",
            "network_manufacturer": "Cisco",
            "network_hardware_type": "Switch",
            "network_hardware_model": "C9300-48P",
            "network_subcategory": "Access Switch",
        },
    ]).to_excel(category_path, index=False)
    pd.DataFrame([{
        "manufacturer": "Cisco",
        "hardware_type": "Switch",
        "hardware_model": "C9300-48P",
        "subcategory": "Access Switch",
        "opaque_id": "HW-REAL",
    }]).to_excel(catalog_path, index=False)

    reconciliation = pd.DataFrame([
        {"Configuration Item": "sw-placeholder", "Serial number": "N/A Virtual", "Action": "Load To IS"},
        {"Configuration Item": "sw-blank", "Serial number": "", "Action": "Load To IS"},
        {"Configuration Item": "sw-real", "Serial number": "SN-REAL-123", "Action": "Load To IS"},
    ])
    result = GovernanceService().run_hardware_governance(
        "network", str(cmdb_path), str(category_path), str(catalog_path),
        str(tmp_path), lambda *_: None,
        os_reconciliation=reconciliation, write_outputs=False,
    )
    decisions = result["decisions"].set_index("CMDB Hostname")

    assert decisions.loc["sw-placeholder", "Reconciliation Action"] == ""
    assert decisions.loc["sw-placeholder", "Recommended Action"] == "NO LOAD ACTION"
    assert decisions.loc["sw-real", "Reconciliation Action"] == "Load To IS"
    assert decisions.loc["sw-real", "Recommended Action"] == "LOAD OS ONLY"
    assert reconciliation["Serial number"].tolist() == ["N/A Virtual", "", "SN-REAL-123"]
