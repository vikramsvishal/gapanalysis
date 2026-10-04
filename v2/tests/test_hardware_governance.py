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
