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
