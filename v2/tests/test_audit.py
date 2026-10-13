from v2.audit import AuditStore


def test_audit_is_hash_chained_and_persistent(tmp_path):
    path = tmp_path / "audit.json"
    store = AuditStore(path)
    first = store.append("RESOURCE", "user", "RESOURCE", "RES-1", "UPLOADED", {"sha256": "abc"})
    second = store.append("JOB", "user", "JOB", "JOB-1", "STARTED", {"operation": "reconcile_network"})

    assert first.event_id.startswith("AUD-")
    assert first.previous_event_hash is None
    assert second.previous_event_hash == first.event_hash
    assert len(second.event_hash) == 64

    restored = AuditStore(path)
    assert restored.get(second.event_id).event_hash == second.event_hash
    assert len(restored.for_entity("JOB", "JOB-1")) == 1


def test_audit_details_are_retained(tmp_path):
    store = AuditStore(tmp_path / "audit.json")
    event = store.append("EXCEPTION", "reviewer", "EXCEPTION", "EXC-1", "RESOLVED", {"resolution": "approved"})
    assert event.details["resolution"] == "approved"
