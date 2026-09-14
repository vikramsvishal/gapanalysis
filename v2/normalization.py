"""V2 normalization facade backed by the V1.4.1 golden functions."""
from __future__ import annotations

from typing import Any, Tuple

from .legacy_adapter import normalization_functions

_F = normalization_functions()
clean = _F["clean"]
hkey = _F["hkey"]
pkey = _F["pkey"]
vkey = _F["vkey"]
lifecycle = _F["lifecycle"]
serial_key = _F["serial_key"]
normalize_hostname = _F["normalize_hostname"]
normalize_fqdn = _F["normalize_fqdn"]
valid_fqdn = _F["valid_fqdn"]
normalize_ipv4 = _F["normalize_ipv4"]
split_product_version = _F["split_product_version"]
find_col = _F["find_col"]


def normalize_identity(hostname: Any = "", fqdn: Any = "", serial: Any = "", ip: Any = "") -> dict:
    """Build a canonical identity dictionary using the golden normalizers."""
    return {
        "hostname": normalize_hostname(hostname),
        "fqdn": normalize_fqdn(fqdn),
        "valid_fqdn": valid_fqdn(fqdn),
        "serial_number": serial_key(serial),
        "ip_address": normalize_ipv4(ip)[0],
    }
