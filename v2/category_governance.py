"""V2 category presence and parent-dependency governance.

This seam isolates the category relationship decision currently embedded in
V1.4.1. It intentionally preserves the legacy outcomes before any execution
path is migrated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from .contracts import DecisionStatus


@dataclass(frozen=True)
class CategoryDependencyDecision:
    serial_number: str
    category_presence_status: str
    parent_dependency_status: str
    recommended_action: str
    parent_opaque_id: str = ""
    parent_serial_number: str = ""
    parent_attributes: dict[str, str] | None = None

    @property
    def action(self) -> DecisionStatus:
        if self.recommended_action in {"LOAD OS ONLY", "LOAD CATEGORY AND OS"}:
            return DecisionStatus.LOAD
        if self.recommended_action == "CATEGORY DATA QUALITY REVIEW":
            return DecisionStatus.REVIEW
        return DecisionStatus.NO_ACTION

    @property
    def category_load_required(self) -> bool:
        return self.recommended_action == "LOAD CATEGORY AND OS"


class CategoryDependencyGovernance:
    """Resolve parent-category presence from normalized serial identity."""

    def __init__(self, lifecycle_fn: Callable[[Any], str], serial_key_fn: Callable[[Any], str]):
        self.lifecycle = lifecycle_fn
        self.serial_key = serial_key_fn

    def evaluate(
        self,
        domain: str,
        serial_number: Any,
        category: pd.DataFrame,
    ) -> CategoryDependencyDecision:
        if domain not in {"network", "server"}:
            raise ValueError("Category governance requires domain=network or domain=server")

        serial_col = self._find(
            category,
            "network_serial_number" if domain == "network" else "serial_number",
            "server_serial_number" if domain == "server" else "network_serial_number",
        )
        opaque_col = self._find(
            category,
            "network_opaque_id" if domain == "network" else "server_opaque_id",
            required=False,
        )
        life_col = self._find(
            category,
            "network_lifecycle_status" if domain == "network" else "lifecycle_status",
            "server_lifecycle_status" if domain == "server" else "network_lifecycle_status",
            required=False,
        )

        key = self.serial_key(serial_number)
        ids = []
        for i, row in category.iterrows():
            if not self.serial_key(row[serial_col]):
                continue
            if life_col and self.lifecycle(row[life_col]) not in {
                "production", "installed", "operational"
            }:
                continue
            if self.serial_key(row[serial_col]) == key:
                ids.append(i)

        if len(ids) == 1:
            row = category.iloc[ids[0]]
            attrs = {}
            for target, aliases in {
                "manufacturer": (
                    "network_manufacturer", "server_manufacturer", "manufacturer"
                ),
                "hardware_type": (
                    "network_hardware_type", "server_hardware_type", "hardware_type"
                ),
                "hardware_model": (
                    "network_hardware_model", "server_hardware_model", "hardware_model"
                ),
                "category": (
                    "category", "network_subcategory", "server_subcategory", "subcategory"
                ),
            }.items():
                col = self._find(category, *aliases, required=False)
                attrs[target] = str(row[col]) if col else ""

            return CategoryDependencyDecision(
                serial_number=str(serial_number or ""),
                category_presence_status="FOUND IN CATEGORY",
                parent_dependency_status="EXISTING PRODUCTION CATEGORY",
                recommended_action="LOAD OS ONLY",
                parent_opaque_id=str(row[opaque_col]) if opaque_col else "",
                parent_serial_number=str(row[serial_col]),
                parent_attributes=attrs,
            )

        if not ids:
            return CategoryDependencyDecision(
                serial_number=str(serial_number or ""),
                category_presence_status="MISSING FROM CATEGORY",
                parent_dependency_status="PARENT CATEGORY LOAD REQUIRED",
                recommended_action="LOAD CATEGORY AND OS",
                parent_serial_number=str(serial_number or ""),
                parent_attributes={},
            )

        return CategoryDependencyDecision(
            serial_number=str(serial_number or ""),
            category_presence_status="FOUND - DUPLICATE NORMALIZED SERIAL",
            parent_dependency_status="NOT APPLICABLE",
            recommended_action="CATEGORY DATA QUALITY REVIEW",
            parent_attributes={},
        )

    @staticmethod
    def _find(df: pd.DataFrame, *names: str, required: bool = True) -> str | None:
        normalized = {str(c).strip().lower().replace(" ", "_"): c for c in df.columns}
        for name in names:
            key = name.strip().lower().replace(" ", "_")
            if key in normalized:
                return normalized[key]
        if required:
            raise ValueError(f"Required category column is missing: {names[0]}")
        return None
