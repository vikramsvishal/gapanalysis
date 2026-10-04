from v2.domain import AssetIdentity, CatalogResolution, DecisionStatus, GovernanceDecision, MatchMethod

def test_default_decision_is_safe():
    d=GovernanceDecision(identity=AssetIdentity(configuration_item="CI-001"))
    assert d.status is DecisionStatus.NO_ACTION

def test_no_match_is_not_loadable():
    r=CatalogResolution(source_value="unknown")
    assert r.match_method is MatchMethod.NONE
    assert r.load_allowed is False
