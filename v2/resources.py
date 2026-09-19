"""Local resource management and input requirements for V2.

The browser never receives or supplies arbitrary filesystem paths. Uploaded files
are stored under the local V2 runtime directory and referenced by stable resource
IDs. This layer is deliberately independent of the V1.4.1 business engine.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNTIME_DIR = Path(__file__).resolve().parent / "runtime"
UPLOAD_DIR = RUNTIME_DIR / "uploads"
REGISTRY_PATH = RUNTIME_DIR / "resources.json"


@dataclass
class ResourceRecord:
    resource_id: str
    kind: str
    file_name: str
    stored_path: str
    size: int
    sha256: str
    uploaded_at: str
    status: str = "AVAILABLE"

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("stored_path", None)
        return data


RESOURCE_TYPES = {
    "nw_cmdb": {
        "label": "NW CMDB Report",
        "description": "Network CMDB export used for reconciliation.",
        "extensions": [".csv", ".xlsx", ".xlsm", ".xlsb"],
    },
    "server_cmdb": {
        "label": "Server CMDB Report",
        "description": "Server CMDB export used for reconciliation.",
        "extensions": [".csv", ".xlsx", ".xlsm", ".xlsb"],
    },
    "is_os": {
        "label": "IS Operating System Report",
        "description": "Current Inventory Services operating-system report.",
        "extensions": [".csv", ".xlsx", ".xlsm", ".xlsb"],
    },
    "is_network_category": {
        "label": "IS Network Category Report",
        "description": "Current IS network category/parent inventory report.",
        "extensions": [".csv", ".xlsx", ".xlsm", ".xlsb"],
    },
    "is_server_category": {
        "label": "IS Server Category Report",
        "description": "Current IS server category/parent inventory report.",
        "extensions": [".csv", ".xlsx", ".xlsm", ".xlsb"],
    },
    "catalog_os": {
        "label": "IS Product Catalog Operating System",
        "description": "Authoritative operating-system product catalog.",
        "extensions": [".csv", ".xlsx", ".xlsm", ".xlsb"],
    },
    "catalog_network": {
        "label": "IS Product Catalog Network",
        "description": "Authoritative network hardware product catalog.",
        "extensions": [".csv", ".xlsx", ".xlsm", ".xlsb"],
    },
    "catalog_server": {
        "label": "IS Product Catalog Server",
        "description": "Authoritative server hardware product catalog.",
        "extensions": [".csv", ".xlsx", ".xlsm", ".xlsb"],
    },
    "field_mapping": {
        "label": "Field List and Mapping",
        "description": "Optional field intelligence workbook containing Field List and Field Mapping sheets.",
        "extensions": [".xlsx", ".xlsm"],
    },
    "bulk_template": {
        "label": "Bulk Load Template",
        "description": "IS bulk-load template used when generating controlled load files.",
        "extensions": [".xlsx", ".xlsm"],
    },
}


OPERATION_REQUIREMENTS = {
    "reconcile_network": ["nw_cmdb", "is_os", "catalog_os"],
    "reconcile_server": ["server_cmdb", "is_os", "catalog_os"],
    "run_hardware_governance_network": ["nw_cmdb", "is_network_category", "catalog_network"],
    "run_hardware_governance_server": ["server_cmdb", "is_server_category", "catalog_server"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResourceManager:
    def __init__(self, registry_path: Path | None = None, upload_dir: Path | None = None):
        self.registry_path = registry_path or REGISTRY_PATH
        self.upload_dir = upload_dir or UPLOAD_DIR
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return {"resources": {}}
        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("resources"), dict):
                return data
        except (OSError, ValueError, TypeError):
            pass
        return {"resources": {}}

    def _save(self) -> None:
        tmp = self.registry_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        tmp.replace(self.registry_path)

    def register_upload(self, kind: str, file_name: str, content: bytes) -> ResourceRecord:
        spec = RESOURCE_TYPES.get(kind)
        if not spec:
            raise ValueError(f"Unsupported resource type: {kind}")
        suffix = Path(file_name).suffix.lower()
        if suffix not in spec["extensions"]:
            allowed = ", ".join(spec["extensions"])
            raise ValueError(f"{spec['label']} requires one of: {allowed}")
        if not content:
            raise ValueError("Uploaded file is empty")

        digest = hashlib.sha256(content).hexdigest()
        resource_id = "RES-" + uuid.uuid4().hex[:12].upper()
        safe_name = Path(file_name).name.replace("\\", "_").replace("/", "_")
        stored = self.upload_dir / f"{resource_id}__{safe_name}"
        stored.write_bytes(content)
        record = ResourceRecord(
            resource_id=resource_id,
            kind=kind,
            file_name=safe_name,
            stored_path=str(stored.resolve()),
            size=len(content),
            sha256=digest,
            uploaded_at=_now(),
        )
        self._data["resources"][resource_id] = asdict(record)
        self._save()
        return record

    def get(self, resource_id: str) -> ResourceRecord | None:
        raw = self._data["resources"].get(resource_id)
        if not raw:
            return None
        path = Path(raw.get("stored_path", ""))
        if not path.exists():
            raw["status"] = "MISSING"
            return ResourceRecord(**raw)
        return ResourceRecord(**raw)

    def list(self, kind: str | None = None) -> list[ResourceRecord]:
        items = [ResourceRecord(**x) for x in self._data["resources"].values()]
        if kind:
            items = [x for x in items if x.kind == kind]
        return sorted(items, key=lambda x: x.uploaded_at, reverse=True)

    def path_for(self, resource_id: str) -> str:
        record = self.get(resource_id)
        if record is None:
            raise FileNotFoundError(f"Resource not found: {resource_id}")
        if record.status != "AVAILABLE":
            raise FileNotFoundError(f"Resource file is unavailable: {resource_id}")
        return record.stored_path

    def resolve_requirements(self, operation: str, resources: dict[str, str] | None = None) -> dict[str, Any]:
        required = OPERATION_REQUIREMENTS.get(operation, [])
        supplied = resources or {}
        missing = []
        resolved = {}
        for kind in required:
            resource_id = supplied.get(kind)
            if not resource_id:
                missing.append({
                    "kind": kind,
                    "label": RESOURCE_TYPES[kind]["label"],
                    "description": RESOURCE_TYPES[kind]["description"],
                    "extensions": RESOURCE_TYPES[kind]["extensions"],
                })
                continue
            try:
                record = self.get(resource_id)
                if record is None or record.status != "AVAILABLE":
                    raise FileNotFoundError(resource_id)
                if record.kind != kind:
                    raise ValueError(f"{resource_id} is {record.kind}, expected {kind}")
                resolved[kind] = record
            except (FileNotFoundError, ValueError):
                missing.append({
                    "kind": kind,
                    "label": RESOURCE_TYPES[kind]["label"],
                    "description": RESOURCE_TYPES[kind]["description"],
                    "extensions": RESOURCE_TYPES[kind]["extensions"],
                })
        return {"ready": not missing, "required": required, "missing": missing, "resolved": resolved}

    def public_catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "kind": kind,
                "label": spec["label"],
                "description": spec["description"],
                "extensions": spec["extensions"],
            }
            for kind, spec in RESOURCE_TYPES.items()
        ]
