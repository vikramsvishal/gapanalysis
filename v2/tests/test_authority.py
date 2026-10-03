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


def test_activation_rejects_missing_decision(tmp_path):
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore
    decisions = MigrationDecisionStore(tmp_path / "decisions.json")
    evidence = MigrationEvidencePackStore(tmp_path / "evidence.json")
    authority = AuthorityStore(decisions, evidence, tmp_path / "authority.json")
    try:
        authority.activate("NETWORK_RECONCILIATION", "DEC-MISSING", "operator", "Attempt.")
        assert False, "expected missing decision rejection"
    except ValueError as exc:
        assert "not found" in str(exc)


def test_activation_rejects_capability_mismatch(tmp_path):
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore
    decisions = MigrationDecisionStore(tmp_path / "decisions.json")
    evidence = MigrationEvidencePackStore(tmp_path / "evidence.json")
    package = evidence.create(scope="CAPABILITY", capability="SERVER_RECONCILIATION", result_ids=[],
        shadow_evidence_ids=[], classification_ids=[], audit_event_ids=[],
        readiness={"status": "READY_FOR_AUTHORITY_REVIEW"}, manifest={"capability": "SERVER_RECONCILIATION"})
    decision = decisions.record(package, "APPROVE_AUTHORITY_REVIEW", "reviewer", "Approved.")
    authority = AuthorityStore(decisions, evidence, tmp_path / "authority.json")
    try:
        authority.activate("NETWORK_RECONCILIATION", decision.decision_id, "operator", "Attempt.")
        assert False, "expected capability mismatch rejection"
    except ValueError as exc:
        assert "capability" in str(exc)


def test_activation_rejects_missing_evidence_package(tmp_path):
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore
    decisions = MigrationDecisionStore(tmp_path / "decisions.json")
    evidence = MigrationEvidencePackStore(tmp_path / "evidence.json")
    package = Package()
    decision = decisions.record(package, "APPROVE_AUTHORITY_REVIEW", "reviewer", "Approved.")
    authority = AuthorityStore(decisions, evidence, tmp_path / "authority.json")
    try:
        authority.activate("NETWORK_RECONCILIATION", decision.decision_id, "operator", "Attempt.")
        assert False, "expected missing package rejection"
    except ValueError as exc:
        assert "not found" in str(exc)


def test_activation_rejects_manifest_binding_mismatch(tmp_path):
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore
    decisions = MigrationDecisionStore(tmp_path / "decisions.json")
    evidence = MigrationEvidencePackStore(tmp_path / "evidence.json")
    package = evidence.create(scope="CAPABILITY", capability="NETWORK_RECONCILIATION", result_ids=[],
        shadow_evidence_ids=[], classification_ids=[], audit_event_ids=[],
        readiness={"status": "READY_FOR_AUTHORITY_REVIEW"}, manifest={"capability": "NETWORK_RECONCILIATION"})
    decision = decisions.record(package, "APPROVE_AUTHORITY_REVIEW", "reviewer", "Approved.")
    object.__setattr__(decision, "package_manifest_sha256", "tampered")
    authority = AuthorityStore(decisions, evidence, tmp_path / "authority.json")
    try:
        authority.activate("NETWORK_RECONCILIATION", decision.decision_id, "operator", "Attempt.")
        assert False, "expected stale binding rejection"
    except ValueError as exc:
        assert "decision hash" in str(exc)


def test_activation_rejects_tampered_evidence_manifest(tmp_path):
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore
    decisions = MigrationDecisionStore(tmp_path / "decisions.json")
    evidence = MigrationEvidencePackStore(tmp_path / "evidence.json")
    package = evidence.create(scope="CAPABILITY", capability="NETWORK_RECONCILIATION", result_ids=[],
        shadow_evidence_ids=[], classification_ids=[], audit_event_ids=[],
        readiness={"status": "READY_FOR_AUTHORITY_REVIEW"}, manifest={"capability": "NETWORK_RECONCILIATION"})
    decision = decisions.record(package, "APPROVE_AUTHORITY_REVIEW", "reviewer", "Approved.")
    evidence._manifests[package.package_id]["tampered"] = True
    authority = AuthorityStore(decisions, evidence, tmp_path / "authority.json")
    try:
        authority.activate("NETWORK_RECONCILIATION", decision.decision_id, "operator", "Attempt.")
        assert False, "expected manifest integrity rejection"
    except ValueError as exc:
        assert "manifest hash" in str(exc)


