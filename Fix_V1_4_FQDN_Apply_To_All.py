#!/usr/bin/env python3
"""Patch V1.4 to ask the missing-FQDN question once per bulk-load run.

Usage:
  python Fix_V1_4_FQDN_Apply_To_All.py "C:\\path\\WPP_CMDB_IS_Gap_Analysis_V1_4.py"
"""
from __future__ import annotations
import ast
import shutil
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "WPP_CMDB_IS_Gap_Analysis_V1_4.py").expanduser().resolve()
    if not target.is_file():
        print(f"ERROR: File not found: {target}", file=sys.stderr)
        return 2

    source = target.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "generate_bulk_load"), None)
    if fn is None:
        print("ERROR: generate_bulk_load function not found", file=sys.stderr)
        return 3

    lines = source.splitlines(keepends=True)
    block = "".join(lines[fn.lineno - 1:fn.end_lineno])

    old = 'if not fq and askfq(1):'
    if old not in block:
        if 'include_missing_fqdn' in block:
            print("INFO: Apply-to-all FQDN logic is already present")
            return 0
        print("ERROR: Expected per-device FQDN prompt was not found", file=sys.stderr)
        return 4

    loop_markers = [
        'for pos,(r,d) in enumerate(eligible,1):',
        'for pos, (r, d) in enumerate(eligible, 1):',
    ]
    marker = next((m for m in loop_markers if m in block), None)
    if marker is None:
        print("ERROR: Eligible-row loop was not found", file=sys.stderr)
        return 5

    decision = (
        'missing_fqdn_count=sum(1 for candidate,_decision in eligible '
        'if not valid_fqdn(candidate["Fully qualified domain name"]))\n'
        '    include_missing_fqdn=askfq(missing_fqdn_count) if missing_fqdn_count else False\n'
        '    progress(f"FQDN decision applied to all candidates; missing: {missing_fqdn_count}",18)\n'
        '    '
    )
    block = block.replace(marker, decision + marker, 1)
    block = block.replace(old, 'if not fq and include_missing_fqdn:', 1)
    lines[fn.lineno - 1:fn.end_lineno] = [block]
    patched = "".join(lines)

    ast.parse(patched)
    compile(patched, str(target), "exec")
    backup = target.with_name(f"{target.stem}.backup_fqdn_all_{datetime.now():%Y%m%d_%H%M%S}{target.suffix}")
    shutil.copy2(target, backup)
    target.write_text(patched, encoding="utf-8")

    print(f"PATCHED: {target}")
    print(f"BACKUP : {backup}")
    print("FIX    : One missing-FQDN decision per OS Bulk Load run")
    print("VALIDATION: AST and Python compilation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
