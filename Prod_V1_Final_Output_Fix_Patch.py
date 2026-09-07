#!/usr/bin/env python3
"""Combined Prod V1 patch: writable versioned outputs + consistent Excel formatting.

Usage:
  python Prod_V1_Final_Output_Fix_Patch.py "C:\\path\\wpp_cmdb_is_gap_analysis_prod_v1_demo.py"

The patch:
- creates one timestamped backup;
- replaces next_versioned_path with a write-tested collision-safe allocator;
- replaces write_workbook with the standard formatted writer;
- formats directly written OS Bulk Load and Category Load XLSX files;
- performs AST and bytecode validation before replacing the source.
"""
from __future__ import annotations

import ast
import shutil
import sys
from datetime import datetime
from pathlib import Path

VERSION_FUNCTION = r'''def next_versioned_path(folder: str, stem: str, extension: str) -> str:
    """Return the next writable daily version without overwriting an existing file."""
    target_dir = Path(folder).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    if not target_dir.is_dir():
        raise NotADirectoryError(f"Output location is not a folder: {target_dir}")

    # Fail early with a useful message if Windows/OneDrive denies folder writes.
    probe = target_dir / f".__wpp_write_test_{datetime.now():%Y%m%d%H%M%S%f}.tmp"
    try:
        with open(probe, "x", encoding="utf-8") as handle:
            handle.write("write-test")
    except PermissionError as exc:
        raise PermissionError(
            f"The selected output folder is not writable: {target_dir}. "
            "Choose a writable folder such as Desktop or Documents, or review Windows folder protection."
        ) from exc
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass

    ext = extension.lstrip(".")
    date_label = datetime.now().strftime("%d-%b-%Y")
    for version in range(1, 10000):
        candidate = target_dir / f"{stem} - {date_label} - V{version}.{ext}"
        if candidate.exists():
            continue
        # Reserve and immediately release the name. This verifies the exact filename
        # can be created and skips a locked or protected version when necessary.
        try:
            with open(candidate, "x+b"):
                pass
            candidate.unlink()
            return str(candidate)
        except FileExistsError:
            continue
        except PermissionError:
            continue
    raise RuntimeError(f"Unable to allocate a writable output filename in: {target_dir}")

'''

FORMATTING_AND_WRITER = r'''def _format_excel_workbook(path: str) -> None:
    """Apply consistent Prod V1 formatting to every worksheet in an XLSX output."""
    workbook = load_workbook(path)
    navy = PatternFill("solid", fgColor="1F4E78")
    metadata_fill = PatternFill("solid", fgColor="D9EAF7")
    alternate_fill = PatternFill("solid", fgColor="F7F9FC")
    white_bold = Font(name="Aptos", size=10, color="FFFFFF", bold=True)
    normal_font = Font(name="Aptos", size=9, color="000000")
    metadata_font = Font(name="Aptos", size=9, color="1F1F1F", italic=True)
    thin = Side(style="thin", color="D9E2F3")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    date_headers = {
        "endoflifedate", "endofsupportdate", "endofextendedsupportdate",
        "networkendoflifedate", "networkendofsupportdate",
        "serverendoflifedate", "serverendofsupportdate", "due",
        "catalogendoflifedate", "catalogendofsupportdate"
    }

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
            recognized = sum(
                value in {"mandatory", "optional", "required", "reference", "recommended"}
                for value in values
            )
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

        for column_index in range(1, worksheet.max_column + 1):
            header = pkey(worksheet.cell(1, column_index).value)
            if header in date_headers or header.endswith("date"):
                for row_index in range(first_data_row, worksheet.max_row + 1):
                    cell = worksheet.cell(row_index, column_index)
                    if isinstance(cell.value, (datetime, date)):
                        cell.number_format = "mm/dd/yyyy"

        # Bound width calculation for performance on large enterprise reports.
        sample_end = min(worksheet.max_row, 250)
        for column_index in range(1, worksheet.max_column + 1):
            longest = len(clean(worksheet.cell(1, column_index).value))
            for row_index in range(2, sample_end + 1):
                value = worksheet.cell(row_index, column_index).value
                if value is not None:
                    longest = max(
                        longest,
                        max((len(line) for line in str(value).splitlines()), default=0),
                    )
            worksheet.column_dimensions[get_column_letter(column_index)].width = min(
                max(longest + 2, 12), 45
            )

        if worksheet.max_row >= 1 and worksheet.max_column >= 1:
            worksheet.auto_filter.ref = worksheet.dimensions
        worksheet.page_setup.orientation = "landscape"
        worksheet.page_setup.fitToWidth = 1
        worksheet.page_setup.fitToHeight = 0
        worksheet.sheet_properties.pageSetUpPr.fitToPage = True
        worksheet.print_title_rows = "1:1"

    try:
        workbook.save(path)
    except PermissionError as exc:
        raise PermissionError(
            f"The output workbook cannot be saved because it is open, locked, or protected: {path}. "
            "Close the workbook in Excel or select a different output folder."
        ) from exc
    finally:
        workbook.close()


def write_workbook(path: str, sheets: Dict[str, pd.DataFrame]):
    """Write a multi-sheet workbook and apply the standard Prod V1 presentation."""
    try:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for name, dataframe in sheets.items():
                safe_name = re.sub(r"[\\[\\]:*?/\\\\]", "-", str(name))[:31] or "Sheet1"
                data = (
                    dataframe
                    if dataframe is not None and len(dataframe)
                    else pd.DataFrame(columns=["No records"])
                )
                data.to_excel(writer, index=False, sheet_name=safe_name)
        _format_excel_workbook(path)
    except PermissionError as exc:
        raise PermissionError(
            f"The output workbook cannot be created because it is open, locked, or protected: {path}. "
            "Close the workbook in Excel or use another output folder."
        ) from exc


def _write_formatted_load(dataframe: pd.DataFrame, path: str) -> None:
    """Write and format a single-sheet OS or Category load workbook."""
    try:
        dataframe.to_excel(path, index=False)
        _format_excel_workbook(path)
    except PermissionError as exc:
        raise PermissionError(
            f"The load workbook cannot be created because it is open, locked, or protected: {path}."
        ) from exc

'''


