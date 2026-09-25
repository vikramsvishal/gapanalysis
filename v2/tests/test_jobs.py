import time
from v2.jobs import JobManager

class FakeService:
    def execute_operation(self, operation, payload, progress):
        progress("Processing", 50)
        return {"operation": operation, "rows": 12}

def wait_for(manager, job_id, status):
    for _ in range(100):
        current=manager.get(job_id)
        if current and current.status==status:
            return current
        time.sleep(0.01)
    return manager.get(job_id)

def test_job_completes_and_persists(tmp_path):
    manager=JobManager(FakeService(),tmp_path/"jobs.json")
    job=manager.create("reconcile_network",{})
    current=wait_for(manager,job.job_id,"COMPLETED")
    assert current.status=="COMPLETED"
    assert current.progress==100
    assert current.result["rows"]==12
    assert (tmp_path/"jobs.json").exists()

def test_unknown_operation_is_failed_not_crash(tmp_path):
    class BadService:
        def execute_operation(self,operation,payload,progress):
            raise ValueError("unsupported")
    manager=JobManager(BadService(),tmp_path/"jobs.json")
    job=manager.create("bad",{})
    current=wait_for(manager,job.job_id,"FAILED")
    assert current.status=="FAILED"
    assert "unsupported" in current.error
