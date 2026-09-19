from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_health_endpoint_exposes_golden_engine():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "READY"
    assert data["golden_version"] == "1.4.1"


def test_operations_endpoint_exposes_active_capabilities():
    response = client.get("/api/governance/operations")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert {"NW_RECONCILIATION", "SERVER_RECONCILIATION", "HARDWARE_GOVERNANCE", "OS_BULK_LOAD"} <= ids


def test_applications_endpoint_exposes_dormant_future_apps():
    response = client.get("/api/applications")
    assert response.status_code == 200
    apps = {item["id"]: item["status"] for item in response.json()["items"]}
    assert apps["CMDB_IS_GOVERNANCE"] == "ACTIVE"
    assert apps["INFRA_GAP_ANALYSIS"] == "DEVELOPMENT"
    assert apps["QIR"] == "DEVELOPMENT"
