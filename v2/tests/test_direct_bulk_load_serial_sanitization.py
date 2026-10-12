import pandas as pd

from v2.services import GovernanceService


def test_direct_generate_bulk_load_sanitizes_serial_placeholders_without_mutating_input():
    source = pd.DataFrame({
        "Configuration Item": ["sw01"],
        "Serial number": ["N/A Virtual"],
        "network_serial_number": ["NA"],
        "Manufacturer": ["Cisco"],
    })
    observed = {}

    class InspectingEngine:
        def generate_bulk_load(self, load_df, *args, **kwargs):
            observed["load_df"] = load_df.copy()
            return ["generated.xlsx"]

    result = GovernanceService(engine=InspectingEngine()).generate_bulk_load(
        source, "network", "is-os.xlsx", "template.xlsx", "out", "xlsx"
    )

    assert result == ["generated.xlsx"]
    assert observed["load_df"].loc[0, "Serial number"] == ""
    assert observed["load_df"].loc[0, "network_serial_number"] == ""
    assert source.loc[0, "Serial number"] == "N/A Virtual"
    assert source.loc[0, "network_serial_number"] == "NA"
