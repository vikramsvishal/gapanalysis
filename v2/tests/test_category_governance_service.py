import pandas as pd

from v2.hardware_governance import HardwareGovernanceService


def test_service_exposes_category_dependency_resolution():
    category = pd.DataFrame([
        {
            "network_serial_number": "N-1",
            "network_opaque_id": "OP-1",
            "network_lifecycle_status": "Production",
        }
    ])

    result = HardwareGovernanceService(object()).resolve_category_dependency(
        "network", "N-1", category
    )

    assert result.recommended_action == "LOAD OS ONLY"
    assert result.parent_opaque_id == "OP-1"
