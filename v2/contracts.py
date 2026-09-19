"""Stable domain contracts introduced without changing V1.4.1 behavior."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

class DecisionStatus(str, Enum):
    LOAD = "LOAD"
    BLOCK = "BLOCK"
    REVIEW = "REVIEW"
    CATALOG_UPDATE_REQUIRED = "CATALOG_UPDATE_REQUIRED"
    NO_ACTION = "NO_ACTION"

class CatalogMatchStatus(str, Enum):
    EXACT = "EXACT CATALOG MATCH"
    NORMALIZED = "NORMALIZED CATALOG MATCH"
    APPROVED_ALIAS = "APPROVED ALIAS -> CATALOG VALUE"
    AMBIGUOUS = "AMBIGUOUS CATALOG MATCH"
    NO_MATCH = "NO CATALOG MATCH"

@dataclass(frozen=True)
class AssetIdentity:
    configuration_item: str = ""
    hostname: str = ""
    fqdn: str = ""
    serial: str = ""
    ip_address: str = ""

    def as_dict(self) -> Dict[str, str]:
        return self.__dict__.copy()

@dataclass(frozen=True)
class SourceEvidence:
    source_system: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    source_reference: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {"source_system": self.source_system, "attributes": dict(self.attributes), "source_reference": self.source_reference}

@dataclass(frozen=True)
class CatalogResolution:
    source_value: str
    normalized_source_value: str = ""
    catalog_record_id: Optional[str] = None
    catalog_value: Optional[str] = None
    match_method: str = ""
    confidence: Optional[float] = None
    status: CatalogMatchStatus = CatalogMatchStatus.NO_MATCH
    reason: str = ""
    load_allowed: bool = False
    catalog_update_required: bool = False
    evidence: List[str] = field(default_factory=list)

@dataclass
class GovernanceDecision:
    asset_identity: AssetIdentity
    source_evidence: List[SourceEvidence] = field(default_factory=list)
    normalized_evidence: Dict[str, Any] = field(default_factory=dict)
    current_is_state: Dict[str, Any] = field(default_factory=dict)
    catalog_resolutions: Dict[str, CatalogResolution] = field(default_factory=dict)
    applicable_policies: List[str] = field(default_factory=list)
    validation_results: Dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""
    required_values: Dict[str, Any] = field(default_factory=dict)
    action: DecisionStatus = DecisionStatus.REVIEW
    approval_required: bool = False
    execution_status: str = "NOT_STARTED"
    verification_status: str = "NOT_STARTED"
    audit_evidence: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "asset_identity": self.asset_identity.as_dict(),
            "source_evidence": [x.as_dict() for x in self.source_evidence],
            "normalized_evidence": dict(self.normalized_evidence),
            "current_is_state": dict(self.current_is_state),
            "catalog_resolutions": {k: v.__dict__.copy() for k, v in self.catalog_resolutions.items()},
            "applicable_policies": list(self.applicable_policies),
            "validation_results": dict(self.validation_results),
            "recommendation": self.recommendation,
            "required_values": dict(self.required_values),
            "action": self.action.value,
            "approval_required": self.approval_required,
            "execution_status": self.execution_status,
            "verification_status": self.verification_status,
            "audit_evidence": list(self.audit_evidence),
        }

@dataclass(frozen=True)
class LoadCandidate:
    asset_identity: AssetIdentity
    values: Dict[str, Any]
    candidate_set_id: str
    eligibility_reason: str = ""
    eligible: bool = False
