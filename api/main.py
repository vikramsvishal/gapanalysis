"""FastAPI boundary for the local CMDB & IS Governance edition.

The API owns transport concerns only. Governance behavior remains behind
ApplicationService and the V1.4.1 compatibility seam until extracted safely.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
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


@app.get("/api/version")
def version() -> dict[str, str]:
    return {
        "application": _service.version,
        "golden_engine": _service.golden_version,
    }
