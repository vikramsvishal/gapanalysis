#!/usr/bin/env python3
"""Fix V1.2 Excel saving by formatting inside the original ExcelWriter session.

This removes the second openpyxl save of the same path, which can fail on Windows
when Defender, OneDrive, Explorer preview, or another process briefly locks the file.

Usage:
  python V1_2_Single_Pass_Excel_Save_Fix.py "C:\\path\\WPP_CMDB_IS_Gap_Analysis_V1_2.py"
"""
from __future__ import annotations
import ast
import shutil
import sys
from datetime import datetime
from pathlib import Path

BLOCK = r'''def _apply_excel_formatting(workbook) -> None:
    """Format an open workbook in memory. The caller performs the only disk save."""
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
            worksheet.row_dimensions[2].height = 24
            for cell in worksheet[2]:
                cell.fill = metadata_fill
                cell.font = metadata_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = border

        first_data_row = 3 if metadata_row else 2
        for row_index in range(first_data_row, worksheet.max_row + 1):
            worksheet.row_dimensions[row_index].height = 20
            for cell in worksheet[row_index]:
                cell.font = normal_font
                cell.border = border
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                if row_index % 2 == 0:
                    cell.fill = alternate_fill

        # Summary action colours requested by the application owner.
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


def write_workbook(path: str, sheets: Dict[str, pd.DataFrame]):
    """Create and format a multi-sheet workbook with one physical save operation."""
    try:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for name, dataframe in sheets.items():
                safe_name = re.sub(r"[\\[\\]:*?/\\\\]", "-", str(name))[:31] or "Sheet1"
                data = dataframe if dataframe is not None and len(dataframe) else pd.DataFrame(columns=["No records"])
                data.to_excel(writer, index=False, sheet_name=safe_name)
            _apply_excel_formatting(writer.book)
    except PermissionError as exc:
        raise PermissionError(
            f"Windows denied creation of the output workbook: {path}. "
            "The application selected a new version, but the destination folder itself or the new file is being blocked. "
            "Choose a dedicated writable output folder outside the input-report folder."
        ) from exc


def _write_formatted_load(dataframe: pd.DataFrame, path: str) -> None:
    """Create and format a single-sheet load workbook with one physical save."""
    try:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name="Load")
            _apply_excel_formatting(writer.book)
    except PermissionError as exc:
        raise PermissionError(
            f"Windows denied creation of the load workbook: {path}. Select a dedicated writable output folder."
        ) from exc

'''

def remove_functions(source: str, names: set[str]) -> tuple[str, int]:
    tree = ast.parse(source)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if not nodes:
        return source, 0
    lines = source.splitlines(keepends=True)
    for node in sorted(nodes, key=lambda n: n.lineno, reverse=True):
        del lines[node.lineno - 1:node.end_lineno]
    return "".join(lines), len(nodes)

def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "WPP_CMDB_IS_Gap_Analysis_V1_2.py").expanduser().resolve()
    if not target.is_file():
        print(f"ERROR: File not found: {target}", file=sys.stderr)
        return 2
    source = target.read_text(encoding="utf-8")
    ast.parse(source)
    source, removed = remove_functions(source, {"_format_excel_workbook", "_apply_excel_formatting", "write_workbook", "_write_formatted_load"})
    marker = "# -------------------------- persistent resource manager --------------------------"
    if marker not in source:
        print("ERROR: insertion marker not found", file=sys.stderr)
        return 3
    source = source.replace(marker, BLOCK + "\n" + marker, 1)
    ast.parse(source)
    compile(source, str(target), "exec")
    backup = target.with_name(f"{target.stem}.backup_single_save_{datetime.now():%Y%m%d_%H%M%S}{target.suffix}")
    shutil.copy2(target, backup)
    target.write_text(source, encoding="utf-8")
    print(f"PATCHED: {target}")
    print(f"BACKUP : {backup}")
    print(f"REPLACED: {removed} legacy Excel writer/formatter functions")
    print("FIX: single-pass formatted Excel save")
    print("VALIDATION: AST and Python compilation passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
