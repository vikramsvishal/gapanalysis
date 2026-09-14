"""Deterministic catalog-resolution service for V2.

The resolver proposes/resolves catalog records; it does not execute loads.
Ambiguous matches are deliberately returned as ambiguous instead of guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from .domain import CatalogResolution, MatchMethod
from .normalization import pkey, vkey


@dataclass(frozen=True)
class CatalogRecord:
    record_id: str
    value: str
    manufacturer: str = ""
    model: str = ""
    category: str = ""
    version: str = ""


class CatalogResolver:
    """Resolve one source identity against an authoritative catalog.

    Resolution order is deterministic. Similarity is only a late-stage candidate
    mechanism and can never override an exact/composite result.
    """

    def __init__(self, records: Iterable[CatalogRecord], aliases: Optional[Mapping[str, str]] = None):
        self.records = list(records)
        self.aliases = {pkey(k): v for k, v in (aliases or {}).items()}
        self._exact: Dict[str, List[CatalogRecord]] = {}
        self._composite: Dict[str, List[CatalogRecord]] = {}
        self._manufacturer_model: Dict[str, List[CatalogRecord]] = {}
        self._normalized: Dict[str, List[CatalogRecord]] = {}
        for record in self.records:
            self._exact.setdefault(pkey(record.value) + "|" + vkey(record.version), []).append(record)
            self._composite.setdefault(
                pkey(record.category) + "|" + pkey(record.model) + "|" + vkey(record.version), []
            ).append(record)
            self._manufacturer_model.setdefault(
                pkey(record.manufacturer) + "|" + pkey(record.model), []
            ).append(record)
            self._normalized.setdefault(pkey(record.value), []).append(record)

    @staticmethod
    def _result(source: str, normalized: str, candidates: Sequence[CatalogRecord], method: MatchMethod, reason: str, confidence: Optional[float] = None) -> CatalogResolution:
        unique = {r.record_id: r for r in candidates}
        if len(unique) != 1:
            return CatalogResolution(
                source_value=source,
                normalized_source_value=normalized,
                match_method=MatchMethod.AMBIGUOUS,
                confidence=confidence,
                status="AMBIGUOUS CATALOG MATCH",
                reason=reason,
                load_allowed=False,
                evidence={"candidate_record_ids": list(unique)},
            )
        record = next(iter(unique.values()))
        return CatalogResolution(
            source_value=source,
            normalized_source_value=normalized,
            catalog_record_id=record.record_id,
            catalog_value=record.value,
            match_method=method,
            confidence=confidence if confidence is not None else 1.0,
            status="EXACT CATALOG MATCH" if method is MatchMethod.EXACT else "CATALOG MATCH",
            reason=reason,
            load_allowed=True,
            evidence={"candidate_record_ids": [record.record_id]},
        )

    def resolve(self, source_value: str, *, manufacturer: str = "", model: str = "", category: str = "", version: str = "", min_similarity: float = 0.92) -> CatalogResolution:
        source = str(source_value or "").strip()
        normalized = pkey(source)
        if not normalized:
            return CatalogResolution(source_value=source, status="NO CATALOG MATCH", reason="Blank source value", load_allowed=False, catalog_update_required=True)

        exact = self._exact.get(normalized + "|" + vkey(version), [])
        if exact:
            return self._result(source, normalized, exact, MatchMethod.EXACT, "Exact catalog identity match")

        composite = self._composite.get(pkey(category) + "|" + pkey(model) + "|" + vkey(version), []) if model else []
        if composite:
            return self._result(source, normalized, composite, MatchMethod.COMPOSITE, "Composite category/model/version match")

        mm = self._manufacturer_model.get(pkey(manufacturer) + "|" + pkey(model), []) if manufacturer and model else []
        if mm:
            return self._result(source, normalized, mm, MatchMethod.MANUFACTURER_MODEL, "Manufacturer/model match")

        normalized_candidates = self._normalized.get(normalized, [])
        if normalized_candidates:
            return self._result(source, normalized, normalized_candidates, MatchMethod.NORMALIZED, "Normalized catalog value match")

        alias_target = self.aliases.get(normalized)
        if alias_target:
            alias_candidates = self._normalized.get(pkey(alias_target), [])
            if alias_candidates:
                return self._result(source, normalized, alias_candidates, MatchMethod.APPROVED_ALIAS, "Approved alias resolved to catalog value")

        scored = []
        for record in self.records:
            score = SequenceMatcher(None, normalized, pkey(record.value)).ratio()
            if score >= min_similarity:
                scored.append((score, record))
        scored.sort(key=lambda item: (-item[0], item[1].record_id))
        if scored:
            top_score = scored[0][0]
            top = [record for score, record in scored if abs(score - top_score) < 0.0001]
            if len(top) == 1:
                return self._result(source, normalized, top, MatchMethod.TOKEN_SIMILARITY, "Deterministic similarity candidate; human review required", top_score)
            return CatalogResolution(
                source_value=source,
                normalized_source_value=normalized,
                match_method=MatchMethod.AMBIGUOUS,
                confidence=top_score,
                status="AMBIGUOUS CATALOG MATCH",
                reason="Multiple equally ranked catalog candidates",
                load_allowed=False,
                evidence={"candidate_record_ids": [r.record_id for r in top]},
            )

        return CatalogResolution(
            source_value=source,
            normalized_source_value=normalized,
            match_method=MatchMethod.NONE,
            status="NO CATALOG MATCH",
            reason="No authoritative catalog record matched the source value",
            load_allowed=False,
            catalog_update_required=True,
        )
