"""Backward-compatible import surface for the V1.4.1 golden adapter.

Use v2.legacy_adapter as the canonical compatibility boundary. This module
remains temporarily so existing imports do not break during V2 migration.
"""
from .legacy_adapter import load_golden


def golden_version() -> str:
    return "V1.4.1"
