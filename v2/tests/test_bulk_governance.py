from v2.resources import OPERATION_REQUIREMENTS, RESOURCE_TYPES, ResourceManager


def test_os_bulk_load_requirements_are_domain_specific():
    assert OPERATION_REQUIREMENTS["generate_bulk_load_network"] == ["nw_load_to_is", "is_os", "bulk_template", "is_network_category"]
    assert OPERATION_REQUIREMENTS["generate_bulk_load_server"] == ["server_load_to_is", "is_os", "bulk_template", "is_server_category"]


def test_os_bulk_load_resources_are_exposed():
    assert "nw_load_to_is" in RESOURCE_TYPES
    assert "server_load_to_is" in RESOURCE_TYPES
    manager = ResourceManager()
    catalog = {x["kind"] for x in manager.public_catalog()}
    assert {"nw_load_to_is", "server_load_to_is", "bulk_template"} <= catalog


def test_os_bulk_preflight_reports_missing_resources(tmp_path):
    manager = ResourceManager(tmp_path / "resources.json", tmp_path / "uploads")
    result = manager.resolve_requirements("generate_bulk_load_network", {})
    assert result["ready"] is False
    assert {x["kind"] for x in result["missing"]} == {"nw_load_to_is", "is_os", "bulk_template", "is_network_category"}
