from pathlib import Path

from v2.approvals import ApprovalStore, candidate_id


def test_candidate_id_is_deterministic():
    candidate = {"row_index": "7", "data": {"Host": "sw01"}}
    assert candidate_id("network", 7, candidate) == candidate_id("network", "7", candidate)


def test_approval_store_lifecycle(tmp_path: Path):
    store = ApprovalStore(tmp_path / "approvals.json")
    record = store.create(
        "RES-123",
        "network",
        "local-user",
        {"nw_load_to_is": "R1", "is_os": "R2"},
        10,
        ["CAND-1", "CAND-2"],
        candidate_snapshot_sha256="candidate-hash",
    )
    assert record.status == "PENDING_REVIEW"
    assert record.candidate_snapshot_sha256 == "candidate-hash"
    assert store.for_result("RES-123").approval_id == record.approval_id

    finalized = store.finalize(
        record.approval_id,
        "reviewer",
        {"status": "LOAD_PACKAGE_GENERATED", "approved_count": 9},
        decision_snapshot_sha256="decision-hash",
        output_sha256={"/tmp/load.xlsx": "output-hash"},
    )
    assert finalized.status == "FINALIZED"
    assert finalized.finalized_by == "reviewer"
    stored = store.get(record.approval_id)
    assert stored.final_result["approved_count"] == 9
    assert stored.decision_snapshot_sha256 == "decision-hash"
    assert stored.output_sha256["/tmp/load.xlsx"] == "output-hash"
