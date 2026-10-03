"""Authoritative hardware catalog resolution contract.

This is deliberately stricter than the legacy matcher: the matcher proposes
identity candidates; this resolver decides whether a candidate is authoritative
enough to be used as a catalog-controlled value.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .catalog_matching import HardwareCatalogMatcher, HardwareMatch
from .contracts import CatalogMatchStatus, CatalogResolution


@dataclass(frozen=True)
class CatalogResolutionRequest:
    domain: str
    manufacturer: str
    model: str
    source_reference: str = ""


class AuthoritativeHardwareCatalogResolver:
    """Translate deterministic matcher output into governed catalog resolution."""

    def __init__(self, catalog: pd.DataFrame):
        self.matcher = HardwareCatalogMatcher(catalog)

    def resolve(self, request: CatalogResolutionRequest) -> CatalogResolution:
        match: HardwareMatch = self.matcher.match(
            request.domain, request.manufacturer, request.model
        )
        source = str(request.model or "")
        normalized = self.matcher._pkey(source)

        if match.status == "EXACT MATCH" and match.record:
            record = match.record
            opaque_id = record.get("opaque_id") or None
            catalog_value = record.get("hardware_model") or None
            return CatalogResolution(
                source_value=source,
                normalized_source_value=normalized,
                catalog_record_id=opaque_id,
                catalog_value=catalog_value,
                match_method=match.detail,
                confidence=1.0,
                status=CatalogMatchStatus.EXACT,
                reason=match.detail,
                load_allowed=True,
                catalog_update_required=False,
                evidence=[request.source_reference] if request.source_reference else [],
            )

        if match.status == "PARTIAL MATCH" and match.record:
            record = match.record
            return CatalogResolution(
                source_value=source,
                normalized_source_value=normalized,
                catalog_record_id=record.get("opaque_id") or None,
                catalog_value=record.get("hardware_model") or None,
                match_method=match.detail,
                confidence=None,
                status=CatalogMatchStatus.AMBIGUOUS,
                reason=(
                    "Candidate catalog record requires human review; "
                    "similarity/partial matching does not authorize load."
                ),
                load_allowed=False,
                catalog_update_required=False,
                evidence=[request.source_reference] if request.source_reference else [],
            )

        if match.detail == "AMBIGUOUS PARTIAL MATCH":
            return CatalogResolution(
                source_value=source,
                normalized_source_value=normalized,
                match_method=match.detail,
                confidence=None,
                status=CatalogMatchStatus.AMBIGUOUS,
                reason="Multiple catalog candidates remain ambiguous.",
                load_allowed=False,
                catalog_update_required=False,
                evidence=[request.source_reference] if request.source_reference else [],
            )

        return CatalogResolution(
            source_value=source,
            normalized_source_value=normalized,
            match_method=match.detail,
            confidence=0.0,
            status=CatalogMatchStatus.NO_MATCH,
            reason="No authoritative catalog record matched the supplied hardware identity.",
            load_allowed=False,
            catalog_update_required=True,
            evidence=[request.source_reference] if request.source_reference else [],
        )
