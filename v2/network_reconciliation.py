"""Network Reconciliation V2 capability executor.

This module is the first real extraction of the V1.4.1 network reconciliation
algorithm. The protected V1.4.1 file remains the behavioral oracle.

Authority readiness is intentionally False until the remaining shared dependencies
are independently owned by V2 and the migration evidence gate approves execution.
"""
from __future__ import annotations

import re
from typing import Any, Tuple

import pandas as pd

from .normalization import clean, pkey, vkey, lifecycle, serial_key, find_col, split_product_version

CURATED_FIRMWARE_CATALOG_MAP = {
    pkey("NSX-T 3.2.1"): ("vmware nsx contoroller", "3.2.0.1", "broadcom"),
    pkey("NSX 22.1.5"): ("vmware nsx advanced load balancer", "22.1", "broadcom"),
    pkey("NSX 4.1.0"): ("vmware nsx edge", "4.1.0", "broadcom"),
    pkey("NSX 4.2.1.4"): ("vmware nsx", "4.2.1.4", "broadcom"),
    pkey("MX OS MX 18.211.5"): ("cisco meraki", "mx 18.2.11", "cisco"),
}


def normalize_firmware_catalog_identity(firmware: Any) -> Tuple[str, str, str, str]:
    raw = clean(firmware)
    if not raw:
        return "", "", "", "BLANK FIRMWARE"
    curated = CURATED_FIRMWARE_CATALOG_MAP.get(pkey(raw))
    if curated:
        return curated[0], curated[1], curated[2], "CURATED VERIFIED MAPPING"

    match = re.match(r"^(MR|MX|MS)\s+OS(?:\s+\1)?\s+(.+?)\s*$", raw, re.I)
    if match:
        family = match.group(1).lower()
        return "cisco meraki", f"{family} {clean(match.group(2)).lower()}", "cisco", "MERAKI FAMILY NORMALIZATION"

    match = re.match(r"^Infoblox\s+NIOS\s+([0-9]+(?:\.[0-9]+)+)(?:-[A-Za-z0-9._-]+)?\s*$", raw, re.I)
    if match:
        return "nios", match.group(1), "infoblox", "INFOBLOX BUILD NORMALIZATION"

    families = [
        (r"^Cisco\s+IOS-XE\s+(.+)$", "cisco ios-xe"),
        (r"^Cisco\s+IOS\s+(.+)$", "cisco ios"),
        (r"^Cisco\s+FXOS\s+(.+)$", "cisco fx-os"),
        (r"^Cisco\s+ASA\s+(.+)$", "cisco asa"),
        (r"^Cisco\s+NXOS\s+(.+)$", "cisco nx-os"),
        (r"^Cisco\s+ISE\s+(.+)$", "cisco ise"),
        (r"^Cisco\s+AireOS\s+(.+)$", "cisco aireos"),
    ]
    for pattern, product in families:
        match = re.match(pattern, raw, re.I)
        if not match:
            continue
        version = clean(match.group(1)).lower()
        version = re.sub(r"\s+ESW\d+\s*$", "", version, flags=re.I)
        version = re.sub(r"\.([a-z])$", r"\1", version, flags=re.I)
        return product, version, "cisco", "NETWORK FAMILY NORMALIZATION"

    product, version = split_product_version(raw)
    return product, version, "", "STANDARD PARSER"


def catalog_index(cat: pd.DataFrame, fi: Any):
    pc = fi.field("operating_system_name", "IS Product Catalog Operating System", cat)
    vc = fi.field("operating_system_version", "IS Product Catalog Operating System", cat)
    pr = fi.field("operating_system_provider", "IS Product Catalog Operating System", cat, False)
    exact, base = {}, {}
    for _, row in cat.iterrows():
        record = {
            "name": clean(row[pc]),
            "version": clean(row[vc]),
            "provider": clean(row[pr]) if pr else "",
        }
        exact.setdefault(pkey(record["name"]) + "|" + vkey(record["version"]), record)
        base.setdefault(
            pkey(record["name"]) + "|" +
            re.sub(r"(?<=\d)[a-z]+$", "", vkey(record["version"])),
            record,
        )
    return exact, base


