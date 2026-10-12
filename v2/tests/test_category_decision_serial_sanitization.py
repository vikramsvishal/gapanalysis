from pathlib import Path

import pandas as pd

from v2.services import GovernanceService


def test_category_decisions_sanitize_load_and_category_serial_placeholders(tmp_path: Path):
    category_path = tmp_path / "category.xlsx"
    original_category = pd.DataFrame([{
        "network_serial_number": "NA Virtual",
        "network_opaque_id": "CAT-1",
        "network_lifecycle_status": "Production",
    }])
    original_category.to_excel(category_path, index=False)
    candidate_frame = pd.DataFrame([{
        "Configuration Item": "sw01",
        "Serial number": "N/A",
        "Manufacturer": "Cisco",
    }])

    class InspectingEngine:
        def read_tabular(self, path):
            return pd.read_excel(path)

        def category_decisions_from_load(self, domain, load_df, category_file, *args, **kwargs):
            assert domain == "network"
            assert load_df.loc[0, "Serial number"] == ""
            category = pd.read_excel(category_file, keep_default_na=False)
            assert category.loc[0, "network_serial_number"] == ""
            return {"decisions": pd.DataFrame(), "category_load": pd.DataFrame()}

    result = GovernanceService(engine=InspectingEngine()).category_decisions_from_load(
        "network", candidate_frame, str(category_path)
    )

    assert "decisions" in result
    assert candidate_frame.loc[0, "Serial number"] == "N/A"
    assert pd.read_excel(category_path, keep_default_na=False).loc[0, "network_serial_number"] == "NA Virtual"
