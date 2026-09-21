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