def replace_top_level_function(source: str, name: str, replacement: str) -> str:
    tree = ast.parse(source)
    node = next(
        (item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name),
        None,
    )
    if node is None:
        raise RuntimeError(f"Required function not found: {name}")
    lines = source.splitlines(keepends=True)
    lines[node.lineno - 1 : node.end_lineno] = [replacement]
    return "".join(lines)


def insert_before_function(source: str, function_name: str, addition: str) -> str:
    tree = ast.parse(source)
    node = next(
        (item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == function_name),
        None,
    )
    if node is None:
        raise RuntimeError(f"Insertion function not found: {function_name}")
    lines = source.splitlines(keepends=True)
    lines.insert(node.lineno - 1, addition)
    return "".join(lines)


def main() -> int:
    source_path = Path(
        sys.argv[1] if len(sys.argv) > 1 else "wpp_cmdb_is_gap_analysis_prod_v1_demo.py"
    ).expanduser().resolve()
    if not source_path.is_file():
        print(f"ERROR: File not found: {source_path}", file=sys.stderr)
        return 2

    original = source_path.read_text(encoding="utf-8")
    ast.parse(original)

    patched = replace_top_level_function(original, "next_versioned_path", VERSION_FUNCTION)
    patched = replace_top_level_function(patched, "write_workbook", FORMATTING_AND_WRITER)

    # Direct Category Load output: route through the same formatted single-sheet writer.
    category_pattern = (
        'pd.DataFrame([metadata]+loadrows,columns=prefix+list(catdf.columns))'
        '.to_excel(p,index=False);paths.append(p)'
    )
    category_replacement = (
        '_write_formatted_load('
        'pd.DataFrame([metadata]+loadrows,columns=prefix+list(catdf.columns)),p);'
        'paths.append(p)'
    )
    patched = patched.replace(category_pattern, category_replacement)

    # Direct OS Bulk Load output: preserve CSV behavior and format only XLSX.
    bulk_patterns = [
        'final.to_excel(load_path,index=False) if fmt=="xlsx" else final.to_csv(load_path,index=False)',
        'final.to_excel(load_path, index=False) if fmt == "xlsx" else final.to_csv(load_path, index=False)',
    ]
    bulk_replacement = (
        '_write_formatted_load(final,load_path) '
        'if fmt=="xlsx" else final.to_csv(load_path,index=False)'
    )
    for pattern in bulk_patterns:
        patched = patched.replace(pattern, bulk_replacement)

    # If the source already has an older helper from a prior patch, do not duplicate it.
    # The replacement above installs one canonical _write_formatted_load definition.
    occurrences = patched.count("def _write_formatted_load(")
    if occurrences != 1:
        raise RuntimeError(
            f"Expected exactly one formatted-load helper after patching; found {occurrences}. "
            "Use the unpatched Prod V1 script or restore the backup before retrying."
        )

    ast.parse(patched)
    compile(patched, str(source_path), "exec")

    backup = source_path.with_name(
        f"{source_path.stem}.backup_final_output_{datetime.now():%Y%m%d_%H%M%S}{source_path.suffix}"
    )
    shutil.copy2(source_path, backup)
    source_path.write_text(patched, encoding="utf-8")

    print(f"PATCHED: {source_path}")
    print(f"BACKUP : {backup}")
    print("FIXES  : Writable version allocation + complete XLSX formatting")
    print("VALIDATION: AST and Python compilation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
