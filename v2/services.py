"""V2 service boundary over the protected V1.4.1 golden engine."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .legacy_adapter import load_golden
from .resources import ResourceManager


class GovernanceService:
    def __init__(self, engine: Any | None = None, resources: ResourceManager | None = None):
        self.engine = engine or load_golden()
        self.resources = resources or ResourceManager()
        self.output_dir = Path(__file__).resolve().parent / "runtime" / "outputs"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def preflight(self, operation: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        resources = payload.get("resources") or {}
        requirement_operation = operation
        if operation in {"run_hardware_governance", "generate_bulk_load"}:
            domain = payload.get("domain")
            prefix = "run_hardware_governance" if operation == "run_hardware_governance" else "generate_bulk_load"
            requirement_operation = f"{prefix}_{domain}" if domain in {"network", "server"} else operation
        result = self.resources.resolve_requirements(requirement_operation, resources)
        return {"operation": operation, "ready": result["ready"], "required": result["required"], "missing": result["missing"]}

    def execute_operation(self, operation: str, payload: dict[str, Any], progress=None):
        progress = progress or (lambda message, percent=0: None)
        supported = {"reconcile_network","reconcile_server","run_hardware_governance","generate_bulk_load","category_decisions_from_load"}
        if operation not in supported:
            raise ValueError(f"Unsupported governance operation: {operation}")
        if payload.get("resources"):
            self._require_ready(operation, payload)
            return self._execute_resource_operation(operation, payload, progress)
        kwargs = dict(payload)
        kwargs["progress"] = progress
        return self._dispatch(operation, kwargs)

    def _require_ready(self, operation: str, payload: dict[str, Any]) -> None:
        check = self.preflight(operation, payload)
        if not check["ready"]:
            labels = ", ".join(x["label"] for x in check["missing"])
            raise ValueError(f"Required input files are missing: {labels}")

    def _record(self, payload: dict[str, Any], kind: str):
        resource_id = (payload.get("resources") or {}).get(kind)
        if not resource_id:
            raise ValueError(f"Required resource is missing: {kind}")
        record = self.resources.get(resource_id)
        if record is None or record.status != "AVAILABLE":
            raise FileNotFoundError(f"Resource is unavailable: {resource_id}")
        return record

    def _tabular(self, payload: dict[str, Any], kind: str):
        return self.engine.read_tabular(self._record(payload, kind).stored_path)

    def _field_intelligence(self, payload: dict[str, Any]):
        fi = self.engine.FieldIntelligence()
        mapping_id = (payload.get("resources") or {}).get("field_mapping")
        if mapping_id:
            record = self.resources.get(mapping_id)
            if record and record.status == "AVAILABLE":
                fi.load_workbook(record.stored_path)
        return fi

    def _execute_resource_operation(self, operation: str, payload: dict[str, Any], progress):
        if operation == "reconcile_network":
            return self.engine.reconcile_nw(
                self._tabular(payload, "nw_cmdb"), self._tabular(payload, "is_os"),
                self._tabular(payload, "catalog_os"), self._field_intelligence(payload), progress,
            )
        if operation == "reconcile_server":
            return self.engine.reconcile_server(
                self._tabular(payload, "server_cmdb"), self._tabular(payload, "is_os"),
                self._tabular(payload, "catalog_os"), self._field_intelligence(payload), progress,
            )[0]
        if operation == "run_hardware_governance":
            domain = payload.get("domain")
            if domain not in {"network", "server"}:
                raise ValueError("Hardware Governance requires domain=network or domain=server")
            cmdb_kind = "nw_cmdb" if domain == "network" else "server_cmdb"
            category_kind = "is_network_category" if domain == "network" else "is_server_category"
            catalog_kind = "catalog_network" if domain == "network" else "catalog_server"
            return self.engine.run_hardware_governance(
                domain, self._record(payload, cmdb_kind).stored_path,
                self._record(payload, category_kind).stored_path,
                self._record(payload, catalog_kind).stored_path,
                str(self.output_dir), progress,
            )
        if operation == "generate_bulk_load":
            domain = payload.get("domain")
            if domain not in {"network", "server"}:
                raise ValueError("OS Bulk Load Governance requires domain=network or domain=server")
            load_kind = "nw_load_to_is" if domain == "network" else "server_load_to_is"
            category_kind = "is_network_category" if domain == "network" else "is_server_category"
            load_df = self.engine.read_load_to_is_file(self._record(payload, load_kind).stored_path, domain, progress)
            governance = self.engine.category_decisions_from_load(domain, load_df, self._record(payload, category_kind).stored_path, progress)
            include_missing_fqdn = bool(payload.get("include_missing_fqdn", False))
            missing_fqdn_count = sum(1 for _, row in load_df.iterrows() if not self.engine.valid_fqdn(row.get("Fully qualified domain name", "")))
            if missing_fqdn_count and "include_missing_fqdn" not in payload:
                raise ValueError(f"{missing_fqdn_count} candidates have no valid FQDN; explicit human decision is required")
            fmt = str(payload.get("format", "xlsx")).lower()
            if fmt not in {"xlsx", "csv"}:
                raise ValueError("OS Bulk Load output format must be xlsx or csv")
            outputs = self.engine.generate_bulk_load(
                load_df, domain, self._record(payload, "is_os").stored_path,
                self._record(payload, "bulk_template").stored_path, str(self.output_dir), fmt,
                lambda _count: include_missing_fqdn, lambda _count: True, progress, governance,
            )
            return {"domain": domain, "candidate_count": len(load_df), "missing_fqdn_count": missing_fqdn_count,
                    "include_missing_fqdn": include_missing_fqdn,
                    "governance_summary": {"decisions": len(governance["decisions"]), "category_load_candidates": len(governance.get("category_load", []))},
                    "outputs": outputs}
        raise ValueError(f"Resource-backed execution is not implemented for: {operation}")

    def _dispatch(self, operation: str, kwargs: dict[str, Any]):
        target = {"reconcile_network":self.reconcile_network,"reconcile_server":self.reconcile_server,
                  "run_hardware_governance":self.run_hardware_governance,"generate_bulk_load":self.generate_bulk_load,
                  "category_decisions_from_load":self.category_decisions_from_load}.get(operation)
        if not target:
            raise ValueError(f"Unsupported governance operation: {operation}")
        return target(**kwargs)

    def execute_legacy(self, operation: str, *args, **kwargs):
        target = {"reconcile_network":self.reconcile_network,"reconcile_server":self.reconcile_server,
                  "run_hardware_governance":self.run_hardware_governance,"generate_bulk_load":self.generate_bulk_load,
                  "category_decisions_from_load":self.category_decisions_from_load}.get(operation)
        if not target:
            raise ValueError(f"Unsupported governance operation: {operation}")
        return target(*args, **kwargs)

    def reconcile_network(self,*args,**kwargs): return self.engine.reconcile_nw(*args,**kwargs)
    def reconcile_server(self,*args,**kwargs): return self.engine.reconcile_server(*args,**kwargs)
    def run_hardware_governance(self,*args,**kwargs): return self.engine.run_hardware_governance(*args,**kwargs)
    def generate_bulk_load(self,*args,**kwargs): return self.engine.generate_bulk_load(*args,**kwargs)
    def category_decisions_from_load(self,*args,**kwargs): return self.engine.category_decisions_from_load(*args,**kwargs)
    def bulk_preflight(self, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        check = self.preflight("generate_bulk_load", {"domain": domain, "resources": payload.get("resources") or {}})
        if not check["ready"]:
            return {**check, "candidate_count": None, "missing_fqdn_count": None, "blocked_category_candidates": None}
        load_kind = "nw_load_to_is" if domain == "network" else "server_load_to_is"
        category_kind = "is_network_category" if domain == "network" else "is_server_category"
        load_df = self.engine.read_load_to_is_file(self._record({"resources": payload.get("resources") or {}}, load_kind).stored_path, domain)
        decisions = self.engine.category_decisions_from_load(domain, load_df, self._record({"resources": payload.get("resources") or {}}, category_kind).stored_path)
        blocked = int(decisions["decisions"]["Recommended Action"].isin(["CATEGORY DATA QUALITY REVIEW", "NO LOAD ACTION"]).sum()) if not decisions["decisions"].empty and "Recommended Action" in decisions["decisions"].columns else 0
        missing_fqdn = sum(1 for _, row in load_df.iterrows() if not self.engine.valid_fqdn(row.get("Fully qualified domain name", "")))
        return {**check, "candidate_count": len(load_df), "missing_fqdn_count": missing_fqdn, "blocked_category_candidates": blocked, "ready_for_review": blocked == 0}

    def normalize(self,value:Any)->str: return self.engine.clean
    def normalize_fqdn(self,value:Any)->str: return self.engine.normalize_fqdn(value)
    def validate_fqdn(self,value:Any)->str: return self.engine.valid_fqdn(value)
    def normalize_ipv4(self,value:Any): return self.engine.normalize_ipv4(value)
    def split_product_version(self,value:Any): return self.engine.split_product_version(value)
