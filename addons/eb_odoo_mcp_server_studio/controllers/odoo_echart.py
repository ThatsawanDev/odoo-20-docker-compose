import json
import logging
import ast
import textwrap

from .mcp_helpers import _sudo_env, _build_safe_globals, mcp_exec

_logger = logging.getLogger(__name__)

_ECHART_FIELDS = ('name', 'chart_type', 'echart_option', 'data_code', 'pre_init_js',
                  'post_init_js', 'description', 'is_public')

_ECHART_KNOWN_TYPES = {
    'bar', 'line', 'pie', 'scatter', 'heatmap', 'radar',
    'funnel', 'gauge', 'map', 'treemap', 'sunburst', 'sankey',
}

_ECHART_OPTION_KEYS = {
    'title', 'legend', 'tooltip', 'toolbox', 'grid', 'xAxis', 'yAxis',
    'radar', 'geo', 'visualMap', 'dataset', 'series', 'graphic',
}

_ECHART_DATA_CODE_BLOCKLIST_PATTERNS = (
    '/mnt/data/',
    'pd.read_csv(',
    'pd.read_excel(',
)

_ECHART_DATA_CODE_BLOCKED_IMPORTS = {'requests', 'pandas', 'os', 'subprocess', 'shutil'}
_ECHART_DATA_CODE_BLOCKED_CALLS = {'open', 'exec', 'eval', '__import__'}


def _looks_like_js_option_object(echart_option_str: str) -> bool:
    """Check if the option string looks like a JS object (with functions/arrows)
    rather than valid JSON. Uses a simple scanner to skip quoted strings."""
    text = (echart_option_str or '').strip()
    if not text:
        return False
    if not ((text.startswith('{') and text.endswith('}')) or (text.startswith('(') and text.endswith(')'))):
        return False

    # Scan through the text, skipping quoted strings, to find JS signals
    js_signals = ('=>', 'function(', 'function (')
    i = 0
    unquoted_parts = []
    while i < len(text):
        ch = text[i]
        if ch in ('"', "'", '`'):
            # Skip quoted string
            quote = ch
            i += 1
            while i < len(text) and text[i] != quote:
                if text[i] == '\\' and i + 1 < len(text):
                    i += 1  # skip escaped char
                i += 1
            i += 1  # skip closing quote
        else:
            unquoted_parts.append(ch)
            i += 1

    unquoted_text = ''.join(unquoted_parts).lower()
    return any(signal in unquoted_text for signal in js_signals)


def _validate_echart_option(echart_option_str):
    if not echart_option_str or not echart_option_str.strip():
        return False, "echart_option cannot be empty."
    try:
        opt = json.loads(echart_option_str)
    except json.JSONDecodeError as e:
        if _looks_like_js_option_object(echart_option_str):
            return True, ""
        return False, f"echart_option is not valid JSON: {e}"
    if not isinstance(opt, dict):
        return False, "echart_option must be a JSON object {}, not an array."
    if 'series' in opt and not isinstance(opt['series'], list):
        return False, "echart_option.series must be an array []."

    # Validate data arrays are empty in skeleton
    series = opt.get('series', [])
    for s in series:
        if isinstance(s, dict):
            data = s.get('data', [])
            if isinstance(data, list) and len(data) > 0:
                # Allow gauge default value
                if s.get('type') == 'gauge':
                    continue
                return False, (
                    f"series[].data must be empty [] in echart_option skeleton. "
                    f"Found: {data[:2]}... "
                    f"Real data comes from data_code via result dict."
                )
    return True, ""


