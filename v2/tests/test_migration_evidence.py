from pathlib import Path

from v2.migration_evidence import MigrationEvidencePackStore


def _store(tmp_path: Path) -> MigrationEvidencePackStore:
    return MigrationEvidencePackStore(tmp_path / "packs.json")


def _inputs():
    return dict(
        scope="CAPABILITY",
        capability="NETWORK_HARDWARE_GOVERNANCE",
        result_ids=["RES-2", "RES-1"],
        shadow_evidence_ids=["E-2", "E-1"],
        classification_ids=["C-2", "C-1"],
        audit_event_ids=["A-2", "A-1"],
        readiness={
            "capability": "NETWORK_HARDWARE_GOVERNANCE",
            "status": "READY_FOR_AUTHORITY_REVIEW",
            "divergence_count": 0,
        },
        manifest={
            "results": [{"result_id": "RES-1"}],
            "shadows": {"RES-1": {"enabled": True, "mismatch_count": 0}},
            "classifications": {"RES-1": []},
            "readiness": {"status": "READY_FOR_AUTHORITY_REVIEW"},
            "audit": [{"event_id": "A-1"}],
        },
    )


def test_pack_is_persisted_and_manifest_hash_is_content_addressed(tmp_path):
    store = _store(tmp_path)
    first = store.create(**_inputs())
    second = store.create(**_inputs())

    assert first.package_id != second.package_id
    assert first.manifest_sha256 == second.manifest_sha256
    assert store.get(first.package_id).public()["manifest_sha256"] == first.manifest_sha256
    assert store.manifest(first.package_id)["capability"] == "NETWORK_HARDWARE_GOVERNANCE"


def test_pack_normalizes_reference_order_before_hashing(tmp_path):
    store = _store(tmp_path)
    a = _inputs()
    b = _inputs()
    b["result_ids"] = ["RES-1", "RES-2"]
    b["shadow_evidence_ids"] = ["E-1", "E-2"]
    b["classification_ids"] = ["C-1", "C-2"]
    b["audit_event_ids"] = ["A-1", "A-2"]

    one = store.create(**a)
    two = store.create(**b)

    assert one.manifest_sha256 == two.manifest_sha256


def test_pack_survives_reload(tmp_path):
    path = tmp_path / "packs.json"
    store = MigrationEvidencePackStore(path)
    record = store.create(**_inputs())

    reloaded = MigrationEvidencePackStore(path)
    assert reloaded.get(record.package_id) is not None
    assert reloaded.manifest(record.package_id)["scope"] == "CAPABILITY"
