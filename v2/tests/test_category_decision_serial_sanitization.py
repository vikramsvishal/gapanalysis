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


def test_server_category_serial_number_alias_is_sanitized_without_mutating_input():
    import pandas as pd
    from v2.normalization import sanitize_serial_placeholders

    source = pd.DataFrame({
        "serial_number": ["N/A Virtual", "SN-123"],
        "description": ["NA", "real description"],
    })

    sanitized = sanitize_serial_placeholders(source)

    assert sanitized["serial_number"].tolist() == ["", "SN-123"]
    assert sanitized["description"].tolist() == ["NA", "real description"]
    assert source["serial_number"].tolist() == ["N/A Virtual", "SN-123"]


def test_server_category_decisions_sanitize_serial_number_column(tmp_path: Path):
    category_path = tmp_path / "server_category.xlsx"
    pd.DataFrame([{
        "serial_number": "N/A Virtual",
        "server_opaque_id": "SERVER-CAT-1",
        "server_lifecycle_status": "Production",
    }]).to_excel(category_path, index=False)
    load_df = pd.DataFrame([{
        "Configuration Item": "server01",
        "Serial number": "NA",
        "Manufacturer": "Dell",
    }])

    class InspectingEngine:
        def read_tabular(self, path):
            return pd.read_excel(path)

        def category_decisions_from_load(self, domain, candidates, category_file, *args, **kwargs):
            assert domain == "server"
            assert candidates.loc[0, "Serial number"] == ""
            category = pd.read_excel(category_file, keep_default_na=False)
            assert category.loc[0, "serial_number"] == ""
            assert category.loc[0, "server_opaque_id"] == "SERVER-CAT-1"
            return {"decisions": pd.DataFrame(), "category_load": pd.DataFrame()}

    result = GovernanceService(engine=InspectingEngine()).category_decisions_from_load(
        "server", load_df, str(category_path)
    )

    assert "decisions" in result
    assert load_df.loc[0, "Serial number"] == "NA"
    assert pd.read_excel(category_path, keep_default_na=False).loc[0, "serial_number"] == "N/A Virtual"
