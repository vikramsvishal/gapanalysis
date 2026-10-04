from v2.catalog import CatalogRecord, CatalogResolver
from v2.domain import MatchMethod

def test_exact_catalog_match_allows_load():
    r=CatalogResolver([CatalogRecord("OS-1","Microsoft Windows Server 2022 Standard",version="2022")]).resolve("Microsoft Windows Server 2022 Standard",version="2022")
    assert r.match_method is MatchMethod.EXACT
    assert r.load_allowed is True

def test_similarity_never_authorizes_load():
    r=CatalogResolver([CatalogRecord("OS-1","Microsoft Windows Server 2022 Standard")]).resolve("Microsoft Windows Server 2022 Standar")
    assert r.match_method is MatchMethod.TOKEN_SIMILARITY
    assert r.load_allowed is False

def test_ambiguous_match_is_not_loadable():
    r=CatalogResolver([CatalogRecord("HW-1","Cisco Nexus 9K"),CatalogRecord("HW-2","Cisco Nexus 9K")]).resolve("Cisco Nexus 9K")
    assert r.load_allowed is False
