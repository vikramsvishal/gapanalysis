from fastapi.testclient import TestClient
from api.main import app

client=TestClient(app)

def test_job_creation_and_lookup():
    response=client.post("/api/jobs",json={"operation":"unsupported","payload":{}})
    assert response.status_code==200
    job=response.json()
    assert job["job_id"].startswith("JOB-")
    assert job["status"] in {"QUEUED","RUNNING","FAILED"}
    found=client.get("/api/jobs/"+job["job_id"])
    assert found.status_code==200

def test_missing_job_is_404():
    assert client.get("/api/jobs/JOB-NOT-FOUND").status_code==404
