"""Deterministic agent interfaces for the V2 platform.

These agents orchestrate domain services; they are not LLM agents. This keeps
governance decisions deterministic while leaving a clean seam for future AI
assistance around explanation, enrichment and ambiguity handling.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Dict

from .catalog import CatalogRecord, CatalogResolver
from .domain import CatalogResolution, GovernanceDecision
from .normalization import normalize_identity


@dataclass
class AgentContext:
    operation: str
    actor: str = "local-user"
    correlation_id: str = ""


class NormalizationAgent:
    name = "deterministic-normalization"

    def normalize_identity(self, **values) -> Dict[str, Any]:
        return normalize_identity(
            hostname=values.get("hostname", ""),
            fqdn=values.get("fqdn", ""),
            serial=values.get("serial", values.get("serial_number", "")),
            ip=values.get("ip", values.get("ip_address", "")),
        )


class CatalogResolutionAgent:
    name = "deterministic-catalog-resolution"

    def __init__(self, records, aliases=None):
        self.resolver = CatalogResolver(records, aliases)

    def resolve(self, source_value: str, **identity) -> CatalogResolution:
        return self.resolver.resolve(source_value, **identity)


class GovernanceDecisionAgent:
    name = "deterministic-governance-decision"

    def build_review(self, identity, *, reason: str, evidence=None) -> GovernanceDecision:
        decision = GovernanceDecision(identity=identity)
        decision.validation_results["reason"] = reason
        decision.audit_evidence["evidence"] = evidence or []
        return decision


class AgentRegistry:
    """Small local registry; future web deployment can replace this adapter."""

    def __init__(self):
        self._agents: Dict[str, Any] = {}

    def register(self, agent: Any) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> Any:
        return self._agents[name]

    def names(self):
        return tuple(sorted(self._agents))


def default_registry(records=None, aliases=None) -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(NormalizationAgent())
    if records is not None:
        registry.register(CatalogResolutionAgent(records, aliases))
    registry.register(GovernanceDecisionAgent())
    return registry
