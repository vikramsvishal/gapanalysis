"""Transitional adapter around the V1.4.1 golden implementation.

This is intentionally a thin compatibility layer. V1.4.1 remains the business
behavior reference until each domain is extracted and covered by regression tests.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_GOLDEN_PATH = Path(__file__).resolve().parents[1] / "WPP_CMDB_IS_Gap_Analysis_V1_4_1_Consolidated.py"


def load_golden() -> ModuleType:
    spec = importlib.util.spec_from_file_location("wpp_v1_4_1_golden", _GOLDEN_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load golden implementation: {_GOLDEN_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalization_functions() -> dict[str, object]:
    golden = load_golden()
    names = (
        "clean", "hkey", "pkey", "vkey", "lifecycle", "serial_key",
        "normalize_hostname", "normalize_fqdn", "valid_fqdn",
        "normalize_ipv4", "split_product_version", "find_col",
    )
    return {name: getattr(golden, name) for name in names}
