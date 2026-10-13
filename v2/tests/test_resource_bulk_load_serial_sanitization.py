from io import BytesIO

import pandas as pd

from v2.resources import ResourceManager
from v2.services import GovernanceService


def _xlsx_bytes(frame: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    frame.to_excel(buffer, index=False)
    return buffer.getvalue()


def test_resource_bulk_load_sanitizes_candidate_serial_before_final_generator(tmp_path):
    resources = ResourceManager(tmp_path / "resources.json", tmp_path / "uploads")
    load_source = pd.DataFrame([{
        "Configuration Item": "sw01",
        "Fully qualified domain name": "sw01.nw.wpp.net",
        "Serial number": "N/A Virtual",
        "network_serial_number": "NA",
        "Manufacturer": "Cisco",
    }])
    category_source = pd.DataFrame([{
        "network_serial_number": "NA Virtual",
        "network_opaque_id": "CAT-1",
        "network_lifecycle_status": "Production",
    }])
    is_os_source = pd.DataFrame([{"Configuration Item": "existing-os"}])
    template_source = pd.DataFrame([{"Field": "Configuration Item"}])

    load = resources.register_upload("nw_load_to_is", "load.xlsx", _xlsx_bytes(load_source))
    is_os = resources.register_upload("is_os", "is_os.xlsx", _xlsx_bytes(is_os_source))
    template = resources.register_upload("bulk_template", "template.xlsx", _xlsx_bytes(template_source))
    category = resources.register_upload("is_network_category", "category.xlsx", _xlsx_bytes(category_source))
    payload = {"domain": "network", "resources": {
        "nw_load_to_is": load.resource_id,
        "is_os": is_os.resource_id,
        "bulk_template": template.resource_id,
        "is_network_category": category.resource_id,
    }}

    observed = {}

    class InspectingEngine:
        def read_load_to_is_file(self, path, domain, progress=None):
            assert domain == "network"
            return pd.read_excel(path)

        def read_tabular(self, path):
            return pd.read_excel(path)

        def category_decisions_from_load(self, domain, load_df, category_path, *args, **kwargs):
            assert load_df.loc[0, "Serial number"] == ""
            assert load_df.loc[0, "network_serial_number"] == ""
            category_df = pd.read_excel(category_path, keep_default_na=False)
            assert category_df.loc[0, "network_serial_number"] == ""
            return {"decisions": pd.DataFrame(), "category_load": pd.DataFrame()}

        def valid_fqdn(self, value):
            return value if isinstance(value, str) and "." in value else ""

        def generate_bulk_load(self, load_df, domain, *args, **kwargs):
            observed["load_df"] = load_df.copy()
            return [{"path": "controlled-load.xlsx"}]

    result = GovernanceService(engine=InspectingEngine(), resources=resources).execute_operation(
        "generate_bulk_load", payload
    )

    assert result["status"] == "LOAD_PACKAGE_GENERATED"
    assert result["outputs"] == [{"path": "controlled-load.xlsx"}]
    assert observed["load_df"].loc[0, "Serial number"] == ""
    assert observed["load_df"].loc[0, "network_serial_number"] == ""
    # The registered source workbook remains unchanged for audit/replay.
    original_after_run = pd.read_excel(load.stored_path, keep_default_na=False)
    assert original_after_run.loc[0, "Serial number"] == "N/A Virtual"
    assert original_after_run.loc[0, "network_serial_number"] == "NA"
