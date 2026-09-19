"""V2 service boundary. Initially delegates to V1.4.1."""
from __future__ import annotations
from typing import Any
from .golden import load_golden

class GovernanceService:
    def __init__(self, engine: Any | None = None):
        self.engine = engine or load_golden()

    def reconcile_network(self, *args, **kwargs):
        return self.engine.reconcile_nw(*args, **kwargs)

    def reconcile_server(self, *args, **kwargs):
        return self.engine.reconcile_server(*args, **kwargs)

    def run_hardware_governance(self, *args, **kwargs):
        return self.engine.run_hardware_governance(*args, **kwargs)

    def generate_bulk_load(self, *args, **kwargs):
        return self.engine.generate_bulk_load(*args, **kwargs)

    def category_decisions_from_load(self, *args, **kwargs):
        return self.engine.category_decisions_from_load(*args, **kwargs)

    def normalize(self, value: Any) -> str:
        return self.engine.clean(value)

    def normalize_fqdn(self, value: Any) -> str:
        return self.engine.normalize_fqdn(value)

    def validate_fqdn(self, value: Any) -> str:
        return self.engine.valid_fqdn(value)

    def normalize_ipv4(self, value: Any):
        return self.engine.normalize_ipv4(value)

    def split_product_version(self, value: Any):
        return self.engine.split_product_version(value)
