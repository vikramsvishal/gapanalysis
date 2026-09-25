from types import SimpleNamespace
from v2.migration_readiness import MigrationReadinessGate, capability

def test_capability_mapping():
    assert capability("reconcile_network", "network") == "NETWORK_RECONCILIATION"
    assert capability("run_hardware_governance", "server") == "SERVER_HARDWARE_GOVERNANCE"

def test_capability_gate_is_independent():
    gate = MigrationReadinessGate()
    ready_shadow = {"enabled": True, "row_count": 1, "mismatches": []}
    blocked_shadow = {"enabled": True, "row_count": 1, "mismatches": [{"row_index": 0, "differences": {"recommended_action": {"golden":"A","v2":"B"}}}]}
    results = [
        SimpleNamespace(result_id="R1", operation="reconcile_network", inputs={"domain":"network"}),
        SimpleNamespace(result_id="R2", operation="run_hardware_governance", inputs={"domain":"server"}),
    ]
    output = gate.evaluate_capabilities(results, {"R1": ready_shadow, "R2": blocked_shadow}, {"R1": [], "R2": []})
    states = {x["capability"]: x["status"] for x in output["capabilities"]}
    assert states["NETWORK_RECONCILIATION"] == "READY_FOR_AUTHORITY_REVIEW"
    assert states["SERVER_HARDWARE_GOVERNANCE"] == "NOT_READY"
    assert output["execution_authority_changed"] is False
