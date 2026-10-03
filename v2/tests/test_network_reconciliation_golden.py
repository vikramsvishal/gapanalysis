from __future__ import annotations

import pandas as pd

from v2.legacy_adapter import load_golden
from v2.network_reconciliation import NetworkReconciliationExecutor


class TestFieldIntelligence:
    """Small deterministic field resolver matching the production semantic names."""

    MAP = {
        ("hostname", "NW CMDB Report"): "Configuration Item",
        ("class", "NW CMDB Report"): "Class",
        ("os_lifecycle_status", "NW CMDB Report"): "Life Cycle Stage",
        ("ip_address", "NW CMDB Report"): "IP Address",
        ("fully_qualified_hostname", "NW CMDB Report"): "Fully qualified domain name",
        ("os_parent_serial_number", "NW CMDB Report"): "Serial number",
        ("os_parent_manufacturer", "NW CMDB Report"): "Manufacturer",
        ("hostname", "IS Operating System Report"): "hostname",
        ("os_parent_serial_number", "IS Operating System Report"): "os_parent_serial_number",
        ("os_lifecycle_status", "IS Operating System Report"): "os_lifecycle_status",
        ("operating_system_name", "IS Operating System Report"): "operating_system_name",
        ("operating_system_version", "IS Operating System Report"): "operating_system_version",
        ("operating_system_provider", "IS Operating System Report"): "operating_system_provider",
        ("operating_system_name", "IS Product Catalog Operating System"): "software_product_name",
        ("operating_system_version", "IS Product Catalog Operating System"): "software_version",
        ("operating_system_provider", "IS Product Catalog Operating System"): "software_provider",
    }

    def field(self, key, source, df, required=True):
        column = self.MAP.get((key, source))
        if column in df.columns:
            return column
        if required:
            raise ValueError(f"Missing mapped field: {key}/{source}")
        return None


def _inputs():
    cm = pd.DataFrame([
        {
            "Configuration Item": "SW-NEW",
            "Class": "Network Device",
            "Life Cycle Stage": "Operational",
            "IP Address": "10.0.0.1",
            "Serial number": "SN-001",
            "Manufacturer": "Cisco",
            "Firmware version": "Cisco IOS-XE 17.9.4",
            "Fully qualified domain name": "sw-new.nw.wpp.net",
            "Model ID": "M1",
            "Model.Name": "Model One",
            "Model number": "M1",
        },
        {
            "Configuration Item": "SW-EXISTING",
            "Class": "Network Device",
            "Life Cycle Stage": "Operational",
            "IP Address": "10.0.0.2",
            "Serial number": "SN-002",
            "Manufacturer": "Cisco",
            "Firmware version": "Cisco IOS-XE 17.9.4",
            "Fully qualified domain name": "sw-existing.nw.wpp.net",
            "Model ID": "M1",
            "Model.Name": "Model One",
            "Model number": "M1",
        },
        {
            "Configuration Item": "SW-EOL",
            "Class": "Network Device",
            "Life Cycle Stage": "EndOfLife",
            "IP Address": "10.0.0.3",
            "Serial number": "SN-003",
            "Manufacturer": "Cisco",
            "Firmware version": "Cisco IOS-XE 17.9.4",
            "Fully qualified domain name": "sw-eol.nw.wpp.net",
            "Model ID": "M1",
            "Model.Name": "Model One",
            "Model number": "M1",
        },
        {
            "Configuration Item": "SW-SERIAL",
            "Class": "Network Device",
            "Life Cycle Stage": "Operational",
            "IP Address": "10.0.0.4",
            "Serial number": "SN-004",
            "Manufacturer": "Cisco",
            "Firmware version": "Unknown Firmware 99.1",
            "Fully qualified domain name": "sw-serial.nw.wpp.net",
            "Model ID": "M1",
            "Model.Name": "Model One",
            "Model number": "M1",
        },
    ])
    isr = pd.DataFrame([
        {
            "hostname": "SW-EXISTING",
            "os_parent_serial_number": "SN-002",
            "os_lifecycle_status": "Production",
            "operating_system_name": "cisco ios-xe",
            "operating_system_version": "17.9.1",
            "operating_system_provider": "cisco",
            "os_opaque_id": "OS-002",
        },
        {
            "hostname": "OLD-SW",
            "os_parent_serial_number": "SN-003",
            "os_lifecycle_status": "Production",
            "operating_system_name": "cisco ios-xe",
            "operating_system_version": "17.9.4",
            "operating_system_provider": "cisco",
            "os_opaque_id": "OS-003",
        },
        {
            "hostname": "DIFFERENT-NAME",
            "os_parent_serial_number": "SN-004",
            "os_lifecycle_status": "Installed",
            "operating_system_name": "cisco ios-xe",
            "operating_system_version": "17.9.4",
            "operating_system_provider": "cisco",
            "os_opaque_id": "OS-004",
        },
    ])
    cat = pd.DataFrame([
        {
            "software_product_name": "cisco ios-xe",
            "software_version": "17.9.4",
            "software_provider": "cisco",
        }
    ])
    return cm, isr, cat, TestFieldIntelligence()


def _normalized_frame(df):
    result = df.copy()
    result = result.reindex(sorted(result.columns), axis=1)
    return result.reset_index(drop=True)


def test_v2_network_reconciliation_matches_golden_for_migration_fixture():
    golden = load_golden()
    cm, isr, cat, fi = _inputs()

    expected = golden.reconcile_nw(cm.copy(), isr.copy(), cat.copy(), fi)
    actual = NetworkReconciliationExecutor().execute(cm.copy(), isr.copy(), cat.copy(), fi)

    pd.testing.assert_frame_equal(_normalized_frame(actual), _normalized_frame(expected), check_dtype=False)


def test_v2_network_reconciliation_exercises_core_decisions():
    cm, isr, cat, fi = _inputs()
    result = NetworkReconciliationExecutor().execute(cm, isr, cat, fi)

    actions = dict(zip(result["Configuration Item"], result["Action"]))
    assert "Load To IS" in actions["SW-NEW"]
    assert "Inventory OS update required" in actions["SW-EXISTING"]
    assert actions["SW-EOL"] == "No Action" or "Retire From IS" in actions["SW-EOL"]
    assert "Catalogue update required" in actions["SW-SERIAL"]


def test_v2_firmware_catalog_normalization_matches_golden():
    golden = load_golden()
    from v2.network_reconciliation import normalize_firmware_catalog_identity

    samples = [
        "",
        "NSX-T 3.2.1",
        "NSX 22.1.5",
        "NSX 4.1.0",
        "NSX 4.2.1.4",
        "MX OS MX 18.211.5",
        "MR OS 30.7",
        "MX OS 18.107",
        "MS OS MS 15.12",
        "Infoblox NIOS 8.6.2-123456",
        "Cisco IOS-XE 17.9.4",
        "Cisco IOS 15.2(7)E3",
        "Cisco FXOS 2.12.1",
        "Cisco ASA 9.18.4",
        "Cisco NXOS 10.2.5",
        "Cisco ISE 3.2.0",
        "Cisco AireOS 8.10.185",
        "Microsoft Windows Server 2022",
        "Unknown Firmware 99.1",
    ]
    for value in samples:
        assert normalize_firmware_catalog_identity(value) == golden.normalize_firmware_catalog_identity(value)
