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


def test_preflight_reports_exact_missing_inputs():
    response = client.post("/api/governance/preflight", json={"operation":"reconcile_network","payload":{"resources":{}}})
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is False
    assert [x["kind"] for x in data["missing"]] == ["nw_cmdb","is_os","catalog_os"]


def test_result_shadow_endpoint_exposes_persisted_diagnostics(monkeypatch):
    from types import SimpleNamespace
    from api import main

    result = SimpleNamespace(
        result_id="RES-SHADOW-1",
        summary={
            "shadow": {
                "enabled": True,
                "authoritative_engine": "V1.4.1",
                "row_count": 10,
                "match_count": 8,
                "mismatch_count": 2,
                "mismatches": [{"row_index": 3, "serial_number": "SN3", "differences": {"recommended_action": {"golden": "LOAD OS ONLY", "v2": "REVIEW"}}}],
            }
        },
        evidence_ids=["EVD-1"],
    )
    monkeypatch.setattr(main._service, "get_result", lambda result_id: result)
    monkeypatch.setattr(main._service, "get_shadow", lambda result_id: {
        "result_id": result_id,
        "authoritative_engine": "V1.4.1",
        "row_count": 10,
        "match_count": 8,
        "mismatch_count": 2,
        "mismatch_percentage": 20.0,
        "mismatches": result.summary["shadow"]["mismatches"],
        "evidence_ids": result.evidence_ids,
    })
    response = client.get("/api/results/RES-SHADOW-1/shadow")

    assert response.status_code == 200
    data = response.json()
    assert data["authoritative_engine"] == "V1.4.1"
    assert data["row_count"] == 10
    assert data["match_count"] == 8
    assert data["mismatch_count"] == 2
    assert data["mismatch_percentage"] == 20.0
    assert data["evidence_ids"] == ["EVD-1"]


def test_result_shadow_endpoint_returns_404_when_shadow_is_unavailable(monkeypatch):
    from types import SimpleNamespace
    from api import main

    monkeypatch.setattr(main._service, "get_result", lambda result_id: SimpleNamespace(result_id=result_id, summary={}, evidence_ids=[]))
    response = client.get("/api/results/RES-NO-SHADOW/shadow")

    assert response.status_code == 404
