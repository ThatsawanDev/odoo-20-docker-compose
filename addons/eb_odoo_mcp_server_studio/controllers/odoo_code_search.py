# -*- coding: utf-8 -*-
# odoo_code_search.py — code_search, code_read, search_webapp_code, search_module_code

import fnmatch
import json as _json
import logging
import os
import re as _re
import shutil
import subprocess

_logger = logging.getLogger(__name__)

# ── Cached binary detection ──────────────────────────────────────────────────
_RG_BIN = None
_GREP_BIN = None


def _rg_available():
    global _RG_BIN
    if _RG_BIN is None:
        _RG_BIN = shutil.which('rg') or ''
    return _RG_BIN


def _grep_available():
    global _GREP_BIN
    if _GREP_BIN is None:
        _GREP_BIN = shutil.which('grep') or ''
    return _GREP_BIN


def _build_glob_includes(file_ext):
    """Convert comma-separated extensions into a list like ['*.py', '*.xml']."""
    exts = [e.strip().lstrip('.') for e in file_ext.split(',') if e.strip()]
    return [f'*.{e}' for e in exts] if exts else ['*.py', '*.xml']


# ── ripgrep backend ──────────────────────────────────────────────────────────
def _search_with_rg(pattern, roots, limit, file_ext, case_insensitive):
    globs = _build_glob_includes(file_ext)
    results = []
    for root in roots:
        if len(results) >= limit:
            break
        cmd = [_rg_available(), '--json', '--no-heading', '-n',
               '--max-count', str(max(limit - len(results), 1))]
        for g in globs:
            cmd += ['-g', g]
        if case_insensitive:
            cmd.append('-i')
        cmd += ['--', pattern, root]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
            for line in proc.stdout.splitlines():
                if len(results) >= limit:
                    break
                try:
                    obj = _json.loads(line)
                except (ValueError, _json.JSONDecodeError):
                    continue
                if obj.get('type') != 'match':
                    continue
                data = obj.get('data', {})
                fpath = data.get('path', {}).get('text', '')
                line_num = data.get('line_number', 0)
                line_text = (data.get('lines', {}).get('text', '') or '').strip()[:200]
                rel = fpath.replace(root, '').lstrip(os.sep) if fpath else ''
                results.append({'file': rel, 'line': line_num, 'match': line_text})
        except (subprocess.TimeoutExpired, OSError) as exc:
            _logger.warning("rg search failed for %s: %s", root, exc)
    return results


# ── GNU grep backend ─────────────────────────────────────────────────────────
def _search_with_grep(pattern, roots, limit, file_ext, case_insensitive):
    globs = _build_glob_includes(file_ext)
    results = []
    for root in roots:
        if len(results) >= limit:
            break
        cmd = [_grep_available(), '-rnIE']
        if case_insensitive:
            cmd.append('-i')
        for g in globs:
            cmd += ['--include', g]
        cmd += ['--', pattern, root]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
            for line in proc.stdout.splitlines():
                if len(results) >= limit:
                    break
                # grep output: /path/to/file:LINE_NUM:matched text
                parts = line.split(':', 2)
                if len(parts) < 3:
                    continue
                fpath, line_num_str, match_text = parts
                rel = fpath.replace(root, '').lstrip(os.sep)
                try:
                    line_num = int(line_num_str)
                except ValueError:
                    continue
                results.append({
                    'file': rel, 'line': line_num,
                    'match': match_text.strip()[:200],
                })
        except (subprocess.TimeoutExpired, OSError) as exc:
            _logger.warning("grep search failed for %s: %s", root, exc)
    return results


# ── Python fallback backend ──────────────────────────────────────────────────
def _search_with_python(pattern, roots, limit, file_ext):
    globs = _build_glob_includes(file_ext)
    _re_pat = _re.compile(pattern) if pattern else None
    results = []
    for root in roots[:10]:
        if len(results) >= limit:
            break
        try:
            for dirpath, _, filenames in os.walk(root):
                if len(results) >= limit:
                    break
                matched_files = []
                for g in globs:
                    matched_files += fnmatch.filter(filenames, g)
                for fn in matched_files:
                    fp = os.path.join(dirpath, fn)
                    if not os.path.isfile(fp):
                        continue
                    try:
                        with open(fp, 'r', errors='ignore') as f:
                            for i, line in enumerate(f, 1):
                                if _re_pat and _re_pat.search(line):
                                    results.append({
                                        'file':  fp.replace(root, '').lstrip(os.sep),
                                        'line':  i,
                                        'match': line.strip()[:200],
                                    })
                                    if len(results) >= limit:
                                        break
                    except (OSError, UnicodeDecodeError):
                        pass
        except OSError:
            pass
    return results