def test_activation_rejects_unready_package_and_changed_decision(tmp_path):
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore
    decisions = MigrationDecisionStore(tmp_path / "decisions.json")
    evidence = MigrationEvidencePackStore(tmp_path / "evidence.json")
    package = evidence.create(scope="CAPABILITY", capability="NETWORK_RECONCILIATION", result_ids=[],
        shadow_evidence_ids=[], classification_ids=[], audit_event_ids=[],
        readiness={"status": "NOT_READY"}, manifest={"capability": "NETWORK_RECONCILIATION"})
    decision = decisions.record(package, "APPROVE_AUTHORITY_REVIEW", "reviewer", "Approved.")
    authority = AuthorityStore(decisions, evidence, tmp_path / "authority.json")
    try:
        authority.activate("NETWORK_RECONCILIATION", decision.decision_id, "operator", "Attempt.")
        assert False, "expected readiness rejection"
    except ValueError as exc:
        assert "not ready" in str(exc)
    package2 = evidence.create(scope="CAPABILITY", capability="NETWORK_RECONCILIATION", result_ids=[],
        shadow_evidence_ids=[], classification_ids=[], audit_event_ids=[],
        readiness={"status": "READY_FOR_AUTHORITY_REVIEW"}, manifest={"capability": "NETWORK_RECONCILIATION", "case": "changed"})
    decision2 = decisions.record(package2, "APPROVE_AUTHORITY_REVIEW", "reviewer", "Approved.")
    object.__setattr__(decision2, "authority_changed", True)
    from v2.migration_decision import _hash
    payload = {
        "package_id": decision2.package_id, "capability": decision2.capability,
        "decision": decision2.decision, "actor": decision2.actor, "rationale": decision2.rationale,
        "package_manifest_sha256": decision2.package_manifest_sha256,
        "authoritative_engine_before": decision2.authoritative_engine_before, "authority_changed": True,
    }
    object.__setattr__(decision2, "decision_sha256", _hash(payload))
    authority2 = AuthorityStore(decisions, evidence, tmp_path / "authority2.json")
    try:
        authority2.activate("NETWORK_RECONCILIATION", decision2.decision_id, "operator", "Attempt.")
        assert False, "expected changed-authority rejection"
    except ValueError as exc:
        assert "authority change" in str(exc)


def test_activation_requires_actor_and_rationale(tmp_path):
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore
    decisions = MigrationDecisionStore(tmp_path / "decisions.json")
    evidence = MigrationEvidencePackStore(tmp_path / "evidence.json")
    authority = AuthorityStore(decisions, evidence, tmp_path / "authority.json")
    for actor, rationale, expected in [("", "reason", "actor"), ("operator", "", "rationale")]:
        try:
            authority.activate("NETWORK_RECONCILIATION", "DEC-MISSING", actor, rationale)
            assert False, "expected validation failure"
        except ValueError as exc:
            assert expected in str(exc)


def test_activation_binds_previous_engine_and_immutable_references(tmp_path):
    from v2.migration_decision import MigrationDecisionStore
    from v2.migration_evidence import MigrationEvidencePackStore
    decisions = MigrationDecisionStore(tmp_path / "decisions.json")
    evidence = MigrationEvidencePackStore(tmp_path / "evidence.json")
    package = evidence.create(scope="CAPABILITY", capability="NETWORK_RECONCILIATION", result_ids=[],
        shadow_evidence_ids=[], classification_ids=[], audit_event_ids=[],
        readiness={"status": "READY_FOR_AUTHORITY_REVIEW"}, manifest={"capability": "NETWORK_RECONCILIATION"})
    decision = decisions.record(package, "APPROVE_AUTHORITY_REVIEW", "reviewer", "Approved.")
    authority = AuthorityStore(decisions, evidence, tmp_path / "authority.json")
    state = authority.activate("NETWORK_RECONCILIATION", decision.decision_id, "operator", "Explicit activation.")
    assert state.previous_engine == DEFAULT_ENGINE
    assert state.evidence_package_id == package.package_id
    assert state.migration_decision_id == decision.decision_id
