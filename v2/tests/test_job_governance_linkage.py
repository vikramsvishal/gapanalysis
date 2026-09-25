from v2.jobs import JobManager


class FakeResultStore:
    def __init__(self, exception_store, audit_store):
        self.evidence_store = None
        self.exception_store = exception_store
        self.audit_store = audit_store


def test_job_manager_accepts_governance_stores(tmp_path):
    manager = JobManager(object(), tmp_path / "jobs.json", result_store=None, exception_store=object(), audit_store=object())
    assert manager.exception_store is not None
    assert manager.audit_store is not None


def test_hardware_shadow_is_persisted_as_evidence_and_audit(tmp_path):
    import pandas as pd
    from v2.evidence import EvidenceStore
    from v2.results import ResultStore
    from v2.audit import AuditStore
    from v2.jobs import JobManager

    class Resource:
        def __init__(self):
            self.resource_id = "RES-1"; self.kind = "nw_cmdb"; self.file_name = "cmdb.xlsx"
            self.sha256 = "abc"; self.size = 1; self.status = "AVAILABLE"

    class Resources:
        def get(self, _): return Resource()

    shadow = {
        "enabled": True, "authoritative_engine": "V1.4.1",
        "row_count": 1, "match_count": 1, "mismatch_count": 0, "mismatches": [],
    }

    class Service:
        resources = Resources()
        def execute_operation(self, operation, payload, progress=None):
            return {"domain": "network", "shadow": shadow, "outputs": []}

    evidence = EvidenceStore(tmp_path / "evidence.json")
    results = ResultStore(tmp_path / "results.json", evidence_store=evidence)
    audit = AuditStore(tmp_path / "audit.json")
    manager = JobManager(
        Service(),
        state_path=tmp_path / "jobs.json",
        result_store=results,
        audit_store=audit,
    )
    job = manager.create("run_hardware_governance", {"resources": {"nw_cmdb": "RES-1"}})
    import time
    for _ in range(100):
        current = manager.get(job.job_id)
        if current.status in {"COMPLETED", "FAILED"}:
            break
        time.sleep(0.01)

    assert current.status == "COMPLETED"
    result = results.for_job(job.job_id)
    assert result is not None
    assert any(x.kind == "HARDWARE_GOVERNANCE_SHADOW" for x in evidence.for_result(result.result_id))
    assert any(x.event_type == "SHADOW_ANALYSIS" and x.entity_id == result.result_id for x in audit.list())
