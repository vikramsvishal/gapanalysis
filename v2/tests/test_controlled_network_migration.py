from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from v2.authority import AuthorityStore, DEFAULT_ENGINE, V2_ENGINE
from v2.execution_router import ExecutionRouter
from v2.evidence import EvidenceStore
from v2.legacy_adapter import load_golden
from v2.migration_decision import MigrationDecisionStore
from v2.migration_evidence import MigrationEvidencePackStore
from v2.migration_readiness import MigrationReadinessGate
from v2.network_reconciliation import NetworkReconciliationExecutor
from v2.shadow_evidence import shadow_fingerprint

from test_network_reconciliation_golden import _inputs


class _Resources:
    def __init__(self):
        self.items = {
            "NW-CMDB": SimpleNamespace(sha256="a" * 64, status="READY"),
            "IS-OS": SimpleNamespace(sha256="b" * 64, status="READY"),
            "CAT-OS": SimpleNamespace(sha256="c" * 64, status="READY"),
        }

    def get(self, resource_id):
        return self.items.get(resource_id)


def _shadow(resources, resource_ids, golden_result, v2_result, evidence_id):
    differences = []
    columns = sorted(set(golden_result.columns) | set(v2_result.columns))
    max_rows = max(len(golden_result), len(v2_result))
    for row_index in range(max_rows):
        row_diff = {}
        for column in columns:
            left = golden_result.iloc[row_index][column] if row_index < len(golden_result) and column in golden_result.columns else None
            right = v2_result.iloc[row_index][column] if row_index < len(v2_result) and column in v2_result.columns else None
            if pd.isna(left) and pd.isna(right):
                continue
            if str(left) != str(right):
                row_diff[column] = {"golden": str(left), "v2": str(right)}
        if row_diff:
            differences.append({"row_index": row_index, "differences": row_diff})
    return {
        "enabled": True,
        "authoritative_engine": DEFAULT_ENGINE,
        "candidate_engine": V2_ENGINE,
        "row_count": max_rows,
        "match_count": max_rows - len(differences),
        "mismatch_count": len(differences),
        "mismatches": differences,
        "fingerprints": shadow_fingerprint(resources, resource_ids, golden_result, v2_result),
        "evidence_ids": [evidence_id],
    }


def test_controlled_network_migration_simulation_is_repeatable(tmp_path):
    # Use the same representative network fixture for both engines.
    cm, isr, cat, fi = _inputs()
    golden = load_golden()
    v2 = NetworkReconciliationExecutor()
    authoritative = golden.reconcile_nw(cm.copy(), isr.copy(), cat.copy(), fi)
    candidate = v2.execute(cm.copy(), isr.copy(), cat.copy(), fi)

    pd.testing.assert_frame_equal(
        authoritative.reindex(sorted(authoritative.columns), axis=1).reset_index(drop=True),
        candidate.reindex(sorted(candidate.columns), axis=1).reset_index(drop=True),
        check_dtype=False,
    )

    resources = _Resources()
    resource_ids = {"nw_cmdb": "NW-CMDB", "is_os": "IS-OS", "catalog_os": "CAT-OS"}
    evidence = EvidenceStore(tmp_path / "evidence.json")
    result_id = "RES-SIM-NETWORK"
    provisional_shadow = {
        "fingerprints": shadow_fingerprint(resources, resource_ids, authoritative, candidate)
    }
    shadow_record = evidence.capture_text(
        result_id,
        "RECONCILE_NETWORK_SHADOW",
        result_id,
        "network-shadow.json",
        str(provisional_shadow),
    )
    shadow = _shadow(resources, resource_ids, authoritative, candidate, shadow_record.evidence_id)

    readiness = MigrationReadinessGate().evaluate(
        shadow, [], "NETWORK_RECONCILIATION"
    )
    assert readiness["status"] == "READY_FOR_AUTHORITY_REVIEW"
    assert readiness["execution_authority_changed"] is False

    packs = MigrationEvidencePackStore(tmp_path / "migration-evidence.json")
    package = packs.create(
        scope="CAPABILITY",
        capability="NETWORK_RECONCILIATION",
        result_ids=[result_id],
        shadow_evidence_ids=[shadow_record.evidence_id],
        classification_ids=[],
        audit_event_ids=[],
        readiness=readiness,
        manifest={
            "shadow_fingerprints": {result_id: shadow["fingerprints"]},
            "runtime_shadow_evidence_ids": [shadow_record.evidence_id],
        },
    )
    assert packs.verify_integrity(package.package_id) == (True, "")

    decisions = MigrationDecisionStore(tmp_path / "decisions.json")
    decision = decisions.record(
        package,
        "APPROVE_AUTHORITY_REVIEW",
        "simulation-reviewer",
        "Representative network shadow evidence is equivalent and integrity-verified.",
    )
    assert decisions.verify_integrity(decision.decision_id) == (True, "")

    authority = AuthorityStore(
        decisions, packs, tmp_path / "authority.json"
    )
    router = ExecutionRouter(
        authority,
        lambda operation, payload, **kwargs: "V1-RESULT",
        {"NETWORK_RECONCILIATION": lambda operation, payload, **kwargs: "V2-RESULT"},
    )

    assert authority.get("NETWORK_RECONCILIATION").engine == DEFAULT_ENGINE
    assert router.route("reconcile_network").engine == DEFAULT_ENGINE

    activated = authority.activate(
        "NETWORK_RECONCILIATION",
        decision.decision_id,
        "simulation-operator",
        "Controlled migration simulation only; isolated temporary authority state.",
    )
    assert activated.engine == V2_ENGINE
    assert activated.evidence_package_id == package.package_id
    assert router.route("reconcile_network").engine == V2_ENGINE
    assert router.execute("reconcile_network") == "V2-RESULT"

    rolled_back = authority.rollback(
        "NETWORK_RECONCILIATION",
        "simulation-operator",
        "Controlled rollback validation after simulated activation.",
    )
    assert rolled_back.engine == DEFAULT_ENGINE
    assert router.route("reconcile_network").engine == DEFAULT_ENGINE
    assert router.execute("reconcile_network") == "V1-RESULT"
