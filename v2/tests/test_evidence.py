from v2.evidence import EvidenceStore


class Resource:
    resource_id = "RES-INPUT"
    kind = "nw_cmdb"
    file_name = "network.xlsx"
    sha256 = "abc123"
    size = 42
    status = "AVAILABLE"


def test_capture_resource_is_hash_backed_and_persistent(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.json")
    item = store.capture_resource("RES-RESULT", Resource())
    assert item.evidence_id.startswith("EVD-")
    assert item.sha256 == "abc123"
    assert item.source_id == "RES-INPUT"

    restored = EvidenceStore(tmp_path / "evidence.json")
    assert restored.get(item.evidence_id).source_name == "network.xlsx"
    assert len(restored.for_result("RES-RESULT")) == 1


def test_text_evidence_uses_sha256(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.json")
    item = store.capture_text("RES-RESULT", "decision_note", "NOTE-1", "note", "approved")
    assert len(item.sha256) == 64
    assert store.get(item.evidence_id).metadata["length"] == 8
