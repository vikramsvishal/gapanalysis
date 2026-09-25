"""Deterministic migration-readiness gates, including capability scope."""
from __future__ import annotations
from collections import defaultdict
from typing import Any

APPROVED = {"EQUIVALENT", "INTENTIONAL_DIFFERENCE"}
BLOCKING = {"POLICY_QUESTION", "V2_DEFECT", "NOT_YET_MIGRATABLE"}

def capability(operation: str, domain: str = "") -> str:
    key = f"{operation}:{domain}".upper()
    return {
        "RECONCILE_NETWORK:NETWORK": "NETWORK_RECONCILIATION",
        "RECONCILE_SERVER:SERVER": "SERVER_RECONCILIATION",
        "RUN_HARDWARE_GOVERNANCE:NETWORK": "NETWORK_HARDWARE_GOVERNANCE",
        "RUN_HARDWARE_GOVERNANCE:SERVER": "SERVER_HARDWARE_GOVERNANCE",
        "GENERATE_BULK_LOAD:NETWORK": "NETWORK_OS_BULK_LOAD",
        "GENERATE_BULK_LOAD:SERVER": "SERVER_OS_BULK_LOAD",
    }.get(key, operation.upper() or "UNKNOWN")

class MigrationReadinessGate:
    def evaluate(self, shadow: dict[str, Any] | None, classifications: list[dict[str, Any]]) -> dict[str, Any]:
        if not shadow or not shadow.get("enabled", True):
            return {"status": "NOT_READY", "reason": "Shadow evidence is unavailable.", "divergence_count": 0, "unclassified_count": 0, "blocking_count": 0, "execution_authority_changed": False}
        divergences = shadow.get("mismatches") or []
        indexed = {(int(x.get("row_index", -1)), str(x.get("field", ""))): x for x in classifications}
        required = [(int(m.get("row_index", -1)), str(f)) for m in divergences for f in (m.get("differences") or {})]
        unclassified = [k for k in required if k not in indexed]
        blocking = [dict(indexed[k]) for k in required if k in indexed and indexed[k].get("status") in BLOCKING]
        approved = sum(1 for k in required if k in indexed and indexed[k].get("status") in APPROVED)
        status = "NOT_READY" if unclassified or blocking else "READY_FOR_AUTHORITY_REVIEW"
        return {"status": status, "authoritative_engine": shadow.get("authoritative_engine", "V1.4.1"),
                "evaluated_rows": shadow.get("row_count", 0), "divergence_count": len(required),
                "approved_divergence_count": approved, "unclassified_count": len(unclassified),
                "blocking_count": len(blocking), "unclassified": [{"row_index": r, "field": f} for r, f in unclassified],
                "blocking": blocking, "execution_authority_changed": False,
                "next_action": "Continue V1.4.1 authority until all divergences are classified as approved evidence and authority review is completed."
                if status == "NOT_READY" else
                "Evidence is sufficient for an explicit authority-migration review; this gate does not switch execution authority."}

    def evaluate_capabilities(self, results: list[Any], shadow_by_result: dict[str, dict[str, Any]], classifications_by_result: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for result in results:
            key = capability(result.operation, str((result.inputs or {}).get("domain", "")))
            grouped[key].append(self.evaluate(shadow_by_result.get(result.result_id), classifications_by_result.get(result.result_id, [])))
        items = []
        for name, gates in sorted(grouped.items()):
            items.append({"capability": name,
                          "status": "READY_FOR_AUTHORITY_REVIEW" if gates and all(g["status"] == "READY_FOR_AUTHORITY_REVIEW" for g in gates) else "NOT_READY",
                          "result_count": len(gates), "divergence_count": sum(g["divergence_count"] for g in gates),
                          "blocking_count": sum(g["blocking_count"] for g in gates), "unclassified_count": sum(g["unclassified_count"] for g in gates)})
        return {"authoritative_engine": "V1.4.1", "capabilities": items, "execution_authority_changed": False}