def _detect_chart_type(echart_option_str: str, fallback: str = 'bar') -> str:
    if not echart_option_str or not echart_option_str.strip():
        return fallback
    try:
        option = json.loads(echart_option_str)
    except Exception:
        return fallback
    if not isinstance(option, dict):
        return fallback
    layout_component_counts = []
    for key in ('grid', 'xAxis', 'yAxis', 'title', 'legend', 'visualMap', 'geo', 'radar'):
        value = option.get(key)
        if isinstance(value, list):
            layout_component_counts.append(len(value))
    geo = option.get('geo')
    if isinstance(geo, dict) and geo.get('map'):
        return 'map'
    if isinstance(geo, list) and any(isinstance(item, dict) and item.get('map') for item in geo):
        return 'map'
    series_types = []
    for series in option.get('series', []):
        if not isinstance(series, dict):
            continue
        series_type = (series.get('type') or '').strip().lower()
        if series_type == 'map':
            return 'map'
        if series_type in _ECHART_KNOWN_TYPES:
            series_types.append(series_type)
    unique_types = {series_type for series_type in series_types if series_type}
    if len(unique_types) > 1:
        return 'custom'
    if unique_types:
        max_layout_count = max(layout_component_counts or [1])
        if max_layout_count > 1 and len(series_types) > 1:
            return 'custom'
        return next(iter(unique_types))
    return fallback


def _validate_data_code(data_code: str, echart_option_str: str = '') -> tuple:
    """
    Validate data_code before saving.
    Uses AST-level analysis to catch blocked imports/calls without
    false-positiving on comments or string literals.
    """
    if not data_code or not data_code.strip():
        return True, ""  # No data_code is fine — static chart

    errors = []
    lower_code = data_code.lower()

    # Simple substring checks for sandbox path patterns
    for needle in _ECHART_DATA_CODE_BLOCKLIST_PATTERNS:
        if needle.lower() in lower_code:
            errors.append(
                f"Do not use '{needle}' in chart data_code. "
                f"Chart data should come from Odoo ORM queries."
            )

    # Check result is set
    if 'result' not in data_code:
        errors.append(
            "data_code must set 'result = {...}' at the end. "
            "result dict is deep-merged into echart_option."
        )

    if 'result = [' in data_code or 'result=[' in data_code:
        errors.append(
            "result must be a dict {}, not a list []. Example: "
            "{'xAxis': {'data': labels}, 'series': [{'data': values}]}"
        )

    # AST-level validation: parse and inspect the tree
    try:
        tree = ast.parse(data_code)
    except SyntaxError as e:
        errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
        if errors:
            return False, "\n".join(f"  • {e}" for e in errors)
        return True, ""

    # Walk the AST to find blocked imports and function calls
    for node in ast.walk(tree):
        # Check import statements
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_root = (alias.name or '').split('.')[0]
                if module_root in _ECHART_DATA_CODE_BLOCKED_IMPORTS:
                    errors.append(
                        f"Do not import '{alias.name}' in chart data_code. "
                        f"Chart data should come from Odoo ORM."
                    )
        elif isinstance(node, ast.ImportFrom):
            module_root = (node.module or '').split('.')[0]
            if module_root in _ECHART_DATA_CODE_BLOCKED_IMPORTS:
                errors.append(
                    f"Do not import from '{node.module}' in chart data_code. "
                    f"Chart data should come from Odoo ORM."
                )
        # Check blocked function calls (open, exec, eval)
        elif isinstance(node, ast.Call):
            func_name = ''
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            if func_name in _ECHART_DATA_CODE_BLOCKED_CALLS:
                errors.append(
                    f"Do not use '{func_name}()' in chart data_code. "
                    f"Query Odoo models instead."
                )

    # Check for common wrong patterns
    if 'for row in rows:' in data_code and 'row[' in data_code:
        # Old dict access pattern — _read_group returns tuples not dicts
        if "row.get(" in data_code or "row['" in data_code or 'row["' in data_code:
            errors.append(
                "_read_group() returns TUPLES not dicts. "
                "Use: for (groupby_val, agg_val) in rows — not row['field']."
            )

    if echart_option_str:
        try:
            option = json.loads(echart_option_str)
        except Exception:
            option = {}
        if isinstance(option, dict):
            for axis_name in ('xAxis', 'yAxis'):
                axis_value = option.get(axis_name)
                if isinstance(axis_value, dict):
                    if f"'{axis_name}': [" in data_code or f'"{axis_name}": [' in data_code:
                        errors.append(
                            f"{axis_name} in echart_option is an object, so result must use "
                            f"{axis_name}: {{'data': ...}}, not {axis_name}: [...]."
                        )
                elif isinstance(axis_value, list):
                    if f"'{axis_name}': {{" in data_code or f'"{axis_name}": {{' in data_code:
                        errors.append(
                            f"{axis_name} in echart_option is an array, so result must use "
                            f"{axis_name}: [{{...}}], not {axis_name}: {{...}}."
                        )

    if errors:
        return False, "\n".join(f"  • {e}" for e in errors)
    return True, ""


