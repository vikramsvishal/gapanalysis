#!/usr/bin/env python3
"""Fix V1.2 Server progress labels and zero-byte/locked Excel outputs.

Usage:
  python V1_2_Server_Output_Integrity_Fix.py "C:\\path\\WPP_CMDB_IS_Gap_Analysis_V1_2.py"

The patch creates a timestamped backup and validates the resulting application.
"""
from __future__ import annotations
import ast
import shutil
import sys
from datetime import datetime
from pathlib import Path

ATOMIC_WRITER = r'''def _next_retry_path(path: str) -> str:
    """Return the next V-number for a versioned output path."""
    candidate = Path(path)
    match = re.match(r"^(.*) - V(\\d+)(\\.[^.]+)$", candidate.name, re.I)
    if not match:
        return str(candidate.with_name(candidate.stem + " - retry" + candidate.suffix))
    stem, version, suffix = match.groups()
    return str(candidate.with_name(f"{stem} - V{int(version) + 1}{suffix}"))


def _apply_excel_formatting(workbook) -> None:
    """Format an open workbook in memory; the caller performs the only disk save."""
    navy = PatternFill("solid", fgColor="1F4E78")
    metadata_fill = PatternFill("solid", fgColor="D9EAF7")
    alternate_fill = PatternFill("solid", fgColor="F7F9FC")
    load_fill = PatternFill("solid", fgColor="E2F0D9")
    retire_fill = PatternFill("solid", fgColor="F4CCCC")
    white_bold = Font(name="Aptos", size=10, color="FFFFFF", bold=True)
    normal_font = Font(name="Aptos", size=9, color="000000")
    metadata_font = Font(name="Aptos", size=9, color="1F1F1F", italic=True)
    thin = Side(style="thin", color="D9E2F3")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for worksheet in workbook.worksheets:
        worksheet.sheet_view.showGridLines = False
        worksheet.sheet_view.zoomScale = 90
        worksheet.freeze_panes = "A2"
        worksheet.row_dimensions[1].height = 34
        for cell in worksheet[1]:
            cell.fill = navy
            cell.font = white_bold
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border

        metadata_row = False
        if worksheet.max_row >= 2:
            values = [pkey(cell.value) for cell in worksheet[2] if clean(cell.value)]
            recognized = sum(v in {"mandatory", "optional", "required", "reference", "recommended"} for v in values)
            metadata_row = bool(values) and recognized >= max(1, len(values) // 2)
        if metadata_row:
            worksheet.freeze_panes = "A3"
            for cell in worksheet[2]:
                cell.fill = metadata_fill
                cell.font = metadata_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = border

        first_data_row = 3 if metadata_row else 2
        for row_index in range(first_data_row, worksheet.max_row + 1):
            for cell in worksheet[row_index]:
                cell.font = normal_font
                cell.border = border
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                if row_index % 2 == 0:
                    cell.fill = alternate_fill

        if worksheet.title.lower() == "summary":
            metric_col = next((c for c in range(1, worksheet.max_column + 1) if pkey(worksheet.cell(1, c).value) == "metric"), None)
            if metric_col:
                for row_index in range(2, worksheet.max_row + 1):
                    metric = pkey(worksheet.cell(row_index, metric_col).value)
                    if "loadtoisrecords" in metric:
                        worksheet.cell(row_index, metric_col).fill = load_fill
                    elif "retirefromisrecords" in metric:
                        worksheet.cell(row_index, metric_col).fill = retire_fill

        sample_end = min(worksheet.max_row, 250)
        for column_index in range(1, worksheet.max_column + 1):
            longest = len(clean(worksheet.cell(1, column_index).value))
            for row_index in range(2, sample_end + 1):
                value = worksheet.cell(row_index, column_index).value
                if value is not None:
                    longest = max(longest, max((len(line) for line in str(value).splitlines()), default=0))
            worksheet.column_dimensions[get_column_letter(column_index)].width = min(max(longest + 2, 12), 45)
        if worksheet.max_row and worksheet.max_column:
            worksheet.auto_filter.ref = worksheet.dimensions
        worksheet.page_setup.orientation = "landscape"
        worksheet.page_setup.fitToWidth = 1
        worksheet.page_setup.fitToHeight = 0
        worksheet.sheet_properties.pageSetUpPr.fitToPage = True
        worksheet.print_title_rows = "1:1"


def _atomic_excel_write(requested_path: str, sheets: Dict[str, pd.DataFrame]) -> str:
    """Write to a private temporary file, then publish atomically with V-number retry."""
    requested = Path(requested_path).resolve()
    requested.parent.mkdir(parents=True, exist_ok=True)
    final_path = requested

    for attempt in range(1, 100):
        while final_path.exists():
            final_path = Path(_next_retry_path(str(final_path)))
        temp_path = final_path.with_name(f".{final_path.stem}.{os.getpid()}.{threading.get_ident()}.tmp.xlsx")
        try:
            with pd.ExcelWriter(temp_path, engine="openpyxl") as writer:
                for name, dataframe in sheets.items():
                    safe_name = re.sub(r"[\\[\\]:*?/\\\\]", "-", str(name))[:31] or "Sheet1"
                    data = dataframe if dataframe is not None and len(dataframe) else pd.DataFrame(columns=["No records"])
                    data.to_excel(writer, index=False, sheet_name=safe_name)
                _apply_excel_formatting(writer.book)

            # Reject incomplete output before publishing it.
            if not temp_path.exists() or temp_path.stat().st_size < 1000:
                raise IOError(f"Temporary workbook is incomplete: {temp_path}")
            check = load_workbook(temp_path, read_only=True, data_only=False)
            check.close()

            try:
                os.replace(temp_path, final_path)
                return str(final_path)
            except PermissionError:
                # The chosen target became locked after allocation. Retry with V+1.
                final_path = Path(_next_retry_path(str(final_path)))
                continue
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
    raise PermissionError(f"Unable to publish a workbook after version retries in: {requested.parent}")


def write_workbook(path: str, sheets: Dict[str, pd.DataFrame]) -> str:
    return _atomic_excel_write(path, sheets)


def _write_formatted_load(dataframe: pd.DataFrame, path: str) -> str:
    return _atomic_excel_write(path, {"Load": dataframe})

'''

