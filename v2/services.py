"""V2 service boundary over the protected V1.4.1 golden engine."""
from __future__ import annotations
from typing import Any
from .legacy_adapter import load_golden

class GovernanceService:
    def __init__(self, engine: Any | None = None):
        self.engine = engine or load_golden()

    def execute_operation(self, operation: str, payload: dict[str, Any], progress=None):
        progress = progress or (lambda message, percent=0: None)
        target = {"reconcile_network":self.reconcile_network,"reconcile_server":self.reconcile_server,"run_hardware_governance":self.run_hardware_governance,"generate_bulk_load":self.generate_bulk_load,"category_decisions_from_load":self.category_decisions_from_load}.get(operation)
        if not target: raise ValueError(f"Unsupported governance operation: {operation}")
        kwargs=dict(payload); kwargs["progress"]=progress
        return target(**kwargs)

    def execute_legacy(self, operation: str, *args, **kwargs):
        target={"reconcile_network":self.reconcile_network,"reconcile_server":self.reconcile_server,"run_hardware_governance":self.run_hardware_governance,"generate_bulk_load":self.generate_bulk_load,"category_decisions_from_load":self.category_decisions_from_load}.get(operation)
        if not target: raise ValueError(f"Unsupported governance operation: {operation}")
        return target(*args, **kwargs)

    def reconcile_network(self,*args,**kwargs): return self.engine.reconcile_nw(*args,**kwargs)
    def reconcile_server(self,*args,**kwargs): return self.engine.reconcile_server(*args,**kwargs)
    def run_hardware_governance(self,*args,**kwargs): return self.engine.run_hardware_governance(*args,**kwargs)
    def generate_bulk_load(self,*args,**kwargs): return self.engine.generate_bulk_load(*args,**kwargs)
    def category_decisions_from_load(self,*args,**kwargs): return self.engine.category_decisions_from_load(*args,**kwargs)
    def normalize(self,value:Any)->str: return self.engine.clean(value)
    def normalize_fqdn(self,value:Any)->str: return self.engine.normalize_fqdn(value)
    def validate_fqdn(self,value:Any)->str: return self.engine.valid_fqdn(value)
    def normalize_ipv4(self,value:Any): return self.engine.normalize_ipv4(value)
    def split_product_version(self,value:Any): return self.engine.split_product_version(value)