def _prepare_echart_data_code(data_code: str) -> str:
    """
    Auto-wrap chart data_code with a safe error guard when the client omits
    try/except. This keeps save-time validation customer-friendly while still
    returning {'__error': ...} at runtime.
    """
    if not data_code or not data_code.strip():
        return data_code
    try:
        tree = ast.parse(data_code)
    except SyntaxError:
        return data_code
    if any(isinstance(node, ast.Try) for node in ast.walk(tree)):
        return data_code
    wrapped = textwrap.indent(data_code.strip(), '    ')
    return (
        "try:\n"
        f"{wrapped}\n"
        "except Exception as e:\n"
        "    result = {'__error': str(e)}\n"
    )


def _normalize_echart_result(result: dict) -> dict:
    """
    Backward-compatible result normalization for dashboards.
    - Accept {'error': '...'} as an older alias for {'__error': '...'}
    - If the result is a plain custom payload and does not contain real
      ECharts option keys, expose it as __js_data__ automatically so
      post_init_js dashboards keep working.
    - Also recognize flat path keys like 'xAxis[0].data', 'series[1].name'
      as legitimate ECharts option updates (the JS side will unflatten them).
    """
    if not isinstance(result, dict):
        return result

    normalized = dict(result)
    if '__error' not in normalized and isinstance(normalized.get('error'), str):
        normalized['__error'] = normalized['error']

    if '__js_data__' not in normalized:
        public_payload = {
            key: value
            for key, value in normalized.items()
            if not str(key).startswith('__') and key != 'error'
        }
        # Check for direct match OR flat path key (e.g. 'xAxis[0].data' → root 'xAxis')
        def _is_echart_key(key: str) -> bool:
            root = str(key).split('[')[0].split('.')[0]
            return root in _ECHART_OPTION_KEYS

        has_option_keys = any(_is_echart_key(key) for key in public_payload)
        if public_payload and not has_option_keys:
            normalized['__js_data__'] = public_payload

    return normalized


def _truncate_preview(value, *, depth=0, max_depth=4, max_items=20):
    if depth >= max_depth:
        return '...[truncated]'
    if isinstance(value, dict):
        items = list(value.items())
        trimmed = {
            key: _truncate_preview(val, depth=depth + 1, max_depth=max_depth, max_items=max_items)
            for key, val in items[:max_items]
        }
        if len(items) > max_items:
            trimmed['__truncated__'] = f"{len(items) - max_items} more key(s)"
        return trimmed
    if isinstance(value, list):
        trimmed = [
            _truncate_preview(item, depth=depth + 1, max_depth=max_depth, max_items=max_items)
            for item in value[:max_items]
        ]
        if len(value) > max_items:
            trimmed.append(f"...[{len(value) - max_items} more item(s)]")
        return trimmed
    if isinstance(value, tuple):
        return _truncate_preview(list(value), depth=depth, max_depth=max_depth, max_items=max_items)
    return value


def _preview_chart_data(env, chart):
    if not chart.data_code or not chart.data_code.strip():
        return {"has_data_code": False}

    globs = _build_safe_globals(env)
    locs = {'result': {}}
    try:
        mcp_exec(_prepare_echart_data_code(chart.data_code), globs, locs)
        result = _normalize_echart_result(locs.get('result') or {})
        if not isinstance(result, dict):
            return {
                "ok": False,
                "error": f"data_code set result to {type(result).__name__}, expected dict."
            }
        if '__error' in result:
            return {"ok": False, "error": result['__error']}
        json.dumps(result, default=str)
        return {"ok": True, "result": _truncate_preview(result)}
    except SyntaxError as exc:
        return {"ok": False, "error": f"Syntax error at line {exc.lineno}: {exc.msg}"}
    except Exception as exc:
        return {"ok": False, "error": _format_echart_runtime_error(str(exc))}


