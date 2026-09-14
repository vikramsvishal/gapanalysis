from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

class DecisionStatus(str, Enum):
    LOAD = "LOAD"
    BLOCK = "BLOCK"
    REVIEW = "REVIEW"
    CATALOG_UPDATE_REQUIRED = "CATALOG_UPDATE_REQUIRED"
    NO_ACTION = "NO_ACTION"

class MatchMethod(str, Enum):
    EXACT = "EXACT"
    COMPOSITE = "COMPOSITE"
    MANUFACTURER_MODEL = "MANUFACTURER_MODEL"
    NORMALIZED = "NORMALIZED"
    APPROVED_ALIAS = "APPROVED_ALIAS"
    TOKEN_SIMILARITY = "TOKEN_SIMILARITY"
    AMBIGUOUS = "AMBIGUOUS"
    NONE = "NONE"

@dataclass(frozen=True)
class AssetIdentity:
    source: str = ""
    configuration_item: str = ""
    hostname: str = ""
    fqdn: str = ""
    serial_number: str = ""
    ip_address: str = ""

@dataclass(frozen=True)
class SourceEvidence:
    field: str
    source_value: Any = ""
    normalized_value: Any = ""
    source_name: str = ""
    evidence: str = ""

@dataclass(frozen=True)
class CatalogResolution:
    source_value: str = ""
    normalized_source_value: str = ""
    catalog_record_id: str = ""
    catalog_value: str = ""
    match_method: MatchMethod = MatchMethod.NONE
    confidence: Optional[float] = None
    status: str = "NO CATALOG MATCH"
    reason: str = ""
    load_allowed: bool = False
    catalog_update_required: bool = False
    evidence: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Recommendation:
    action: str
    reason: str = ""
    required_value: str = ""
    approval_required: bool = False
    evidence: Dict[str, Any] = field(default_factory=dict)

@dataclass
class GovernanceDecision:
    identity: AssetIdentity
    source_evidence: List[SourceEvidence] = field(default_factory=list)
    current_is_state: Dict[str, Any] = field(default_factory=dict)
    catalog_resolutions: Dict[str, CatalogResolution] = field(default_factory=dict)
    applicable_policies: List[str] = field(default_factory=list)
    validation_results: Dict[str, Any] = field(default_factory=dict)
    recommendation: Optional[Recommendation] = None
    required_values: Dict[str, Any] = field(default_factory=dict)
    status: DecisionStatus = DecisionStatus.NO_ACTION
    execution_status: str = "NOT_EXECUTED"
    verification_status: str = "NOT_VERIFIED"
    audit_evidence: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class LoadCandidate:
    identity: AssetIdentity
    values: Dict[str, Any]
    decision_id: str
    catalog_resolution_ids: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class JobResult:
    job_id: str
    operation: str
    status: str
    decisions: List[GovernanceDecision] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)
    load_candidates: List[LoadCandidate] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
