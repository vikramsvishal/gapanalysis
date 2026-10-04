"""Deterministic hardware-governance decision composition.

This module composes already-resolved signals. It does not perform catalog
matching or category discovery itself, and it does not replace V1.4.1 yet.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .category_governance import CategoryDependencyDecision
from .contracts import CatalogMatchStatus, DecisionStatus, GovernanceDecision


@dataclass(frozen=True)
class HardwareGovernanceSignals:
    """Inputs required to compose one governed hardware decision."""

    lifecycle_stage: str
    reconciliation_action: str
    catalog_status: CatalogMatchStatus
    catalog_update_required: bool
    category: CategoryDependencyDecision


class HardwareGovernanceDecisionComposer:
    """Apply deterministic precedence to previously resolved governance signals."""

    def compose(
        self,
        *,
        decision: GovernanceDecision,
        signals: HardwareGovernanceSignals,
    ) -> GovernanceDecision:
        decision.validation_results.update({
            "lifecycle_stage": signals.lifecycle_stage,
            "reconciliation_action": signals.reconciliation_action,
            "catalog_status": signals.catalog_status.value,
            "category_presence_status": signals.category.category_presence_status,
            "parent_dependency_status": signals.category.parent_dependency_status,
            "recommended_action": signals.category.recommended_action,
        })

        lifecycle = str(signals.lifecycle_stage or "").strip().lower()
        recon = str(signals.reconciliation_action or "").strip().lower()

        # A hardware record that is not an operational Load-To-IS candidate is
        # outside this governance execution scope.
        if lifecycle != "operational" or "load to is" not in recon:
            decision.action = DecisionStatus.NO_ACTION
            decision.recommendation = "NO LOAD ACTION"
            decision.approval_required = False
            return decision

        # Catalog authority is a prerequisite for a governed catalog-controlled
        # load. Similarity/partial/ambiguous results never authorize loading.
        if signals.catalog_status == CatalogMatchStatus.NO_MATCH:
            decision.action = DecisionStatus.CATALOG_UPDATE_REQUIRED
            decision.recommendation = "CATALOG UPDATE REQUIRED"
            decision.approval_required = True
            return decision

        if signals.catalog_status == CatalogMatchStatus.AMBIGUOUS:
            decision.action = DecisionStatus.REVIEW
            decision.recommendation = "CATEGORY DATA QUALITY REVIEW"
            decision.approval_required = True
            return decision

        # Category dependency remains independently governed even when catalog
        # identity is authoritative.
        if signals.category.recommended_action == "CATEGORY DATA QUALITY REVIEW":
            decision.action = DecisionStatus.REVIEW
            decision.recommendation = "CATEGORY DATA QUALITY REVIEW"
            decision.approval_required = True
            return decision

        if signals.category.recommended_action == "LOAD CATEGORY AND OS":
            decision.action = DecisionStatus.LOAD
            decision.recommendation = "LOAD CATEGORY AND OS"
            decision.approval_required = True
            decision.required_values["category_load_required"] = True
            return decision

        if signals.category.recommended_action == "LOAD OS ONLY":
            decision.action = DecisionStatus.LOAD
            decision.recommendation = "LOAD OS ONLY"
            decision.approval_required = True
            decision.required_values["category_load_required"] = False
            return decision

        decision.action = DecisionStatus.REVIEW
        decision.recommendation = "CATEGORY DATA QUALITY REVIEW"
        decision.approval_required = True
        return decision
