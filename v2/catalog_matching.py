"""V2 hardware catalog matching engine.

This module is an extracted, testable representation of the V1.4.1 hardware
matching behavior. It deliberately preserves the golden matching precedence
until equivalence coverage is complete.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
from typing import Any, Optional

import pandas as pd

from .legacy_adapter import load_golden


@dataclass(frozen=True)
class HardwareMatch:
    record: Optional[dict[str, Any]]
    status: str
    detail: str
    score: int = 0


@dataclass(frozen=True)
class HardwareCatalogIndex:
    records: tuple[dict[str, Any], ...]
    exact: dict[str, tuple[int, ...]]
    composite: dict[str, tuple[int, ...]]
    manufacturer_model: dict[str, tuple[int, ...]]


class HardwareCatalogMatcher:
    """Deterministic catalog resolver extracted from the V1.4.1 behavior."""

    def __init__(self, catalog: pd.DataFrame):
        self.index = self._build_index(catalog)

    @staticmethod
    def _clean(value: Any) -> str:
        return load_golden().clean(value)

    @staticmethod
    def _pkey(value: Any) -> str:
        return load_golden().pkey(value)

    @classmethod
    def _build_index(cls, catalog: pd.DataFrame) -> HardwareCatalogIndex:
        find_col = load_golden().find_col
        cols = {
            name: find_col(catalog, name)
            for name in ("manufacturer", "hardware_type", "hardware_model", "subcategory")
        }
        eol = find_col(catalog, "end_of_life_date", required=False)
        eosl = find_col(catalog, "end_of_support_date", required=False)
        oid = find_col(catalog, "product_opaque_id", required=False)

        records: list[dict[str, Any]] = []
        exact: dict[str, list[int]] = defaultdict(list)
        composite: dict[str, list[int]] = defaultdict(list)
        manufacturer_model: dict[str, list[int]] = defaultdict(list)

        for _, row in catalog.iterrows():
            record = {
                "manufacturer": cls._clean(row[cols["manufacturer"]]),
                "hardware_type": cls._clean(row[cols["hardware_type"]]),
                "hardware_model": cls._clean(row[cols["hardware_model"]]),
                "subcategory": cls._clean(row[cols["subcategory"]]),
                "eol": cls._clean(row[eol]) if eol else "",
                "eosl": cls._clean(row[eosl]) if eosl else "",
                "opaque_id": cls._clean(row[oid]) if oid else "",
            }
            records.append(record)
            index = len(records) - 1
            exact[cls._pkey(record["hardware_model"])].append(index)
            composite[
                cls._pkey(record["hardware_type"] + record["hardware_model"])
            ].append(index)
            manufacturer_model[
                cls._pkey(record["manufacturer"]) + "|" + cls._pkey(record["hardware_model"])
            ].append(index)

        return HardwareCatalogIndex(
            records=tuple(records),
            exact={k: tuple(v) for k, v in exact.items()},
            composite={k: tuple(v) for k, v in composite.items()},
            manufacturer_model={k: tuple(v) for k, v in manufacturer_model.items()},
        )

    def match(self, domain: str, manufacturer: Any, model: Any) -> HardwareMatch:
        """Resolve one CMDB hardware identity using the V1.4.1 precedence."""
        if domain not in {"network", "server"}:
            raise ValueError("Hardware catalog matching requires domain=network or domain=server")

        records = self.index.records
        q = self._pkey(model)
        mk = self._pkey(manufacturer)

        ids = self.index.manufacturer_model.get(mk + "|" + q, ()) if domain == "server" else ()
        if ids:
            return HardwareMatch(
                records[ids[0]],
                "EXACT MATCH",
                "EXACT MANUFACTURER + MODEL ID",
                10000,
            )

        ids = self.index.exact.get(q, ())
        if len(ids) == 1:
            record = records[ids[0]]
            if (
                domain == "server"
                and mk
                and self._pkey(record["manufacturer"]) != mk
            ):
                return HardwareMatch(
                    record,
                    "PARTIAL MATCH",
                    "MODEL MATCH - MANUFACTURER REVIEW",
                    9000,
                )
            return HardwareMatch(record, "EXACT MATCH", "EXACT HARDWARE MODEL", 9800)

        ids = self.index.composite.get(q, ())
        if len(ids) == 1:
            record = records[ids[0]]
            if (
                domain == "server"
                and mk
                and self._pkey(record["manufacturer"]) != mk
            ):
                return HardwareMatch(
                    record,
                    "PARTIAL MATCH",
                    "MODEL MATCH - MANUFACTURER REVIEW",
                    9500,
                )
            return HardwareMatch(
                record,
                "EXACT MATCH",
                "EXACT TYPE + MODEL COMPOSITE",
                9500,
            )

        scored: list[tuple[int, int]] = []
        tokens = set(re.findall(r"[a-z]+|\d+", self._clean(model).lower()))
        for index, record in enumerate(records):
            record_tokens = set(
                re.findall(
                    r"[a-z]+|\d+",
                    (record["hardware_type"] + " " + record["hardware_model"]).lower(),
                )
            )
            score = len(tokens & record_tokens) * 100
            if score:
                scored.append((score, index))

        if not scored:
            return HardwareMatch(None, "NO MATCH", "NO INDEXED CANDIDATE", 0)

        top = max(score for score, _ in scored)
        ids = [index for score, index in scored if score == top]
        if len(
            {
                (
                    self._pkey(records[index]["manufacturer"]),
                    self._pkey(records[index]["hardware_type"]),
                    self._pkey(records[index]["hardware_model"]),
                )
                for index in ids
            }
        ) > 1:
            return HardwareMatch(None, "NO MATCH", "AMBIGUOUS PARTIAL MATCH", top)

        record = records[ids[0]]
        detail = (
            "MODEL MATCH - MANUFACTURER REVIEW"
            if domain == "server"
            and mk
            and self._pkey(record["manufacturer"]) != mk
            else "INDEXED HARDWARE TYPE/TOKEN MATCH"
        )
        return HardwareMatch(record, "PARTIAL MATCH", detail, top)


def golden_hardware_match(domain: str, manufacturer: Any, model: Any, catalog: pd.DataFrame):
    """Call the protected V1.4.1 matcher for equivalence tests."""
    golden = load_golden()
    return golden.hardware_match(domain, manufacturer, model, golden._hw_index(catalog))
