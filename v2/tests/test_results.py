from v2.results import ResultStore


def test_result_store_lifecycle(tmp_path):
    store = ResultStore(tmp_path / "results.json")
    created = store.create("JOB-1", "reconcile_network", "local-user", {"nw_cmdb": "RES-INPUT"})
    assert created.status == "RUNNING"
    completed = store.complete(created.result_id, {"rows": 3})
    assert completed.status == "COMPLETED"
    assert completed.summary["rows"] == 3
    assert store.for_job("JOB-1").result_id == created.result_id


def test_result_store_survives_restart(tmp_path):
    path = tmp_path / "results.json"
    store = ResultStore(path)
    created = store.create("JOB-2", "reconcile_server", "local-user")
    store.fail(created.result_id, {"error": "test"})
    restored = ResultStore(path)
    record = restored.get(created.result_id)
    assert record is not None
    assert record.status == "FAILED"
    assert record.summary["error"] == "test"
