# -*- coding: utf-8 -*-
# odoo_import_data.py — Bulk import records from CSV / Excel / JSON / TSV
#
# Strategy:
#   1. Accept file as base64 or raw text, auto-detect format.
#   2. Parse to a (headers, rows) structure.
#   3. Feed into Odoo's model.load(fields, data) which is the same engine
#      that powers the native Odoo Import wizard — handles Many2one by name,
#      external IDs, selection by label, date parsing, etc.
#   4. Return a rich report: created IDs, failed rows with per-row errors.
#
# Supported formats:
#   csv  — comma / semicolon / tab auto-detected delimiter
#   tsv  — tab-separated
#   xlsx — Excel workbook (requires openpyxl)
#   xls  — Legacy Excel (requires xlrd)
#   json — top-level list of objects  [{field: value}, ...]
#   txt  — treated as CSV

import base64
import csv
import io
import json
import logging

from . import mcp_security_helpers as _mcp_sec

_logger = logging.getLogger(__name__)


# ── Format detection ──────────────────────────────────────────────────────────

def _detect_format(file_name, file_format):
    """Return canonical format string: csv | xlsx | xls | json."""
    if file_format:
        return file_format.lower().strip('.')
    if file_name:
        ext = file_name.rsplit('.', 1)[-1].lower()
        if ext in ('xls',):
            return 'xls'
        if ext in ('xlsx', 'xlsm', 'xlam'):
            return 'xlsx'
        if ext == 'json':
            return 'json'
        if ext == 'tsv':
            return 'tsv'
    return 'csv'


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_csv(raw_text, delimiter=None):
    """
    Parse CSV/TSV text → (headers: list[str], rows: list[list[str]])
    Auto-detects delimiter if not specified.
    """
    if not raw_text:
        raise ValueError("File content is empty.")
    # Normalise line endings
    raw_text = raw_text.replace('\r\n', '\n').replace('\r', '\n')

    if delimiter is None:
        # Sniff fallback: try comma, semicolon, tab in that order
        try:
            dialect = csv.Sniffer().sniff(raw_text[:4096], delimiters=',;\t|')
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ','

    reader = csv.reader(io.StringIO(raw_text), delimiter=delimiter)
    rows   = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError("CSV file is empty or has no data rows.")
    headers = [h.strip() for h in rows[0]]
    data    = [[cell.strip() for cell in row] for row in rows[1:]]
    return headers, data


def _parse_excel(raw_bytes, sheet_index=0):
    """
    Parse .xlsx bytes → (headers, rows).
    Requires openpyxl (ships with Odoo).
    """
    try:
        import openpyxl
    except ImportError:
        raise ValueError(
            "openpyxl is not installed. Cannot parse .xlsx files. "
            "Install it or convert your file to CSV."
        )
    wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True, read_only=True)
    ws = wb.worksheets[sheet_index] if sheet_index < len(wb.worksheets) else wb.active

    rows = []
    for row in ws.iter_rows(values_only=True):
        str_row = [str(cell) if cell is not None else '' for cell in row]
        if any(cell.strip() for cell in str_row):
            rows.append(str_row)
    wb.close()

    if not rows:
        raise ValueError("Excel sheet is empty or has no data rows.")
    headers = [str(h).strip() for h in rows[0]]
    data    = [[str(cell).strip() for cell in row] for row in rows[1:]]
    return headers, data


def _parse_xls(raw_bytes, sheet_index=0):
    """
    Parse legacy .xls bytes → (headers, rows).
    Requires xlrd.
    """
    try:
        import xlrd
    except ImportError:
        raise ValueError(
            "xlrd is not installed. Cannot parse .xls files. "
            "Convert your file to .xlsx or CSV instead."
        )
    wb = xlrd.open_workbook(file_contents=raw_bytes)
    ws = wb.sheet_by_index(sheet_index)
    rows = []
    for r in range(ws.nrows):
        row = [str(ws.cell_value(r, c)).strip() for c in range(ws.ncols)]
        if any(cell for cell in row):
            rows.append(row)
    if not rows:
        raise ValueError("XLS sheet is empty.")
    headers = rows[0]
    data    = rows[1:]
    return headers, data


def _parse_json(content):
    """
    Parse JSON array of objects → (headers, rows).
    """
    try:
        obj = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
    if not isinstance(obj, list):
        raise ValueError("JSON must be a top-level array: [{field: value}, ...]")
    if not obj:
        raise ValueError("JSON array is empty.")

    # Collect all keys across all rows (some rows may have missing keys)
    headers = list(dict.fromkeys(k for record in obj for k in record.keys()))
    data    = [[str(record.get(h, '')) for h in headers] for record in obj]
    return headers, data


# ── Field mapping ─────────────────────────────────────────────────────────────

def _apply_field_mapping(headers, field_mapping):
    """
    Apply optional column→field remap dict.
    e.g. {"Name": "name", "Email Address": "email"}
    """
    if not field_mapping:
        return headers
    return [field_mapping.get(h, h) for h in headers]


