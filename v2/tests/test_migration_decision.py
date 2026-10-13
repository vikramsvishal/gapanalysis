from v2.migration_decision import MigrationDecisionStore


def test_decision_requires_rationale(tmp_path):
    store = MigrationDecisionStore(tmp_path / "decisions.json")

    class Package:
        package_id = "MIG-1"
        capability = "NETWORK_RECONCILIATION"
        manifest_sha256 = "abc"
        authoritative_engine = "V1.4.1"

    try:
        store.record(Package(), "APPROVE_AUTHORITY_REVIEW", "reviewer", "")
        assert False, "expected rationale validation"
    except ValueError as exc:
        assert "rationale" in str(exc)


def test_decision_binds_to_package_hash_and_never_changes_authority(tmp_path):
    store = MigrationDecisionStore(tmp_path / "decisions.json")

    class Package:
        package_id = "MIG-1"
        capability = "NETWORK_RECONCILIATION"
        manifest_sha256 = "abc123"
        authoritative_engine = "V1.4.1"

    record = store.record(Package(), "APPROVE_AUTHORITY_REVIEW", "reviewer", "Evidence reviewed.")
    assert record.package_manifest_sha256 == "abc123"
    assert record.authority_changed is False
    assert record.authoritative_engine_before == "V1.4.1"
    assert record.decision_sha256


def test_decisions_survive_reload(tmp_path):
    path = tmp_path / "decisions.json"
    store = MigrationDecisionStore(path)

    class Package:
        package_id = "MIG-1"
        capability = None
        manifest_sha256 = "abc"
        authoritative_engine = "V1.4.1"

    record = store.record(Package(), "DEFER", "reviewer", "Need more evidence.")
    reloaded = MigrationDecisionStore(path)
    assert reloaded.get(record.decision_id).package_id == "MIG-1"
