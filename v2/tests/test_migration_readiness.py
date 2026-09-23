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
