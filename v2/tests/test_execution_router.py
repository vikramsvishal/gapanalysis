from v2.authority import AuthorityStore
from v2.execution_router import ExecutionRouter, capability_for


def test_capability_mapping_is_domain_specific():
    assert capability_for("reconcile_network") == "NETWORK_RECONCILIATION"
    assert capability_for("run_hardware_governance", {"domain": "server"}) == "SERVER_HARDWARE_GOVERNANCE"
    assert capability_for("generate_bulk_load", {"domain": "network"}) == "NETWORK_OS_BULK_LOAD"


def test_default_route_executes_v1(tmp_path):
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore

    authority = AuthorityStore(
        MigrationDecisionStore(tmp_path / "d.json"),
        MigrationEvidencePackStore(tmp_path / "e.json"),
        tmp_path / "a.json",
    )
    calls = []
    router = ExecutionRouter(authority, lambda op, payload, **kw: calls.append((op, payload)) or "v1")
    assert router.route("reconcile_network").engine == "V1.4.1"
    assert router.execute("reconcile_network", {"resources": {}}) == "v1"
    assert calls


def test_v2_authority_fails_closed_without_executor(tmp_path):
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore

    decisions = MigrationDecisionStore(tmp_path / "d.json")
    evidence = MigrationEvidencePackStore(tmp_path / "e.json")
    package = evidence.create(
        scope="CAPABILITY", capability="NETWORK_RECONCILIATION", result_ids=[],
        shadow_evidence_ids=[], classification_ids=[], audit_event_ids=[],
        readiness={"status": "READY_FOR_AUTHORITY_REVIEW"},
        manifest={"capability": "NETWORK_RECONCILIATION"},
    )
    decision = decisions.record(package, "APPROVE_AUTHORITY_REVIEW", "reviewer", "Approved.")
    authority = AuthorityStore(decisions, evidence, tmp_path / "a.json")
    authority.activate("NETWORK_RECONCILIATION", decision.decision_id, "operator", "Activate.")
    router = ExecutionRouter(authority, lambda *a, **k: "v1")
    assert router.route("reconcile_network").executor_available is False
    try:
        router.execute("reconcile_network")
        assert False, "expected fail-closed routing"
    except RuntimeError as exc:
        assert "execution blocked" in str(exc)
