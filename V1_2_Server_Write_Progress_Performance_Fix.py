#!/usr/bin/env python3
"""Fix V1.2 slow/zero-byte Server output and add visible writing progress.

Usage:
 python V1_2_Server_Write_Progress_Performance_Fix.py "C:\\path\\WPP_CMDB_IS_Gap_Analysis_V1_2.py"
"""
from __future__ import annotations
import ast, shutil, sys
from datetime import datetime
from pathlib import Path

BLOCK = r'''_OUTPUT_PROGRESS_CALLBACK = None

def set_output_progress(callback=None) -> None:
    global _OUTPUT_PROGRESS_CALLBACK
    _OUTPUT_PROGRESS_CALLBACK = callback

def _output_progress(message: str, percentage: int) -> None:
    callback = _OUTPUT_PROGRESS_CALLBACK
    if callback:
        callback(message, percentage)

def _next_retry_path(path: str) -> str:
    candidate = Path(path)
    match = re.match(r"^(.*) - V(\d+)(\.[^.]+)$", candidate.name, re.I)
    if not match:
        return str(candidate.with_name(candidate.stem + " - V2" + candidate.suffix))
    stem, version, suffix = match.groups()
    return str(candidate.with_name(f"{stem} - V{int(version)+1}{suffix}"))

def _fast_format_workbook(workbook) -> None:
    """Apply presentation formatting without iterating through every data cell."""
    navy = PatternFill("solid", fgColor="1F4E78")
    metadata_fill = PatternFill("solid", fgColor="D9EAF7")
    load_fill = PatternFill("solid", fgColor="E2F0D9")
    retire_fill = PatternFill("solid", fgColor="F4CCCC")
    white_bold = Font(name="Aptos", size=10, color="FFFFFF", bold=True)
    metadata_font = Font(name="Aptos", size=9, color="1F1F1F", italic=True)
    thin = Side(style="thin", color="D9E2F3")
    header_border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for worksheet in workbook.worksheets:
        worksheet.sheet_view.showGridLines = False
        worksheet.sheet_view.zoomScale = 90
        worksheet.freeze_panes = "A2"
        worksheet.row_dimensions[1].height = 34
        for cell in worksheet[1]:
            cell.fill = navy; cell.font = white_bold; cell.border = header_border
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        metadata_row = False
        if worksheet.max_row >= 2:
            values = [pkey(cell.value) for cell in worksheet[2] if clean(cell.value)]
            recognized = sum(v in {"mandatory","optional","required","reference","recommended"} for v in values)
            metadata_row = bool(values) and recognized >= max(1, len(values)//2)
        if metadata_row:
            worksheet.freeze_panes = "A3"
            for cell in worksheet[2]:
                cell.fill = metadata_fill; cell.font = metadata_font; cell.border = header_border
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        if worksheet.title.lower() == "summary":
            metric_col = next((c for c in range(1, worksheet.max_column+1) if pkey(worksheet.cell(1,c).value)=="metric"), None)
            if metric_col:
                for row_index in range(2, worksheet.max_row+1):
                    metric = pkey(worksheet.cell(row_index, metric_col).value)
                    if "loadtoisrecords" in metric: worksheet.cell(row_index,metric_col).fill = load_fill
                    elif "retirefromisrecords" in metric: worksheet.cell(row_index,metric_col).fill = retire_fill

        # Width calculation is intentionally sampled for large enterprise reports.
        sample_end = min(worksheet.max_row, 100)
        for column_index in range(1, worksheet.max_column+1):
            longest = len(clean(worksheet.cell(1,column_index).value))
            for row_index in range(2, sample_end+1):
                value = worksheet.cell(row_index,column_index).value
                if value is not None: longest=max(longest,min(len(str(value)),60))
            worksheet.column_dimensions[get_column_letter(column_index)].width=min(max(longest+2,12),45)
        if worksheet.max_row and worksheet.max_column: worksheet.auto_filter.ref=worksheet.dimensions
        worksheet.page_setup.orientation="landscape";worksheet.page_setup.fitToWidth=1;worksheet.page_setup.fitToHeight=0
        worksheet.sheet_properties.pageSetUpPr.fitToPage=True;worksheet.print_title_rows="1:1"

def _publish_temp_workbook(temp_path: Path, requested_path: Path) -> str:
    if not temp_path.exists() or temp_path.stat().st_size < 1000:
        raise IOError(f"Workbook creation did not produce a valid file: {temp_path}")
    _output_progress("Validating generated Excel workbook", 96)
    check=load_workbook(temp_path,read_only=True,data_only=False);check.close()
    final_path=requested_path
    for _ in range(100):
        if final_path.exists(): final_path=Path(_next_retry_path(str(final_path)));continue
        try:
            os.replace(temp_path,final_path)
            return str(final_path)
        except PermissionError:
            final_path=Path(_next_retry_path(str(final_path)))
    raise PermissionError(f"Unable to publish a versioned workbook in {requested_path.parent}")

def _atomic_write_sheets(requested_path: str, sheets: Dict[str,pd.DataFrame]) -> str:
    requested=Path(requested_path).resolve();requested.parent.mkdir(parents=True,exist_ok=True)
    final=requested
    while final.exists(): final=Path(_next_retry_path(str(final)))
    temp=final.with_name(f".{final.stem}.{os.getpid()}.{threading.get_ident()}.part.xlsx")
    try:
        count=max(len(sheets),1)
        _output_progress("Preparing Excel output workbook",72)
        with pd.ExcelWriter(temp,engine="openpyxl") as writer:
            for index,(name,dataframe) in enumerate(sheets.items(),1):
                pct=72+int((index-1)/count*18)
                _output_progress(f"Writing worksheet {index} of {count}: {name}",pct)
                safe=re.sub(r"[\[\]:*?/\\]","-",str(name))[:31] or "Sheet1"
                data=dataframe if dataframe is not None and len(dataframe) else pd.DataFrame(columns=["No records"])
                data.to_excel(writer,index=False,sheet_name=safe)
            _output_progress("Applying Excel formatting",92)
            _fast_format_workbook(writer.book)
        published=_publish_temp_workbook(temp,final)
        _output_progress(f"Excel output saved: {Path(published).name}",100)
        return published
    finally:
        try: temp.unlink(missing_ok=True)
        except OSError: pass

def write_workbook(path: str, sheets: Dict[str,pd.DataFrame]) -> str:
    return _atomic_write_sheets(path,sheets)

def _write_formatted_load(dataframe: pd.DataFrame,path: str) -> str:
    return _atomic_write_sheets(path,{"Load":dataframe})

'''

