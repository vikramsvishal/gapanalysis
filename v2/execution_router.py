"""Capability-aware execution routing.

This router selects the engine authorized for a capability. It deliberately does
not alias V2 to V1.4.1: if V2 authority is active without a registered V2
executor, execution fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .authority import DEFAULT_ENGINE, V2_ENGINE, AuthorityStore

OPERATION_CAPABILITIES = {
    "reconcile_network": "NETWORK_RECONCILIATION",
    "reconcile_server": "SERVER_RECONCILIATION",
    "run_hardware_governance:network": "NETWORK_HARDWARE_GOVERNANCE",
    "run_hardware_governance:server": "SERVER_HARDWARE_GOVERNANCE",
    "generate_bulk_load:network": "NETWORK_OS_BULK_LOAD",
    "generate_bulk_load:server": "SERVER_OS_BULK_LOAD",
}


def capability_for(operation: str, payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    domain = str(payload.get("domain") or "").lower()
    key = f"{operation}:{domain}" if domain else operation
    try:
        return OPERATION_CAPABILITIES[key]
    except KeyError as exc:
        raise ValueError(f"No authority capability mapping for operation: {key}") from exc


@dataclass(frozen=True)
class ExecutionRoute:
    capability: str
    engine: str
    executor_available: bool

    def public(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "engine": self.engine,
            "executor_available": self.executor_available,
        }


class ExecutionRouter:
    def __init__(self, authority: AuthorityStore, v1_executor: Callable[..., Any], v2_executors: dict[str, Callable[..., Any]] | None = None):
        self.authority = authority
        self.v1_executor = v1_executor
        self.v2_executors = v2_executors or {}

    def route(self, operation: str, payload: dict[str, Any] | None = None) -> ExecutionRoute:
        capability = capability_for(operation, payload)
        state = self.authority.get(capability)
        if state.engine == DEFAULT_ENGINE:
            return ExecutionRoute(capability, DEFAULT_ENGINE, True)
        if state.engine == V2_ENGINE:
            return ExecutionRoute(capability, V2_ENGINE, capability in self.v2_executors)
        raise ValueError(f"Unsupported execution engine: {state.engine}")

    def execute(self, operation: str, payload: dict[str, Any] | None = None, **kwargs: Any):
        route = self.route(operation, payload)
        if route.engine == DEFAULT_ENGINE:
            return self.v1_executor(operation, payload or {}, **kwargs)
        executor = self.v2_executors.get(route.capability)
        if executor is None:
            raise RuntimeError(
                f"Authority is active for {route.capability}, but no V2 executor is registered; execution blocked"
            )
        return executor(operation, payload or {}, **kwargs)
