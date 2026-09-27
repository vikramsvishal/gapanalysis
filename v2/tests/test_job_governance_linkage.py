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


def test_network_shadow_persists_canonical_fingerprints(tmp_path):
    import pandas as pd
    import time
    from v2.evidence import EvidenceStore
    from v2.results import ResultStore
    from v2.audit import AuditStore
    from v2.jobs import JobManager
    from v2.authority import AuthorityStore
    from v2.execution_router import ExecutionRouter
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore

    class Resource:
        resource_id = "RES-NW"
        kind = "nw_cmdb"
        file_name = "network.xlsx"
        sha256 = "network-input-sha"
        size = 123
        status = "AVAILABLE"

    class Resources:
        def get(self, resource_id):
            return Resource() if resource_id == "RES-NW" else None

    frame = pd.DataFrame([{"Configuration Item": "SW-1", "Action": "Load To IS"}])

    class Service:
        resources = Resources()

    authority = AuthorityStore(
        MigrationDecisionStore(tmp_path / "decisions.json"),
        MigrationEvidencePackStore(tmp_path / "evidence-packs.json"),
        tmp_path / "authority.json",
    )
    router = ExecutionRouter(
        authority,
        lambda operation, payload, progress=None: frame.copy(),
        v2_executors={"NETWORK_RECONCILIATION": lambda operation, payload, progress=None: frame.copy()},
    )
    evidence = EvidenceStore(tmp_path / "evidence.json")
    results = ResultStore(tmp_path / "results.json", evidence_store=evidence)
    audit = AuditStore(tmp_path / "audit.json")
    manager = JobManager(
        Service(),
        state_path=tmp_path / "jobs.json",
        result_store=results,
        audit_store=audit,
        execution_router=router,
    )

    job = manager.create("reconcile_network", {"resources": {"nw_cmdb": "RES-NW"}})
    for _ in range(100):
        current = manager.get(job.job_id)
        if current.status in {"COMPLETED", "FAILED"}:
            break
        time.sleep(0.01)

    assert current.status == "COMPLETED"
    result = results.for_job(job.job_id)
    assert result is not None
    shadow_records = [
        item for item in evidence.for_result(result.result_id)
        if item.kind == "RECONCILE_NETWORK_SHADOW"
    ]
    assert len(shadow_records) == 1
    payload = shadow_records[0].metadata
    assert payload["sha256"]
    assert result.summary["shadow"]["fingerprints"]["input_sha256"] == "c7b1d4b2c0b8c1e6a9b0e7e1e8a3b5e2e2a8c6b5d5a0c7d0b1f6f6b0d2a9a5b3"
