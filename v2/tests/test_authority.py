from v2.authority import AuthorityStore, DEFAULT_ENGINE, V2_ENGINE


class Package:
    package_id = "MIG-1"
    capability = "NETWORK_RECONCILIATION"
    manifest_sha256 = "manifest-1"
    authoritative_engine = "V1.4.1"
    readiness = {"status": "READY_FOR_AUTHORITY_REVIEW"}


def _decision(store):
    class P(Package):
        pass
    return store.record(P(), "APPROVE_AUTHORITY_REVIEW", "reviewer", "Evidence reviewed.")


def test_default_authority_is_v1(tmp_path):
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore

    decisions = MigrationDecisionStore(tmp_path / "decisions.json")
    evidence = MigrationEvidencePackStore(tmp_path / "evidence.json")
    authority = AuthorityStore(decisions, evidence, tmp_path / "authority.json")
    assert authority.get("NETWORK_RECONCILIATION").engine == DEFAULT_ENGINE


def test_activation_requires_explicit_approved_decision_and_binds_hash(tmp_path):
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore

    decisions = MigrationDecisionStore(tmp_path / "decisions.json")
    evidence = MigrationEvidencePackStore(tmp_path / "evidence.json")
    package = evidence.create(
        scope="CAPABILITY", capability="NETWORK_RECONCILIATION", result_ids=[],
        shadow_evidence_ids=[], classification_ids=[], audit_event_ids=[],
        readiness={"status": "READY_FOR_AUTHORITY_REVIEW"},
        manifest={"capability": "NETWORK_RECONCILIATION"},
    )
    decision = decisions.record(package, "APPROVE_AUTHORITY_REVIEW", "reviewer", "Approved after evidence review.")
    authority = AuthorityStore(decisions, evidence, tmp_path / "authority.json")
    state = authority.activate("NETWORK_RECONCILIATION", decision.decision_id, "operator", "Explicit activation.")
    assert state.engine == V2_ENGINE
    assert state.evidence_manifest_sha256 == package.manifest_sha256
    assert state.migration_decision_sha256 == decision.decision_sha256


def test_reject_or_defer_cannot_activate(tmp_path):
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore

    decisions = MigrationDecisionStore(tmp_path / "decisions.json")
    evidence = MigrationEvidencePackStore(tmp_path / "evidence.json")
    package = evidence.create(
        scope="CAPABILITY", capability="NETWORK_RECONCILIATION", result_ids=[],
        shadow_evidence_ids=[], classification_ids=[], audit_event_ids=[],
        readiness={"status": "READY_FOR_AUTHORITY_REVIEW"}, manifest={"capability": "NETWORK_RECONCILIATION"},
    )
    for choice in ("REJECT", "DEFER"):
        decision = decisions.record(package, choice, "reviewer", "Not approved.")
        authority = AuthorityStore(decisions, evidence, tmp_path / f"authority-{choice}.json")
        try:
            authority.activate("NETWORK_RECONCILIATION", decision.decision_id, "operator", "Attempt.")
            assert False, "expected activation rejection"
        except ValueError as exc:
            assert "APPROVE_AUTHORITY_REVIEW" in str(exc)


def test_rollback_restores_v1_and_is_capability_isolated(tmp_path):
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore

    decisions = MigrationDecisionStore(tmp_path / "decisions.json")
    evidence = MigrationEvidencePackStore(tmp_path / "evidence.json")
    package = evidence.create(
        scope="CAPABILITY", capability="NETWORK_RECONCILIATION", result_ids=[],
        shadow_evidence_ids=[], classification_ids=[], audit_event_ids=[],
        readiness={"status": "READY_FOR_AUTHORITY_REVIEW"}, manifest={"capability": "NETWORK_RECONCILIATION"},
    )
    decision = decisions.record(package, "APPROVE_AUTHORITY_REVIEW", "reviewer", "Approved.")
    authority = AuthorityStore(decisions, evidence, tmp_path / "authority.json")
    authority.activate("NETWORK_RECONCILIATION", decision.decision_id, "operator", "Activate.")
    assert authority.get("SERVER_RECONCILIATION").engine == DEFAULT_ENGINE
    state = authority.rollback("NETWORK_RECONCILIATION", "operator", "Rollback for controlled validation.")
    assert state.engine == DEFAULT_ENGINE
    assert state.previous_engine == V2_ENGINE


def test_activation_survives_reload(tmp_path):
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore

    decisions = MigrationDecisionStore(tmp_path / "decisions.json")
    evidence = MigrationEvidencePackStore(tmp_path / "evidence.json")
    package = evidence.create(
        scope="CAPABILITY", capability="NETWORK_RECONCILIATION", result_ids=[],
        shadow_evidence_ids=[], classification_ids=[], audit_event_ids=[],
        readiness={"status": "READY_FOR_AUTHORITY_REVIEW"}, manifest={"capability": "NETWORK_RECONCILIATION"},
    )
    decision = decisions.record(package, "APPROVE_AUTHORITY_REVIEW", "reviewer", "Approved.")
    authority = AuthorityStore(decisions, evidence, tmp_path / "authority.json")
    authority.activate("NETWORK_RECONCILIATION", decision.decision_id, "operator", "Activate.")
    reloaded = AuthorityStore(decisions, evidence, tmp_path / "authority.json")
    assert reloaded.get("NETWORK_RECONCILIATION").engine == V2_ENGINE