# ── Main tool entry point ────────────────────────────────────────────────────
def _tool_code_search(env, params):
    pattern          = params.get('pattern') or ''
    path_filter      = (params.get('path') or '').strip().lower()
    file_ext         = params.get('file_ext') or 'py,xml'
    case_insensitive = bool(params.get('case_insensitive'))
    cfg              = env['mcp.config'].sudo().get_config()
    max_limit        = cfg.code_search_limit or 5000
    limit            = min(int(params.get('limit') or cfg.code_search_limit or 5000), max_limit)

    roots = []
    try:
        roots = list(env['ir.module.module']._get_module_paths() or [])
    except Exception:
        try:
            import odoo
            roots = list(getattr(odoo.addons, '__path__', []))
        except Exception:
            pass
    roots = [os.path.normpath(p) for p in roots if p]
    if path_filter:
        roots = [r for r in roots if path_filter in r.lower()]

    # Pick the fastest available engine
    if _rg_available():
        engine = 'rg'
        results = _search_with_rg(pattern, roots, limit, file_ext, case_insensitive)
    elif _grep_available():
        engine = 'grep'
        results = _search_with_grep(pattern, roots, limit, file_ext, case_insensitive)
    else:
        engine = 'python'
        results = _search_with_python(pattern, roots, limit, file_ext)

    _logger.info("code_search engine=%s pattern=%r results=%d", engine, pattern, len(results))
    return {"count": len(results), "results": results, "engine": engine}


def _tool_code_read(env, params):
    path  = params.get('path') or ''
    start = int(params.get('start') or 1)
    end   = int(params.get('end') or 0)
    if not path or '..' in path or path.startswith('/'):
        raise ValueError("Invalid path")

    roots = []
    try:
        roots = list(env['ir.module.module']._get_module_paths() or [])
    except Exception:
        try:
            import odoo
            roots = list(getattr(odoo.addons, '__path__', []))
        except Exception:
            pass

    for root in roots:
        full      = os.path.normpath(os.path.join(root, path.lstrip('/')))
        root_norm = os.path.normpath(root)
        if os.path.isfile(full) and full.startswith(root_norm):
            with open(full, 'r', errors='ignore') as f:
                lines = f.readlines()
            lines = lines[start - 1:end] if end else lines[start - 1:]
            return {"path": path, "lines": ''.join(lines), "start": start}
    raise ValueError(f"File not found: {path}")


def _tool_search_webapp_code(env, params):
    pattern   = params.get('pattern') or ''
    webapp_id = params.get('webapp_id')
    limit     = min(int(params.get('limit') or 50), 200)
    Webapp    = env['mcp.webapp']
    domain    = [('id', '=', webapp_id)] if webapp_id else []
    webapps   = Webapp.search(domain)
    _re_pat   = _re.compile(pattern) if pattern else None
    results   = []
    for w in webapps:
        for field in ['jsx_code', 'data_code']:
            val = getattr(w, field, None) or ''
            if isinstance(val, str) and _re_pat and _re_pat.search(val):
                for i, line in enumerate(val.splitlines(), 1):
                    if _re_pat.search(line):
                        results.append({'webapp_id': w.id, 'field': field, 'line': i, 'match': line[:200]})
                        if len(results) >= limit:
                            return {"count": len(results), "results": results}
    return {"count": len(results), "results": results}


def _tool_search_module_code(env, params):
    pattern   = params.get('pattern') or ''
    module_id = params.get('module_id')
    limit     = min(int(params.get('limit') or 50), 200)
    Mod       = env['mcp.module']
    domain    = [('id', '=', module_id)] if module_id else []
    mods      = Mod.search(domain)
    _re_pat   = _re.compile(pattern) if pattern else None
    results   = []
    code_fields = ['manifest_code', 'models_code', 'views_code', 'security_code', 'report_code', 'demo_data_code']
    for m in mods:
        for field in code_fields:
            content = getattr(m, field, None) or ''
            if isinstance(content, str) and _re_pat and _re_pat.search(content):
                for i, line in enumerate(content.splitlines(), 1):
                    if _re_pat.search(line):
                        results.append({
                            'module_id': m.id, 'module': m.technical_name,
                            'field': field, 'line': i, 'match': line.strip()[:200],
                        })
                        if len(results) >= limit:
                            return {"count": len(results), "results": results}
    return {"count": len(results), "results": results}