SERVER = r'''def reconcile_server(cm, isr, cat, fi, progress=lambda m,p:None):
    progress("Resolving Server fields through Field Intelligence", 10)
    support=find_col(cm,"Support Group",required=False); managed=find_col(cm,"Managed by Group","Managed By Group",required=False)
    if not support and not managed: raise ValueError("Server CMDB requires Support Group or Managed By Group for W-KYN scoping")
    scope=pd.Series(False,index=cm.index)
    if support: scope |= cm[support].map(clean).str.upper().str.startswith("W-KYN")
    if managed: scope |= cm[managed].map(clean).str.upper().str.startswith("W-KYN")
    scoped=cm[scope].copy().reset_index(drop=True); outside=cm[~scope].copy().reset_index(drop=True)
    if scoped.empty: return pd.DataFrame(),outside,pd.DataFrame(),pd.DataFrame()
    name=fi.field("hostname","Server CMDB Report",scoped); life=fi.field("os_lifecycle_status","Server CMDB Report",scoped); ip=fi.field("ip_address","Server CMDB Report",scoped)
    serial=fi.field("os_parent_serial_number","Server CMDB Report",scoped,False); osn=fi.field("operating_system_name","Server CMDB Report",scoped); osv=fi.field("operating_system_version","Server CMDB Report",scoped)
    fq=fi.field("fully_qualified_hostname","Server CMDB Report",scoped,False); cls=fi.field("class","Server CMDB Report",scoped,False)
    lstat=find_col(scoped,"Life Cycle Stage Status",required=False); man=find_col(scoped,"Manufacturer",required=False); mid=find_col(scoped,"Model ID",required=False); attrs=find_col(scoped,"Attribute Field Value","Attributes",required=False)
    category=find_col(scoped,"Category",required=False); subcategory=find_col(scoped,"Subcategory",required=False)
    base=pd.DataFrame({"Configuration Item":scoped[name],"Class":scoped[cls] if cls else "Server","Life Cycle Stage":scoped[life],"Life Cycle Stage Status":scoped[lstat] if lstat else "","Manufacturer":scoped[man] if man else "","Model ID":scoped[mid] if mid else "","Model.Name":"","Model number":"","Serial number":scoped[serial] if serial else "","IP Address":scoped[ip],"Firmware version":scoped[osn].map(clean)+" "+scoped[osv].map(clean),"Fully qualified domain name":scoped[fq] if fq else scoped[name],"category":scoped[category] if category else "Server","subcategory":scoped[subcategory] if subcategory else "Server","Attribute Field Value":scoped[attrs] if attrs else ""})
    base["_name_key"]=base["Configuration Item"].map(pkey); base["_life_key"]=base["Life Cycle Stage"].map(lifecycle)
    duplicates=base[base.duplicated(["_name_key","_life_key"],False)].copy();base=base.drop_duplicates(["_name_key","_life_key"],keep="first")
    active=set(base.loc[base["_life_key"]=="operational","_name_key"]);historical=base[(base["_life_key"]=="end of life") & base["_name_key"].isin(active)].copy();eligible=base[~((base["_life_key"]=="end of life") & base["_name_key"].isin(active))].copy()
    context=eligible[["Configuration Item","category","subcategory","Attribute Field Value"]].reset_index(drop=True);standardized=eligible.drop(columns=["_name_key","_life_key","category","subcategory","Attribute Field Value"])
    def server_progress(message,pct):
        translations={"Resolving NW fields through Field Intelligence":"Preparing Server reconciliation fields","Reconciling NW CMDB and IS":"Reconciling Server CMDB and IS","NW reconciliation complete":"Server reconciliation complete"}
        progress(translations.get(message,message.replace("NW","Server")),pct)
    result=reconcile_nw(standardized,isr,cat,fi,server_progress)
    for c in context.columns[1:]: result[c]=context[c].values
    return result,outside,duplicates,historical

'''

