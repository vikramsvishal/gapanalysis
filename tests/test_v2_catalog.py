import unittest

from v2.catalog import CatalogRecord, CatalogResolver
from v2.domain import MatchMethod


class CatalogResolverTests(unittest.TestCase):
    def setUp(self):
        self.resolver = CatalogResolver([
            CatalogRecord("OS-2022", "Microsoft Windows Server 2022 Standard", version="2022"),
            CatalogRecord("OS-2019", "Microsoft Windows Server 2019 Standard", version="2019"),
            CatalogRecord("HW-001", "Cisco Catalyst 9300", manufacturer="Cisco", model="C9300", category="Switch", version="17.12"),
            CatalogRecord("HW-002", "Cisco Catalyst 9300L", manufacturer="Cisco", model="C9300L", category="Switch", version="17.12"),
        ], aliases={"windows server 2022": "Microsoft Windows Server 2022 Standard"})

    def test_exact_match_is_load_allowed(self):
        result = self.resolver.resolve("Microsoft Windows Server 2022 Standard", version="2022")
        self.assertEqual(result.match_method, MatchMethod.EXACT)
        self.assertTrue(result.load_allowed)

    def test_approved_alias_resolves_to_authoritative_value(self):
        result = self.resolver.resolve("Windows Server 2022")
        self.assertEqual(result.match_method, MatchMethod.APPROVED_ALIAS)
        self.assertEqual(result.catalog_record_id, "OS-2022")
        self.assertTrue(result.load_allowed)

    def test_similarity_candidate_never_authorizes_load(self):
        result = self.resolver.resolve("Microsoft Windows Server 2022 Standar", min_similarity=0.90)
        self.assertEqual(result.match_method, MatchMethod.TOKEN_SIMILARITY)
        self.assertFalse(result.load_allowed)
        self.assertEqual(result.status, "REVIEW REQUIRED")

    def test_unknown_value_requires_catalog_update(self):
        result = self.resolver.resolve("Completely Unknown Product")
        self.assertEqual(result.match_method, MatchMethod.NONE)
        self.assertFalse(result.load_allowed)
        self.assertTrue(result.catalog_update_required)


if __name__ == "__main__":
    unittest.main()
