from v2 import normalization as v2n
from v2.legacy_adapter import load_golden


def test_v2_normalization_matches_golden_for_core_cases():
    golden=load_golden()
    samples=["Server01.EXAMPLE.COM.","WORKGROUP","server01.example.com"]
    for value in samples:
        assert v2n.normalize_fqdn(value)==golden.normalize_fqdn(value)
        assert v2n.valid_fqdn(value)==golden.valid_fqdn(value)


def test_v2_ipv4_facade_matches_golden():
    golden=load_golden()
    samples=["10.1.2.3","STACK","10.1.2.3, 10.1.2.4","not-an-ip"]
    for value in samples:
        assert v2n.normalize_ipv4(value)==golden.normalize_ipv4(value)
