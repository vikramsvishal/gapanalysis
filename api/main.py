""""FastAPI boundary for the local CMDB & IS Governance edition.

The API owns transport concerns only. Governance behavior remains behind
ApplicationService and the V1.4.1 compatibility seam until extracted safely.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from v2.application import ApplicationService

app = FastAPI(
    title="Enterprise Reconciliation & Recommendation Platform",
    version="2.0.0-alpha.2",
    description="Local enterprise API for governed CMDB and IS reconciliation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_service = ApplicationService()

APPLICATIONS = [
    {
        "id": "CMDB_IS_GOVERNANCE",
        "name": "CMDB & IS Governance",
        "route": "/cmdb-governance",
        "status": "ACTIVE",
        "description": "Reconcile CMDB and Inventory Services data and govern controlled load candidates.",
    },
    {
        "id": "INFRA_GAP_ANALYSIS",
        "name": "Infrastructure Gap Analysis",
        "route": "/infrastructure-gap-analysis",
        "status": "DEVELOPMENT",
        "description": "Correlate infrastructure-tool evidence with CMDB and recommend remediation.",
    },
    {
        "id": "QIR",
        "name": "Quarterly Inventory Review",
        "route": "/qir",
        "status": "DEVELOPMENT",
        "description": "Run governed quarterly inventory tests, evidence collection and sign-off.",
    },
    {
        "id": "GOVERNANCE_ANALYTICS",
        "name": "Governance Analytics",
        "route": "/governance-analytics",
        "status": "DEVELOPMENT",
        "description": "Enterprise governance metrics and trend analytics.",
    },
]

OPERATIONS = [
    {
        "id": "NW_RECONCILIATION",
        "name": "Network Reconciliation",
        "capability": "reconcile_network",
        "status": "ACTIVE",
        "description": "Compare network CMDB records against current IS inventory.",
    },
    {
        "id": "SERVER_RECONCILIATION",
        "name": "Server Reconciliation",
        "capability": "reconcile_server",
        "status": "ACTIVE",
        "description": "Identify server inventory gaps and required IS updates.",
    },
    {
        "id": "HARDWARE_GOVERNANCE",
        "name": "Hardware Governance",
        "capability": "run_hardware_governance",
        "status": "ACTIVE",
        "description": "Resolve physical devices against the authoritative IS hardware catalog.",
    },
    {
        "id": "OS_BULK_LOAD",
        "name": "OS Bulk Governance",
        "capability": "generate_bulk_load",
        "status": "ACTIVE",
        "description": "Validate operating-system candidates before controlled load generation.",
    },
]


@app.get("/api/health")
def health() -> dict[str, Any]:
    return _service.health()


@app.get("/api/applications")
def applications() -> dict[str, Any]:
    return {"items": APPLICATIONS}


@app.get("/api/governance/operations")
def operations() -> dict[str, Any]:
    return {"items": OPERATIONS}


@app.get("/api/agents")
def agents() -> dict[str, Any]:
    return {"items": list(_service.agents.names())}


@app.get("/api/resources/types")
def resource_types() -> dict[str, Any]:
    return {"items": _service.governance.resources.public_catalog()}


@app.get("/api/resources")
def resources(kind: str | None = None) -> dict[str, Any]:
    return {"items": [item.public() for item in _service.governance.resources.list(kind)]}


@app.post("/api/resources/upload")
async def upload_resource(kind: str = Form(...), file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        content = await file.read()
        record = _service.governance.resources.register_upload(kind, file.filename or "uploaded-file", content)
        return record.public()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/governance/preflight")
def governance_preflight(request: dict[str, Any]) -> dict[str, Any]:
    operation = request.get("operation")
    if not operation:
        raise HTTPException(status_code=400, detail="operation is required")
    return _service.governance.preflight(operation, request.get("payload") or {})


@app.get("/api/version")
def version() -> dict[str, str]:
    return {
        "application": _service.version,
        "golden_engine": _service.golden_version,
    }


@app.post("/api/jobs")
def create_job(request: dict[str, Any]) -> dict[str, Any]:
    operation = request.get("operation")
    if not operation:
        raise HTTPException(status_code=400, detail="operation is required")
    payload = request.get("payload") or {}
    actor = request.get("actor") or "local-user"
    if operation in {"reconcile_network", "reconcile_server", "run_hardware_governance"}:
        if not payload.get("resources"):
            raise HTTPException(
                status_code=409,
                detail={"message": "Required input resources must be loaded before starting this operation"},
            )
        check = _service.governance.preflight(operation, payload)
        if not check["ready"]:
            raise HTTPException(
                status_code=409,
                detail={"message": "Required input files are missing", "missing": check["missing"]},
            )
    job = _service.start_job(operation, payload, actor)
    return job.public()


@app.get("/api/jobs")
def list_jobs() -> dict[str, Any]:
    return {"items": [job.public() for job in _service.list_jobs()]}


@app.get("/api/results")
def list_results() -> dict[str, Any]:
    return {"items": [result.public() for result in _service.list_results()]}


@app.get("/api/results/{result_id}")
def get_result(result_id: str) -> dict[str, Any]:
    result = _service.get_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="result not found")
    return result.public()


@app.get("/api/jobs/{job_id}/result")
def get_job_result(job_id: str) -> dict[str, Any]:
    result = _service.get_job_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="result not found for job")
    return result.public()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = _service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job.public()
"