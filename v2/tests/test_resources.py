import pytest
from v2.resources import ResourceManager


def test_missing_resources_are_reported(tmp_path):
    manager=ResourceManager(tmp_path/"resources.json",tmp_path/"uploads")
    result=manager.resolve_requirements("reconcile_network",{})
    assert result["ready"] is False
    assert {x["kind"] for x in result["missing"]} == {"nw_cmdb","is_os","catalog_os"}


def test_upload_registers_and_resolves_resource(tmp_path):
    manager=ResourceManager(tmp_path/"resources.json",tmp_path/"uploads")
    record=manager.register_upload("nw_cmdb","network.xlsx",b"test-content")
    result=manager.resolve_requirements("reconcile_network",{"nw_cmdb":record.resource_id})
    assert record.status=="AVAILABLE"
    assert record.sha256
    assert result["ready"] is False
    assert {x["kind"] for x in result["missing"]} == {"is_os","catalog_os"}


def test_wrong_extension_is_rejected(tmp_path):
    manager=ResourceManager(tmp_path/"resources.json",tmp_path/"uploads")
    with pytest.raises(ValueError):
        manager.register_upload("field_mapping","mapping.csv",b"bad")
