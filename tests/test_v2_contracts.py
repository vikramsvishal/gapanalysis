import unittest

from v2.domain import CatalogResolution, DecisionStatus, GovernanceDecision, MatchMethod, AssetIdentity
from v2.normalization import normalize_identity
from v2.policies import CatalogPolicy, FQDNPolicy, LoadEligibilityPolicy


class V2ContractTests(unittest.TestCase):
    def test_normalization_uses_golden_behavior(self):
        identity = normalize_identity(
            hostname=" Router/01 ",
            fqdn="Router01.NW.WPP.NET.",
            serial="SN-01",
            ip="stack 10.10.10.10",
        )
        self.assertEqual(identity["hostname"], "Router_01")
        self.assertEqual(identity["fqdn"], "router01.nw.wpp.net")
        self.assertEqual(identity["serial_number"], "sn01")
        self.assertEqual(identity["ip_address"], "10.10.10.10")

    def test_missing_fqdn_requires_review_when_human_approval_is_configured(self):
        status, reason = FQDNPolicy().evaluate("", "router01")
        self.assertEqual(status, DecisionStatus.REVIEW)
        self.assertIn("router01", reason)

    def test_catalog_governance_blocks_unresolved_value(self):
        resolution = CatalogResolution(
            source_value="Windows 2022",
            match_method=MatchMethod.NONE,
            status="NO CATALOG MATCH",
            catalog_update_required=True,
        )
        policy = CatalogPolicy(governed={"operating_system"})
        self.assertFalse(policy.allows("operating_system", resolution))

    def test_load_policy_requires_operational_and_upstream_approval(self):
        policy = LoadEligibilityPolicy()
        self.assertEqual(policy.evaluate("operational", True, True), DecisionStatus.LOAD)
        self.assertEqual(policy.evaluate("operational", True, False), DecisionStatus.REVIEW)
        self.assertEqual(policy.evaluate("end of life", True, True), DecisionStatus.BLOCK)
        self.assertEqual(policy.evaluate("operational", False, True), DecisionStatus.NO_ACTION)

    def test_governance_decision_has_explicit_execution_state(self):
        decision = GovernanceDecision(identity=AssetIdentity(configuration_item="CI-001"))
        self.assertEqual(decision.status, DecisionStatus.NO_ACTION)
        self.assertEqual(decision.execution_status, "NOT_EXECUTED")
        self.assertEqual(decision.verification_status, "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