def _normalise_cell(value):
    """Convert structured values into the strings expected by model.load()."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'True' if value else 'False'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _parse_records(records, columns=None):
    """
    Parse a list of dict records supplied directly by the MCP client.

    This is useful for ChatGPT file uploads: the model can read the attached
    spreadsheet itself, then pass structured rows here without relying on a
    server-side filesystem path such as /mnt/data/...
    """
    if not isinstance(records, list) or not records:
        raise ValueError("'records' must be a non-empty list of objects.")
    if not all(isinstance(rec, dict) for rec in records):
        raise ValueError("Each element in 'records' must be an object/dict.")

    if columns:
        headers = [str(col).strip() for col in columns if str(col).strip()]
    else:
        headers = []
        seen = set()
        for rec in records:
            for key in rec.keys():
                key = str(key).strip()
                if key and key not in seen:
                    seen.add(key)
                    headers.append(key)

    if not headers:
        raise ValueError("Could not derive any columns from 'records'.")

    rows = []
    for rec in records:
        rows.append([_normalise_cell(rec.get(h, '')) for h in headers])
    return headers, rows


def _parse_rows(headers, rows):
    """
    Parse explicit headers + row arrays supplied directly by the MCP client.
    """
    if not headers:
        raise ValueError("'headers' is required when using 'rows'.")
    if not isinstance(headers, list) or not all(str(h).strip() for h in headers):
        raise ValueError("'headers' must be a non-empty list of column names.")
    if not isinstance(rows, list) or not rows:
        raise ValueError("'rows' must be a non-empty list of row arrays.")

    clean_headers = [str(h).strip() for h in headers]
    width = len(clean_headers)
    clean_rows = []
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, (list, tuple)):
            raise ValueError(f"rows[{idx}] must be an array/list.")
        row_vals = list(row[:width])
        if len(row_vals) < width:
            row_vals.extend([''] * (width - len(row_vals)))
        clean_rows.append([_normalise_cell(v) for v in row_vals])
    return clean_headers, clean_rows


# ── Main tool ─────────────────────────────────────────────────────────────────

def _tool_import_data(env, params, user=None):
    """
    Import records from CSV / Excel / JSON / TSV into any Odoo model.

    Parameters (in params dict):
        model       str   — Odoo model technical name (required)
        file_content str   — raw text (CSV/JSON) OR base64-encoded binary (Excel)
        records     list  — optional list of dict rows parsed from an uploaded file
        headers     list  — optional column names when using rows
        rows        list  — optional list-of-lists row data
        columns     list  — optional explicit column order for records mode
        file_name   str   — original filename (used for format detection)
        file_format str   — override: 'csv' | 'xlsx' | 'xls' | 'json' | 'tsv'
        is_base64   bool  — True if file_content is base64 encoded (default: auto-detect)
        field_mapping dict — {"CSV Column": "odoo_field_name"} remap
        delimiter   str   — CSV delimiter override (default: auto-detect)
        sheet_index int   — Excel sheet index (default: 0)
        dry_run     bool  — Parse and validate only, don't create records
        limit       int   — Max rows to import (safety cap, default: 5000)
        skip_rows   int   — Skip N data rows from the top (default: 0)

    Returns:
        dict with ids, count, fails, messages, report
    """
    # ── Parameters ────────────────────────────────────────────────────────────
    model_name  = params['model']
    file_content = params.get('file_content') or ''
    records_input = params.get('records') or []
    headers_input = params.get('headers') or []
    rows_input    = params.get('rows') or []
    columns_input = params.get('columns') or []
    file_name   = (params.get('file_name') or '').strip()
    file_format = (params.get('file_format') or '').strip()
    is_base64   = params.get('is_base64')
    field_mapping = params.get('field_mapping') or {}
    delimiter   = params.get('delimiter') or None
    sheet_index = int(params.get('sheet_index') or 0)
    dry_run     = bool(params.get('dry_run', False))
    limit       = min(int(params.get('limit') or 5000), 50000)
    skip_rows   = max(int(params.get('skip_rows') or 0), 0)

    if not file_content and not records_input and not rows_input:
        raise ValueError(
            "Provide one of: 'file_content', 'records', or 'headers' + 'rows'."
        )

    # ── Security ──────────────────────────────────────────────────────────────
    if user:
        _mcp_sec.check_model_restriction(env, user, model_name, 'create')

    # ── Model existence check ─────────────────────────────────────────────────
    try:
        model = env[model_name]
    except KeyError:
        raise ValueError(f"Model '{model_name}' not found.")

    # ── Parse content supplied directly by the MCP client ────────────────────
    if records_input:
        fmt = 'records'
        headers, data = _parse_records(records_input, columns=columns_input)
    elif rows_input:
        fmt = 'rows'
        headers, data = _parse_rows(headers_input, rows_input)
    else:
        # Clear guidance when an AI client tries to pass its local sandbox path
        stripped = file_content.strip()
        if ('\n' not in stripped and '\r' not in stripped and
                (stripped.startswith('/mnt/data/')
                 or stripped.startswith('file://')
                 or stripped.endswith(('.csv', '.tsv', '.xlsx', '.xls', '.json')))):
            raise ValueError(
                "Received a local file path, not file data. Odoo cannot read "
                "ChatGPT sandbox paths like /mnt/data/... . Read the uploaded file "
                "inside the MCP client, then call odoo_import_data with one of: "
                "'file_content' (raw CSV/JSON text or Excel base64), "
                "'records' (list of objects), or 'headers' + 'rows'."
            )

        # ── Decode base64 if needed ───────────────────────────────────────────
        fmt = _detect_format(file_name, file_format)

        # Auto-detect base64: binary formats always need base64; text formats may
        if is_base64 is None:
            is_base64 = fmt in ('xlsx', 'xls')

        raw_bytes = None
        raw_text  = ''
        if is_base64:
            try:
                # Strip data-URI prefix if present (e.g. "data:text/csv;base64,...")
                if ',' in file_content[:80]:
                    file_content = file_content.split(',', 1)[1]
                raw_bytes = base64.b64decode(file_content)
            except Exception as e:
                raise ValueError(f"Failed to decode base64 content: {e}")
            if fmt not in ('xlsx', 'xls'):
                raw_text = raw_bytes.decode('utf-8', errors='replace')
        else:
            raw_text = file_content

        # ── Parse ─────────────────────────────────────────────────────────────
        if fmt in ('csv', 'txt'):
            headers, data = _parse_csv(raw_text, delimiter=delimiter)
        elif fmt == 'tsv':
            headers, data = _parse_csv(raw_text, delimiter='\t')
        elif fmt == 'xlsx':
            headers, data = _parse_excel(raw_bytes, sheet_index=sheet_index)
        elif fmt == 'xls':
            headers, data = _parse_xls(raw_bytes, sheet_index=sheet_index)
        elif fmt == 'json':
            headers, data = _parse_json(raw_text or raw_bytes.decode('utf-8'))
        else:
            raise ValueError(
                f"Unsupported format '{fmt}'. "
                "Supported: csv, tsv, xlsx, xls, json."
            )

    # ── Apply field mapping ────────────────────────────────────────────────────
    mapped_headers = _apply_field_mapping(headers, field_mapping)

    # ── Skip rows / limit ─────────────────────────────────────────────────────
    if skip_rows:
        data = data[skip_rows:]
    if len(data) > limit:
        data = data[:limit]
        _logger.warning("MCP import: truncated to %d rows (limit=%d)", limit, limit)

    total_rows = len(data)
    if total_rows == 0:
        return {
            "model":  model_name,
            "format": fmt,
            "total":  0,
            "ids":    [],
            "errors": 0,
            "message": "File parsed successfully but contained no data rows.",
        }

    if dry_run:
        # Return parse result without touching the database
        return {
            "model":          model_name,
            "format":         fmt,
            "dry_run":        True,
            "total_rows":     total_rows,
            "columns":        headers,
            "mapped_columns": mapped_headers,
            "preview":        data[:5],
            "message": (
                f"Dry run complete. {total_rows} rows parsed from "
                f"'{file_name or fmt}' with {len(headers)} columns. "
                f"Set dry_run=false to import."
            ),
        }

    # ── Import via Odoo's load() ──────────────────────────────────────────────
    #
    # model.load(fields, data) is Odoo's native import engine:
    #   - Resolves Many2one by name / external ID
    #   - Handles selection fields by label
    #   - Returns {ids, messages} with per-row error reporting
    #   - Runs inside a transaction (rolled back on failure if onchange=True)
    #
    try:
        result = model.load(mapped_headers, data)
    except Exception as e:
        raise ValueError(f"Import engine error: {e}")

    created_ids = result.get('ids', []) or []
    messages    = result.get('messages', [])

    # Partition messages into errors vs. warnings
    errors   = [m for m in messages if m.get('type') == 'error']
    warnings = [m for m in messages if m.get('type') not in ('error',)]

    success_count = len([i for i in created_ids if i])
    error_count   = len(errors)

    # Build human-readable error summary (top 20)
    error_lines = []
    for err in errors[:20]:
        row  = err.get('rows', {})
        rnum = row.get('to', row.get('from', '?'))
        msg  = err.get('message', '')
        fld  = err.get('field', '')
        error_lines.append(f"  Row {rnum}{(' [' + fld + ']') if fld else ''}: {msg}")

    report = {
        "model":         model_name,
        "format":        fmt,
        "file":          file_name or f'<{fmt}>',
        "total_rows":    total_rows,
        "imported":      success_count,
        "failed":        error_count,
        "ids":           created_ids,
        "errors":        error_lines,
        "warnings_count": len(warnings),
        "message": (
            f"✅ {success_count}/{total_rows} records imported into '{model_name}'."
            + (f" ❌ {error_count} row(s) failed — check 'errors' for details." if error_count else "")
        ),
    }

    if error_count and not success_count:
        # Total failure — include first error in raised exception for LLM clarity
        first_err = error_lines[0] if error_lines else "Unknown error"
        raise ValueError(
            f"Import failed for all {error_count} row(s).\n"
            f"First error: {first_err}\n"
            f"Hint: Run with dry_run=true and check 'mapped_columns' match real Odoo field names."
        )

    return report