def replace_functions(source: str, replacements: dict[str,str]) -> str:
    tree=ast.parse(source);lines=source.splitlines(keepends=True)
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in replacements]
    for node in sorted(nodes,key=lambda n:n.lineno,reverse=True):
        lines[node.lineno-1:node.end_lineno]=[replacements[node.name]]
    return ''.join(lines)

def main():
    target=Path(sys.argv[1] if len(sys.argv)>1 else "WPP_CMDB_IS_Gap_Analysis_V1_2.py").expanduser().resolve()
    if not target.is_file():print(f"ERROR: File not found: {target}",file=sys.stderr);return 2
    source=target.read_text(encoding="utf-8");ast.parse(source)
    source=replace_functions(source,{"reconcile_server":SERVER})
    # Remove all legacy writer functions then insert the atomic writer as one block.
    tree=ast.parse(source);names={"_format_excel_workbook","_apply_excel_formatting","write_workbook","_write_formatted_load","_atomic_excel_write","_next_retry_path"};lines=source.splitlines(keepends=True)
    for node in sorted([n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],key=lambda n:n.lineno,reverse=True):del lines[node.lineno-1:node.end_lineno]
    source=''.join(lines);marker="# -------------------------- persistent resource manager --------------------------";source=source.replace(marker,ATOMIC_WRITER+"\n"+marker,1)
    # UI callers must use the actual returned path if a V-number retry occurred.
    source=source.replace('write_workbook(p,{"Summary":nw_summary(r)', 'p=write_workbook(p,{"Summary":nw_summary(r)')
    source=source.replace('write_workbook(p,{"Summary":server_summary(r,outside,dups,historical)', 'p=write_workbook(p,{"Summary":server_summary(r,outside,dups,historical)')
    # Balance the added assignment wrappers at the end of the two dict calls.
    source=source.replace('"Catalogue Update Required":r[r.Action.str.contains("Catalogue update required",na=False)]});self.say("Created: "+p)', '"Catalogue Update Required":r[r.Action.str.contains("Catalogue update required",na=False)]});self.say("Created: "+p)',1)
    ast.parse(source);compile(source,str(target),'exec')
    backup=target.with_name(f"{target.stem}.backup_integrity_{datetime.now():%Y%m%d_%H%M%S}{target.suffix}");shutil.copy2(target,backup);target.write_text(source,encoding="utf-8")
    print(f"PATCHED: {target}\nBACKUP : {backup}\nFIXES  : Server-only progress labels + atomic zero-byte-safe workbook publishing\nVALIDATION: AST and Python compilation passed");return 0
if __name__=="__main__":raise SystemExit(main())
