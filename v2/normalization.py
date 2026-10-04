"""Pure V2 shared normalization and field-resolution utilities.

This module is intentionally independent of the V1.4.1 adapter.  The
implementations are extracted verbatim in behavior from the V1.4.1 golden
engine so the migration boundary can be tested explicitly.
"""
from __future__ import annotations

import ipaddress
import re
from typing import Any, Optional, Tuple

import pandas as pd


def clean(v: Any) -> str:
    return "" if pd.isna(v) else re.sub(r"\s+", " ", str(v).strip())


def hkey(v: Any) -> str:
    return re.sub(r"[\s_.-]+", "", clean(v).lower())


def pkey(v: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", clean(v).lower())


def vkey(v: Any) -> str:
    s = clean(v).lower()
    return re.sub(r"\d+", lambda m: str(int(m.group())), s) if s else ""


def lifecycle(v: Any) -> str:
    return {
        "operational": "operational",
        "endoflife": "end of life",
        "eol": "end of life",
        "production": "production",
        "installed": "installed",
        "deploy": "deploy",
        "design": "design",
    }.get(pkey(v), clean(v).lower())


SERIAL_PLACEHOLDER_KEYS = {
    "", "na", "nan", "none", "null", "nil", "unknown",
    "notavailable", "notapplicable", "notprovided", "notpresent",
    "notknown", "tbd", "navirtual", "nonevirtual", "unknownvirtual",
    "notavailablevirtual", "notapplicablevirtual",
}


def serial_key(v: Any) -> str:
    """Return a deduplication key only for a real serial identifier.

    Inventory placeholders such as NA, N/A, NA Virtual, N/A virtual,
    None and equivalent normalized forms are absence, not identifiers.
    The original display value is intentionally preserved in output;
    only the identity key is blank.
    """
    key = re.sub(r"[^a-z0-9]", "", clean(v).lower())
    if key in SERIAL_PLACEHOLDER_KEYS:
        return ""
    if key.endswith("virtual") and key[:-7] in {
        "na", "none", "unknown", "notavailable", "notapplicable"
    }:
        return ""
    return key


def normalize_hostname(v: Any) -> str:
    return clean(v).replace("/", "_")


def normalize_fqdn(v: Any) -> str:
    return clean(v).replace("/", "_").lower().strip(".")


def valid_fqdn(v: Any) -> str:
    s = normalize_fqdn(v)
    invalid = {
        "",
        "domainnamenotconfigured",
        "domainnamenotapplicable",
        "notapplicable",
        "na",
        "workgroup",
        "workgroupserver",
    }
    return s if pkey(s) not in invalid and "." in s and " " not in s else ""


def normalize_ipv4(v: Any) -> Tuple[str, str, str]:
    raw = clean(v)
    if pkey(raw) in {"stack", "standby", "na", "notapplicable", "notconfigured", "none"}:
        return "", "Placeholder removed", ""
    found = []
    for token in re.findall(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", raw):
        try:
            ipaddress.IPv4Address(token)
            found.append(token)
        except ValueError:
            pass
    if not found:
        return "", ("No valid IPv4 found - review required" if raw else ""), ""
    if len(found) > 1:
        return found[0], "Multiple IP found, kept the first one, review required", ", ".join(found[1:])
    return found[0], ("IP normalized" if found[0] != raw else ""), ""


def split_product_version(v: Any) -> Tuple[str, str]:
    raw = clean(v)
    match = re.search(
        r"(?<!\d)(\d{4}|\d+(?:\.\d+)+(?:\([^)]+\))*[A-Za-z0-9_.()\-]*)\s*$",
        raw,
    )
    if not match:
        return raw, ""
    name = clean(raw[:match.start()])
    version = clean(match.group(1))
    return (name, version) if name else (raw, "")


def find_col(df: pd.DataFrame, *aliases: str, required: bool = True) -> Optional[str]:
    index = {hkey(c): c for c in df.columns}
    for alias in aliases:
        if hkey(alias) in index:
            return index[hkey(alias)]
    if required:
        raise ValueError("Required field not found. Expected one of: " + ", ".join(aliases))
    return None


def sanitize_serial_placeholders(df: pd.DataFrame, aliases: tuple[str, ...] = ("Serial number", "Serial Number", "os_parent_serial_number", "server_serial_number", "network_serial_number")) -> pd.DataFrame:
    """Blank known serial placeholders before any identity/deduplication check."""
    result = df.copy()
    for column in result.columns:
        if hkey(column) not in {hkey(alias) for alias in aliases}:
            continue
        result[column] = result[column].map(lambda value: "" if not serial_key(value) else value)
    return result

def normalize_identity(
    hostname: Any = "", fqdn: Any = "", serial: Any = "", ip: Any = ""
) -> dict:
    """Build a canonical identity dictionary from the shared normalizers."""
    return {
        "hostname": normalize_hostname(hostname),
        "fqdn": normalize_fqdn(fqdn),
        "valid_fqdn": valid_fqdn(fqdn),
        "serial_number": serial_key(serial),
        "ip_address": normalize_ipv4(ip)[0],
    }
