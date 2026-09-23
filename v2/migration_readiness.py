"""Deterministic migration-readiness gate for shadowed V2 decisions.

This gate never changes execution authority. It only reports whether the
available evidence and human classifications support a future migration.
"""
from __future__ import annotations
from typing import Any

APPROVED = {"EQUIVALENT", "INTENTIONAL_DIFFERENCE"}
BLOCKING = {"POLICY_QUESTION", "V2_DEFECT", "NOT_YET_MIGRATABLE"}

class MigrationReadinessGate:
    def evaluate(self, shadow: dict[str, Any] | None, classifications: list[dict[str, Any]]) -> dict[str, Any]:
        if not shadow or not shadow.get("enabled", True):
            return {"status": "NOT_READY", "reason": "Shadow evidence is unavailable.", "divergence_count": 0, "unclassified_count": 0, "blocking_count": 0}
        divergences = shadow.get("mismatches") or []
        indexed = {(int(x.get("row_index", -1)), str(x.get("field", ""))): x for x in classifications}
        required = [(int(m.get("row_index", -1)), str(f)) for m in divergences for f in (m.get("differences") or {})]
        unclassified = [k for k in required if k not in indexed]
        blocking = [dict(indexed[k]) for k in required if k in indexed and indexed[k].get("status") in BLOCKING]
        approved = sum(1 for k in required if k in indexed and indexed[k].get("status") in APPROVED)
        if unclassified or blocking:
            status = "NOT_READY"
        else:
            status = "READY_FOR_AUTHORITY_REVIEW"
        return {
            "status": status,
            "authoritative_engine": shadow.get("authoritative_engine", "V1.4.1"),
            "evaluated_rows": shadow.get("row_count", 0),
            "divergence_count": len(required),
            "approved_divergence_count": approved,
            "unclassified_count": len(unclassified),
            "blocking_count": len(blocking),
            "unclassified": [{"row_index": r, "field": f} for r, f in unclassified],
            "blocking": blocking,
            "execution_authority_changed": False,
            "next_action": "Continue V1.4.1 authority until all divergences are classified as approved evidence and authority review is completed."
            if status == "NOT_READY" else
            "Evidence is sufficient for an explicit authority-migration review; this gate does not switch execution authority.",
        }
