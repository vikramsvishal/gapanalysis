"""Golden regression corpus for the V1.4.1 -> V2 migration boundary.

The tests intentionally treat V1.4.1 as the oracle. When a V2 implementation is
extracted from the golden engine, these tests should continue to pass until the
behavioral change is explicitly approved.
"""
from __future__ import annotations

import pytest

from v2 import normalization as v2n
from v2.legacy_adapter import load_golden


@pytest.fixture(scope="module")
def golden():
    return load_golden()


@pytest.mark.parametrize(
    "value",
    [
        "", "  Server01  ", "Server01.EXAMPLE.COM.", "WORKGROUP",
        "server/01", "domain name", None,
        "NA", "Not Applicable", "10.1.2.3", "STACK",
        "10.1.2.3, 10.1.2.4", "999.1.1.1",
    ],
)
def test_identity_normalization_matches_v141(golden, value):
    assert v2n.clean(value) == golden.clean(value)
    assert v2n.hkey(value) == golden.hkey(value)
    assert v2n.pkey(value) == golden.pkey(value)
    assert v2n.vkey(value) == golden.vkey(value)
    assert v2n.lifecycle(value) == golden.lifecycle(value)
    assert v2n.serial_key(value) == golden.serial_key(value)
    assert v2n.normalize_hostname(value) == golden.normalize_hostname(value)
    assert v2n.normalize_fqdn(value) == golden.normalize_fqdn(value)
    assert v2n.valid_fqdn(value) == golden.valid_fqdn(value)
    assert v2n.normalize_ipv4(value) == golden.normalize_ipv4(value)


@pytest.mark.parametrize(
    "value",
    [
        "Cisco IOS XE 17.9.4",
        "Microsoft Windows Server 2022",
        "Ubuntu 22.04.3 LTS",
        "Arista EOS 4.30.2F",
        "Product without version",
        None,
        "",
    ],
)
def test_product_version_parsing_matches_v141(golden, value):
    assert v2n.split_product_version(value) == golden.split_product_version(value)


def test_golden_compatibility_surface_is_complete(golden):
    required = {
        "clean", "hkey", "pkey", "vkey", "lifecycle", "serial_key",
        "normalize_hostname", "normalize_fqdn", "valid_fqdn",
        "normalize_ipv4", "split_product_version", "find_col",
    }
    missing = [name for name in required if not callable(getattr(golden, name, None))]
    assert not missing, f"V1.4.1 compatibility surface changed: {missing}"


def test_v2_identity_facade_is_still_golden_backed():
    identity = v2n.normalize_identity(
        hostname="SW01",
        fqdn="SW01.EXAMPLE.COM.",
        serial=" SN-001 ",
        ip="10.1.2.3, 10.1.2.4",
    )
    assert identity == {
        "hostname": "SW01",
        "fqdn": "sw01.example.com",
        "valid_fqdn": "sw01.example.com",
        "serial_number": "sn001",
        "ip_address": "10.1.2.3",
    }