def reconcile_nw(cm, isr, cat, fi, progress=lambda m, p: None):
    progress("Resolving NW fields through Field Intelligence", 10)
    ci = fi.field("hostname", "NW CMDB Report", cm)
    cls = fi.field("class", "NW CMDB Report", cm)
    life_c = fi.field("os_lifecycle_status", "NW CMDB Report", cm)
    ip = fi.field("ip_address", "NW CMDB Report", cm)
    fq = fi.field("fully_qualified_hostname", "NW CMDB Report", cm, False)
    serial = fi.field("os_parent_serial_number", "NW CMDB Report", cm)
    manuf = fi.field("os_parent_manufacturer", "NW CMDB Report", cm, False)
    firmware = find_col(cm, "Firmware version", "Firmware Version")

    def opt(*aliases):
        column = find_col(cm, *aliases, required=False)
        return cm[column] if column else ""

    out = pd.DataFrame({
        "Configuration Item": cm[ci],
        "Class": cm[cls],
        "Life Cycle Stage": cm[life_c],
        "Life Cycle Stage Status": opt("Life Cycle Stage Status"),
        "Manufacturer": cm[manuf] if manuf else "",
        "Model ID": opt("Model ID"),
        "Model.Name": opt("Model.Name", "Model Name"),
        "Model number": opt("Model number"),
        "Serial number": cm[serial],
        "IP Address": cm[ip],
        "Firmware version": cm[firmware],
        "Fully qualified domain name": cm[fq] if fq else "",
    })
    parsed = out["Firmware version"].map(normalize_firmware_catalog_identity).apply(pd.Series)
    parsed.columns = [
        "Parsed Firmware Name", "Parsed Firmware Version",
        "Parsed Firmware Provider", "Firmware Mapping Method",
    ]
    out = pd.concat([out, parsed], axis=1)

    exact, base = catalog_index(cat, fi)
    ih = fi.field("hostname", "IS Operating System Report", isr)
    isn = fi.field("os_parent_serial_number", "IS Operating System Report", isr)
    il = fi.field("os_lifecycle_status", "IS Operating System Report", isr)
    io = find_col(isr, "os_opaque_id", "OS Opaque ID", required=False)
    ion = fi.field("operating_system_name", "IS Operating System Report", isr)
    iov = fi.field("operating_system_version", "IS Operating System Report", isr)
    iop = fi.field("operating_system_provider", "IS Operating System Report", isr, False)

    host_map, serial_map = {}, {}
    for index, row in isr.iterrows():
        if clean(row[ih]):
            host_map.setdefault(clean(row[ih]).lower(), index)
        if serial_key(row[isn]):
            serial_map.setdefault(serial_key(row[isn]), index)

    rows = []
    total = max(len(out), 1)
    progress("Reconciling NW CMDB and IS", 25)
    for position, (_, row) in enumerate(out.iterrows(), 1):
        if position == 1 or position == total or position % 500 == 0:
            progress(
                f"Reconciling NW records: {position} of {len(out)}",
                25 + int(position / total * 40),
            )
        name = clean(row["Configuration Item"])
        index = next(
            (
                host_map[key]
                for key in (
                    name.lower(),
                    name.replace("/", "_").lower(),
                    name.replace("/", "-").lower(),
                )
                if key in host_map
            ),
            None,
        )
        mode = "Hostname Match" if index is not None else ""
        if index is None and serial_key(row["Serial number"]) in serial_map:
            index = serial_map[serial_key(row["Serial number"])]
            mode = "Serial Match Different Hostname"

        present = index is not None
        is_row = isr.iloc[index] if present else None
        key = pkey(row["Parsed Firmware Name"]) + "|" + vkey(row["Parsed Firmware Version"])
        hit = exact.get(key)
        status = "Match"
        if not hit:
            hit = base.get(
                pkey(row["Parsed Firmware Name"]) + "|" +
                re.sub(r"(?<=\d)[a-z]+$", "", vkey(row["Parsed Firmware Version"]))
            )
            status = "Closest Match Proposed" if hit else "No Match"
        hit = hit or {}
        osmatch = bool(
            present and hit and
            pkey(is_row[ion]) == pkey(hit.get("name")) and
            vkey(is_row[iov]) == vkey(hit.get("version"))
        )
        life = lifecycle(row["Life Cycle Stage"])
        actions = []
        classification = "ACTIVE OR REVIEW"
        reason = ""

        if life == "end of life" and not present:
            actions = ["Retired Device - No Action Required"]
            classification = "RETIRED DEVICE - NOT PRESENT IN IS"
            reason = "CMDB DEVICE IS END OF LIFE AND NO ACTIVE IS OS RECORD EXISTS"
        else:
            if status == "No Match":
                actions.append("Catalogue update required")
            if present and hit and not osmatch:
                actions.append("Inventory OS update required")
            if life == "operational" and not present:
                actions.append("Load To IS")
            if life == "end of life" and present and lifecycle(is_row[il]) in {"production", "installed"}:
                actions.append("Retire From IS")

        result = row.to_dict()
        result.update({
            "Present in IS ?": "Yes - " + mode if present else "No",
            "Host name in IS": clean(is_row[ih]) if present else "",
            "os_opaque_id": clean(is_row[io]) if present and io else "",
            "os_parent_serial_number": clean(is_row[isn]) if present else "",
            "Lifecycle Status in IS": clean(is_row[il]) if present else "",
            "Current operating_system_provider": clean(is_row[iop]) if present and iop else "",
            "Current operating_system_name": clean(is_row[ion]) if present else "",
            "Current operating_system_version": clean(is_row[iov]) if present else "",
            "Catalogue Match?": status,
            "Required operating_system_provider": hit.get("provider", ""),
            "Required operating_system_name": hit.get("name", ""),
            "Required operating_system_version": hit.get("version", ""),
            "Device Classification": classification,
            "Action Reason": reason,
            "Action": "; ".join(actions) or "No Action",
        })
        rows.append(result)

    progress("NW reconciliation complete", 68)
    return pd.DataFrame(rows)


class NetworkReconciliationExecutor:
    capability = "NETWORK_RECONCILIATION"
    engine = "V2"
    authority_ready = False

    def execute(self, cm, isr, cat, fi, progress=None):
        return reconcile_nw(cm, isr, cat, fi, progress or (lambda m, p: None))
