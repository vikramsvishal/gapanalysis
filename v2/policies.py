from dataclasses import dataclass
from typing import Iterable, Set

from .domain import CatalogResolution, DecisionStatus, GovernanceDecision


@dataclass(frozen=True)
class FQDNPolicy:
    """Configuration-only representation of the existing FQDN governance rule."""
    required: bool = True
    default_suffix: str = ".nw.wpp.net"
    require_human_approval_for_default: bool = True

    def evaluate(self, fqdn: str, hostname: str) -> tuple[DecisionStatus, str]:
        if not self.required:
            return DecisionStatus.NO_ACTION, "FQDN policy not required"
        if fqdn and "." in fqdn and " " not in fqdn:
            return DecisionStatus.NO_ACTION, "Valid FQDN present"
        if hostname and self.default_suffix:
            if self.require_human_approval_for_default:
                return DecisionStatus.REVIEW, f"Default FQDN candidate: {hostname}{self.default_suffix}"
            return DecisionStatus.LOAD, f"Default FQDN generated: {hostname}{self.default_suffix}"
        return DecisionStatus.BLOCK, "Valid FQDN unavailable"


@dataclass(frozen=True)
class CatalogPolicy:
    """Load-control policy: catalog resolution is required before governed loading."""
    governed: Set[str]

    def allows(self, field: str, resolution: CatalogResolution) -> bool:
        if field not in self.governed:
            return True
        return resolution.load_allowed and not resolution.catalog_update_required


@dataclass(frozen=True)
class LoadEligibilityPolicy:
    """Final deterministic gate for load candidates."""
    operational_values: Set[str] = frozenset({"operational", "production", "installed", "deploy"})

    def evaluate(self, lifecycle: str, absent_in_is: bool, upstream_ok: bool) -> DecisionStatus:
        if not absent_in_is:
            return DecisionStatus.NO_ACTION
        if lifecycle.lower() not in self.operational_values:
            return DecisionStatus.BLOCK
        if not upstream_ok:
            return DecisionStatus.REVIEW
        return DecisionStatus.LOAD


def all_catalog_resolutions_allow_load(decision: GovernanceDecision) -> bool:
    """Shared guard used by future load builders; never infer a catalog value."""
    return all(r.load_allowed and not r.catalog_update_required for r in decision.catalog_resolutions.values())
