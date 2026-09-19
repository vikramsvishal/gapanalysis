"""Compatibility adapter around the untouched V1.4.1 golden implementation."""
from __future__ import annotations
import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = ROOT / "WPP_CMDB_IS_Gap_Analysis_V1_4_1_Consolidated.py"

def load_golden() -> ModuleType:
    spec = importlib.util.spec_from_file_location("wpp_v1_4_1_golden", GOLDEN_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load golden implementation: {GOLDEN_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def golden_version() -> str:
    return "V1.4.1"
