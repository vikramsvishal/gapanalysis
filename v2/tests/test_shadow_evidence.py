import pandas as pd

from v2.shadow_evidence import dataframe_fingerprint, resource_input_fingerprint, shadow_fingerprint


def test_dataframe_fingerprint_is_order_stable():
    left = pd.DataFrame([{"b": 2, "a": 1}, {"b": 4, "a": 3}])
    right = pd.DataFrame([{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    assert dataframe_fingerprint(left) == dataframe_fingerprint(right)


def test_resource_input_fingerprint_binds_resource_sha():
    class Resource:
        sha256 = "abc123"
        status = "AVAILABLE"

    class Resources:
        def get(self, _):
            return Resource()

    first = resource_input_fingerprint(Resources(), {"nw_cmdb": "RES-1"})
    Resource.sha256 = "different"
    second = resource_input_fingerprint(Resources(), {"nw_cmdb": "RES-1"})
    assert first != second


def test_shadow_fingerprint_contains_input_and_both_outputs():
    class Resource:
        sha256 = "input-sha"
        status = "AVAILABLE"

    class Resources:
        def get(self, _):
            return Resource()

    result = shadow_fingerprint(
        Resources(),
        {"nw_cmdb": "RES-1"},
        pd.DataFrame([{"Action": "Load To IS"}]),
        pd.DataFrame([{"Action": "Load To IS"}]),
    )
    assert result["schema_version"] == "1.0"
    assert len(result["input_sha256"]) == 64
    assert len(result["authoritative_output_sha256"]) == 64
    assert len(result["candidate_output_sha256"]) == 64
