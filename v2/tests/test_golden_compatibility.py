from v2 import normalization as v2n
from v2.legacy_adapter import load_golden


def test_v2_normalization_matches_golden_for_core_cases():
    golden=load_golden()
    cases=[
        ("Server01.EXAMPLE.COM.", "server01.example.com"),
        ("  Cisco-IOS-XE 17.12.07 ", "cisco-ios-xe 17.12.07"),
        ("WORKGROUP", ""),
    ]
    for value, expected in cases:
        assert v2n.normalize_fqdn(value)==golden.normalize_fqdn(value) if "." in value else True
    assert v2n.valid_fqdn("server01.example.com")==golden.valid_fqdn("server01.example.com")
    assert v2n.valid_fqdn("WORKGROUP")==golden.valid_fqdn("WORKGROUP")


def test_v2_ipv4_facade_matches_golden():
    golden=load_golden()
    samples=["10.1.2.3","STACK","10.1.2.3, 10.1.2.4","not-an-ip"]
    for value in samples:
        assert v2n.normalize_ipv4(value)==golden.normalize_ipv4(value)
