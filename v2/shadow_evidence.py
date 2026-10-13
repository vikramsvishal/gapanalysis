"""Canonical fingerprints for non-authoritative engine shadow comparisons."""
from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def dataframe_fingerprint(frame: pd.DataFrame) -> str:
    columns = sorted(str(column) for column in frame.columns)
    rows = []
    for _, row in frame.iterrows():
        rows.append([None if pd.isna(row[column]) else str(row[column]) for column in columns])
    return sha256_json({"columns": columns, "rows": rows})


def resource_input_fingerprint(resources: Any, resource_ids: dict[str, Any]) -> str:
    records = []
    for kind, resource_id in sorted((resource_ids or {}).items()):
        resource = resources.get(resource_id) if resources is not None else None
        records.append({
            "kind": str(kind),
            "resource_id": str(resource_id),
            "resource_sha256": getattr(resource, "sha256", None),
            "resource_status": getattr(resource, "status", None),
        })
    return sha256_json(records)


def shadow_fingerprint(resources: Any, resource_ids: dict[str, Any], authoritative_result: pd.DataFrame, candidate_result: pd.DataFrame) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "input_sha256": resource_input_fingerprint(resources, resource_ids),
        "authoritative_output_sha256": dataframe_fingerprint(authoritative_result),
        "candidate_output_sha256": dataframe_fingerprint(candidate_result),
    }
