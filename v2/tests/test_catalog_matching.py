import pandas as pd
import pytest

from v2.catalog_matching import HardwareCatalogMatcher, golden_hardware_match


def catalog():
    return pd.DataFrame(
        [
            {
                "manufacturer": "Cisco",
                "hardware_type": "Router",
                "hardware_model": "ASR1001-X",
                "subcategory": "Router",
                "end_of_life_date": "",
                "end_of_support_date": "",
                "product_opaque_id": "CAT-1",
            },
            {
                "manufacturer": "Dell",
                "hardware_type": "Server",
                "hardware_model": "R740",
                "subcategory": "Server",
                "end_of_life_date": "",
                "end_of_support_date": "",
                "product_opaque_id": "CAT-2",
            },
            {
                "manufacturer": "HP",
                "hardware_type": "Server",
                "hardware_model": "R740",
                "subcategory": "Server",
                "end_of_life_date": "",
                "end_of_support_date": "",
                "product_opaque_id": "CAT-3",
            },
            {
                "manufacturer": "Arista",
                "hardware_type": "Switch",
                "hardware_model": "7050SX3",
                "subcategory": "Switch",
                "end_of_life_date": "",
                "end_of_support_date": "",
                "product_opaque_id": "CAT-4",
            },
        ]
    )


@pytest.mark.parametrize(
    ("domain", "manufacturer", "model"),
    [
        ("network", "Cisco", "ASR1001-X"),
        ("network", "Cisco", "7050SX3"),
        ("server", "Dell", "R740"),
        ("server", "HP", "R740"),
        ("server", "Lenovo", "R740"),
        ("network", "Unknown", "UnknownModel"),
        ("server", "Unknown", "Server 999"),
    ],
)
def test_v2_matching_is_behaviorally_equivalent_to_v1_4_1(
    domain, manufacturer, model
):
    matcher = HardwareCatalogMatcher(catalog())
    actual = matcher.match(domain, manufacturer, model)
    expected = golden_hardware_match(domain, manufacturer, model, catalog())

    assert actual.record == expected.record
    assert actual.status == expected.status
    assert actual.detail == expected.detail
    assert actual.score == expected.score


def test_index_preserves_duplicate_model_candidates():
    matcher = HardwareCatalogMatcher(catalog())

    assert matcher.index.exact["r740"] == (1, 2)


def test_unknown_domain_is_rejected():
    with pytest.raises(ValueError, match="domain=network or domain=server"):
        HardwareCatalogMatcher(catalog()).match("storage", "Dell", "R740")
