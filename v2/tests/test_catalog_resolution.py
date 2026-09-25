import pandas as pd

from v2.catalog_resolution import (
    AuthoritativeHardwareCatalogResolver,
    CatalogResolutionRequest,
)
from v2.contracts import CatalogMatchStatus


def catalog():
    return pd.DataFrame(
        [
            {
                "manufacturer": "Cisco",
                "hardware_type": "Router",
                "hardware_model": "ASR1001-X",
                "subcategory": "Router",
                "product_opaque_id": "CAT-1",
            },
            {
                "manufacturer": "Dell",
                "hardware_type": "Server",
                "hardware_model": "R740",
                "subcategory": "Server",
                "product_opaque_id": "CAT-2",
            },
            {
                "manufacturer": "HP",
                "hardware_type": "Server",
                "hardware_model": "R740",
                "subcategory": "Server",
                "product_opaque_id": "CAT-3",
            },
        ]
    )


def test_exact_catalog_match_is_authorized():
    result = AuthoritativeHardwareCatalogResolver(catalog()).resolve(
        CatalogResolutionRequest("server", "Dell", "R740", "CMDB:123")
    )

    assert result.status is CatalogMatchStatus.EXACT
    assert result.catalog_record_id == "CAT-2"
    assert result.catalog_value == "R740"
    assert result.load_allowed is True
    assert result.catalog_update_required is False


def test_partial_match_is_candidate_only_and_not_load_authorized():
    result = AuthoritativeHardwareCatalogResolver(catalog()).resolve(
        CatalogResolutionRequest("server", "Lenovo", "R740", "CMDB:124")
    )

    assert result.status is CatalogMatchStatus.AMBIGUOUS
    assert result.load_allowed is False
    assert result.catalog_update_required is False


def test_no_match_requires_catalog_update():
    result = AuthoritativeHardwareCatalogResolver(catalog()).resolve(
        CatalogResolutionRequest("network", "Cisco", "NCS-9999", "CMDB:125")
    )

    assert result.status is CatalogMatchStatus.NO_MATCH
    assert result.load_allowed is False
    assert result.catalog_update_required is True