def main():
    target=Path(sys.argv[1] if len(sys.argv)>1 else 'WPP_CMDB_IS_Gap_Analysis_V1_2.py').expanduser().resolve()
    if not target.is_file(): print(f'ERROR: File not found: {target}',file=sys.stderr);return 2
    source=target.read_text(encoding='utf-8');ast.parse(source)
    names={'_format_excel_workbook','_apply_excel_formatting','_fast_format_workbook','_next_retry_path','_publish_temp_workbook','_atomic_excel_write','_atomic_write_sheets','write_workbook','_write_formatted_load','set_output_progress','_output_progress'}
    tree=ast.parse(source);lines=source.splitlines(keepends=True)
    for node in sorted([n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],key=lambda n:n.lineno,reverse=True): del lines[node.lineno-1:node.end_lineno]
    source=''.join(lines);marker='# -------------------------- persistent resource manager --------------------------'
    if marker not in source: print('ERROR: writer insertion marker not found',file=sys.stderr);return 3
    source=source.replace(marker,BLOCK+'\n'+marker,1)
    # Activate visible progress for both reconciliation outputs and all subsequent workbook writes.
    source=source.replace('def task():\n            self._load_field_mapping();r=reconcile_nw', 'def task():\n            set_output_progress(self.progress)\n            self._load_field_mapping();r=reconcile_nw',1)
    server_marker='def task():\n            self._load_field_mapping();r,outside,dups,historical=reconcile_server'
    source=source.replace(server_marker,'def task():\n            set_output_progress(self.progress)\n            self._load_field_mapping();r,outside,dups,historical=reconcile_server',1)
    # Use actual returned version path in activity log / message.
    source=source.replace(';write_workbook(p,{"Summary":nw_summary(r)', ';p=write_workbook(p,{"Summary":nw_summary(r)',1)
    source=source.replace(';write_workbook(p,{"Summary":server_summary(r,outside,dups,historical)', ';p=write_workbook(p,{"Summary":server_summary(r,outside,dups,historical)',1)
    ast.parse(source);compile(source,str(target),'exec')
    backup=target.with_name(f'{target.stem}.backup_write_progress_{datetime.now():%Y%m%d_%H%M%S}{target.suffix}');shutil.copy2(target,backup);target.write_text(source,encoding='utf-8')
    print(f'PATCHED: {target}\nBACKUP : {backup}\nFIXES  : Fast atomic workbook publishing + visible worksheet writing progress\nVALIDATION: AST and Python compilation passed');return 0
if __name__=='__main__':raise SystemExit(main())