def _format_echart_runtime_error(message: str) -> str:
    if "Invalid field 'amount_total' on model 'product.template'" in message:
        return (
            f"{message}\n"
            "Use sale.order.line with aggregate 'price_subtotal:sum' grouped by 'product_template_id' "
            "instead of product.template.amount_total."
        )
    if "Invalid field 'amount_total' on model 'product.product'" in message:
        return (
            f"{message}\n"
            "Use sale.order.line with aggregate 'price_subtotal:sum' grouped by 'product_id' "
            "instead of product.product.amount_total."
        )
    return message


def _validate_live_data_code(env, data_code: str) -> tuple[bool, str]:
    if not data_code or not data_code.strip():
        return True, ""
    globs = _build_safe_globals(env)
    locs = {'result': {}}
    try:
        mcp_exec(_prepare_echart_data_code(data_code), globs, locs)
        result = _normalize_echart_result(locs.get('result') or {})
        if not isinstance(result, dict):
            return False, f"data_code set result to {type(result).__name__}, expected dict."
        if '__error' in result:
            return False, str(result['__error'])
        json.dumps(result, default=str)
        return True, ""
    except SyntaxError as exc:
        return False, f"Syntax error at line {exc.lineno}: {exc.msg}"
    except Exception as exc:
        return False, _format_echart_runtime_error(str(exc))


def _append_chart_data_preview(env, payload, chart):
    cfg = env['mcp.config'].sudo().get_config()
    if not cfg.expose_echart_data_in_response:
        return payload
    payload['data_preview'] = _preview_chart_data(env, chart)
    return payload


