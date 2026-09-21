import pandas as pd

from v2.hardware_governance import HardwareGovernanceService


def test_hardware_service_exposes_authoritative_catalog_resolution():
    catalog = pd.DataFrame([
        {
            "manufacturer": "Cisco",
            "hardware_type": "Router",
            "hardware_model": "ASR1001-X",
            "subcategory": "Router",
            "product_opaque_id": "CAT-1",
        }
    ])
    service = HardwareGovernanceService(engine=object())

    result = service.resolve_catalog_identity(
        catalog,
        manufacturer="Cisco",
        model="ASR1001-X",
        source_reference="CMDB:1",
        domain="network",
    )

    assert result.load_allowed is True
    assert result.catalog_record_id == "CAT-1"
    assert result.source_value == "ASR1001-X"
