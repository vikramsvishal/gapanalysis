from v2.migration_readiness import MigrationReadinessGate

def test_readiness_blocks_unclassified_divergence():
    shadow = {"enabled": True, "authoritative_engine": "V1.4.1", "row_count": 1,
              "mismatches": [{"row_index": 0, "differences": {"recommended_action": {"golden":"A","v2":"B"}}}]}
    result = MigrationReadinessGate().evaluate(shadow, [])
    assert result["status"] == "NOT_READY"
    assert result["unclassified_count"] == 1
    assert result["execution_authority_changed"] is False

def test_readiness_allows_explicitly_approved_evidence():
    shadow = {"enabled": True, "row_count": 1,
              "mismatches": [{"row_index": 0, "differences": {"recommended_action": {"golden":"A","v2":"B"}}}]}
    classifications = [{"row_index": 0, "field": "recommended_action", "status": "INTENTIONAL_DIFFERENCE"}]
    result = MigrationReadinessGate().evaluate(shadow, classifications)
    assert result["status"] == "READY_FOR_AUTHORITY_REVIEW"
    assert result["blocking_count"] == 0

def test_readiness_blocks_v2_defect():
    shadow = {"enabled": True, "row_count": 1,
              "mismatches": [{"row_index": 0, "differences": {"recommended_action": {"golden":"A","v2":"B"}}}]}
    classifications = [{"row_index": 0, "field": "recommended_action", "status": "V2_DEFECT"}]
    assert MigrationReadinessGate().evaluate(shadow, classifications)["status"] == "NOT_READY"


def _runtime_network_shadow():
    return {
        "enabled": True,
        "authoritative_engine": "V1.4.1",
        "row_count": 1,
        "mismatches": [],
        "evidence_ids": ["EVID-NW-SHADOW"],
        "fingerprints": {
            "schema_version": "1.0",
            "input_sha256": "a" * 64,
            "authoritative_output_sha256": "b" * 64,
            "candidate_output_sha256": "c" * 64,
        },
    }


def test_network_runtime_shadow_fingerprint_is_required_for_capability_readiness():
    from types import SimpleNamespace
    result = SimpleNamespace(
        result_id="RES-NW",
        operation="reconcile_network",
        inputs={"domain": "network"},
    )
    gate = MigrationReadinessGate()
    ready = gate.evaluate_capabilities([result], {"RES-NW": _runtime_network_shadow()}, {"RES-NW": []})
    assert ready["capabilities"][0]["status"] == "READY_FOR_AUTHORITY_REVIEW"
    assert ready["execution_authority_changed"] is False


def test_network_readiness_blocks_missing_runtime_fingerprint():
    from types import SimpleNamespace
    result = SimpleNamespace(
        result_id="RES-NW",
        operation="reconcile_network",
        inputs={"domain": "network"},
    )
    shadow = _runtime_network_shadow()
    shadow.pop("fingerprints")
    gate = MigrationReadinessGate()
    ready = gate.evaluate_capabilities([result], {"RES-NW": shadow}, {"RES-NW": []})
    item = ready["capabilities"][0]
    assert item["status"] == "NOT_READY"
    assert item["execution_authority_changed"] is False


def test_network_readiness_blocks_invalid_runtime_fingerprint():
    from types import SimpleNamespace
    result = SimpleNamespace(
        result_id="RES-NW",
        operation="reconcile_network",
        inputs={"domain": "network"},
    )
    shadow = _runtime_network_shadow()
    shadow["fingerprints"]["candidate_output_sha256"] = "not-a-sha256"
    gate = MigrationReadinessGate()
    ready = gate.evaluate_capabilities([result], {"RES-NW": shadow}, {"RES-NW": []})
    assert ready["capabilities"][0]["status"] == "NOT_READY"