def _tool_manage_echart(env, params):
    action = (params.get('action') or '').strip().lower()
    EC     = _sudo_env(env, 'mcp.echart')

    if action == 'list':
        rows = EC.search_read([], ['id', 'name', 'slug', 'chart_type', 'description',
                                   'chart_url', 'share_url', 'write_date'])
        return {"count": len(rows), "charts": rows}

    if action == 'get':
        slug  = params.get('slug') or ''
        chart = EC.search([('slug', '=', slug)], limit=1)
        if not chart:
            raise ValueError(f"Chart '{slug}' not found.")
        return _append_chart_data_preview(env, {
            "id":            chart.id,
            "name":          chart.name,
            "slug":          chart.slug,
            "chart_type":    chart.chart_type,
            "echart_option": chart.echart_option or '',
            "data_code":     chart.data_code or '',
            "pre_init_js":   chart.pre_init_js or '',
            "post_init_js":  chart.post_init_js or '',
            "chart_url":     chart.chart_url,
            "share_url":     chart.share_url or '',
        }, chart)

    if action == 'delete':
        slug  = params.get('slug') or ''
        chart = EC.search([('slug', '=', slug)], limit=1)
        if not chart:
            raise ValueError(f"Chart '{slug}' not found.")
        name = chart.name
        chart.unlink()
        return {"message": f"Chart '{name}' deleted."}

    if action == 'create':
        name = params.get('name') or ''
        if not name:
            raise ValueError("'name' is required.")

        # Validate echart_option
        if params.get('echart_option'):
            ok, err = _validate_echart_option(params['echart_option'])
            if not ok:
                raise ValueError(
                    f"Invalid echart_option:\n  {err}\n\n"
                    f"CORRECT skeleton example:\n"
                    f'{{"backgroundColor":"#0f172a",'
                    f'"xAxis":{{"type":"category","data":[]}},'
                    f'"yAxis":{{"type":"value"}},'
                    f'"series":[{{"type":"bar","data":[]}}]}}'
                )

        # Validate data_code
        if params.get('data_code'):
            ok, err = _validate_data_code(params['data_code'], params.get('echart_option', ''))
            if not ok:
                raise ValueError(
                    f"Invalid data_code:\n{err}\n\n"
                    f"CORRECT pattern:\n"
                    f"try:\n"
                    f"    rows = env['sale.order']._read_group(\n"
                    f"        domain=[('state','in',['sale','done'])],\n"
                    f"        groupby=['date_order:month'],\n"
                    f"        aggregates=['amount_total:sum'],\n"
                    f"        order='date_order:month asc',\n"
                    f"        limit=12,\n"
                    f"    )\n"
                    f"    labels = [r[0].strftime('%b %Y') if r[0] else '?' for r in rows]\n"
                    f"    values = [round(r[1] or 0, 2) for r in rows]\n"
                    f"    result = {{'xAxis': {{'data': labels}}, 'series': [{{'data': values}}]}}\n"
                    f"except Exception as e:\n"
                    f"    result = {{'__error': str(e)}}\n\n"
                    f"For custom browser-only payload, you may also include:\n"
                    f"    result['__js_data__'] = {{...}}\n"
                    f"Then read it in post_init_js via window.mcpJsData or chart.__mcp_js_data__."
                )
            ok, err = _validate_live_data_code(env, params['data_code'])
            if not ok:
                raise ValueError(
                    f"Invalid live data_code execution:\n  {err}\n\n"
                    f"Use odoo_get_fields(model='...') before building grouped analytics, "
                    f"and make sure every model/field in data_code exists in this Odoo database."
                )

        vals = {k: params[k] for k in _ECHART_FIELDS
                if k in params and params[k] is not None}
        vals.setdefault('name', name)
        vals.setdefault('is_public', True)
        vals.setdefault(
            'chart_type',
            _detect_chart_type(params.get('echart_option', ''), fallback=params.get('chart_type') or 'bar'),
        )
        if params.get('slug'):
            vals['slug'] = params['slug']

        chart = EC.create(vals)
        return _append_chart_data_preview(env, {
            "id":        chart.id,
            "name":      chart.name,
            "slug":      chart.slug,
            "chart_type": chart.chart_type,
            "chart_url": chart.chart_url,
            "share_url": chart.share_url or '',
            "message":   f"Chart created. View at: {chart.chart_url}",
        }, chart)

    if action == 'update':
        slug  = params.get('slug') or ''
        chart = EC.search([('slug', '=', slug)], limit=1)
        if not chart:
            raise ValueError(f"Chart '{slug}' not found.")

        upd = {k: params[k] for k in _ECHART_FIELDS
               if k in params and params[k] is not None}

        if 'chart_type' not in upd:
            upd['chart_type'] = _detect_chart_type(
                upd.get('echart_option') or chart.echart_option or '',
                fallback=chart.chart_type or 'bar',
            )

        if upd.get('echart_option'):
            ok, err = _validate_echart_option(upd['echart_option'])
            if not ok:
                raise ValueError(f"Invalid echart_option: {err}")

        if upd.get('data_code'):
            ok, err = _validate_data_code(
                upd['data_code'],
                upd.get('echart_option') or chart.echart_option or '',
            )
            if not ok:
                raise ValueError(f"Invalid data_code:\n{err}")
            ok, err = _validate_live_data_code(env, upd['data_code'])
            if not ok:
                raise ValueError(
                    f"Invalid live data_code execution:\n  {err}\n\n"
                    f"Use odoo_get_fields(model='...') before building grouped analytics, "
                    f"and make sure every model/field in data_code exists in this Odoo database."
                )

        chart.write(upd)
        return _append_chart_data_preview(env, {
            "id":        chart.id,
            "slug":      chart.slug,
            "chart_type": chart.chart_type,
            "chart_url": chart.chart_url,
            "share_url": chart.share_url or '',
            "message":   f"Chart '{chart.name}' updated.",
        }, chart)

    raise ValueError(
        f"Unknown action '{action}'. Use: create, update, get, list, delete."
    )
