#!/usr/bin/env python3
"""Safely patch the Prod V1 Tkinter close_app method into GovernanceApp.
Usage:
  python fix_prod_v1_close_app.py "C:\\path\\wpp_enterprise_cmdb_inventory_prod_v1.py"
A timestamped backup is created before modification.
"""
from __future__ import annotations
import ast
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

METHOD = '''
        def close_app(self) -> None:
            """Close the Tkinter application without leaving a foreground process."""
            try:
                shutdown_event = getattr(self, "shutdown_event", None)
                if shutdown_event is not None:
                    shutdown_event.set()
            except Exception:
                pass

            worker = getattr(self, "worker", None)
            if worker is not None and worker.is_alive() and not worker.daemon:
                # Do not block the Tkinter thread. Poll briefly while allowing the
                # worker to observe shutdown_event, then close the UI.
                self.after(100, self.close_app)
                return

            try:
                self.quit()
            finally:
                self.destroy()

'''

def main() -> int:
    source = Path(sys.argv[1] if len(sys.argv) > 1 else "wpp_enterprise_cmdb_inventory_prod_v1.py").expanduser().resolve()
    if not source.is_file():
        print(f"ERROR: File not found: {source}", file=sys.stderr)
        return 2

    text = source.read_text(encoding="utf-8")
    tree = ast.parse(text)
    app = next((n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "GovernanceApp"), None)
    if app is None:
        print("ERROR: class GovernanceApp was not found.", file=sys.stderr)
        return 3

    if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "close_app" for n in app.body):
        print("No change required: GovernanceApp.close_app already exists.")
        return 0

    class_line = text.splitlines()[app.lineno - 1]
    class_indent = class_line[: len(class_line) - len(class_line.lstrip())]
    method_indent = class_indent + "    "

    # Insert before the first class method after __init__ where possible. This keeps
    # close_app inside GovernanceApp and avoids the original AttributeError.
    lines = text.splitlines(keepends=True)
    insert_at = None
    for node in app.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name != "__init__":
            insert_at = node.lineno - 1
            break
    if insert_at is None:
        insert_at = app.end_lineno

    rendered = METHOD.replace("        ", method_indent)
    lines.insert(insert_at, rendered)
    patched = "".join(lines)

    # Validate before replacing the source.
    ast.parse(patched)
    backup = source.with_name(f"{source.stem}.backup_{datetime.now():%Y%m%d_%H%M%S}{source.suffix}")
    shutil.copy2(source, backup)
    source.write_text(patched, encoding="utf-8")
    compile(patched, str(source), "exec")

    print(f"PATCHED: {source}")
    print(f"BACKUP : {backup}")
    print("VALIDATION: Python syntax passed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
