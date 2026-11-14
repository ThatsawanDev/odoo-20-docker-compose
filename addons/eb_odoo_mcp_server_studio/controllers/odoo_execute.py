# -*- coding: utf-8 -*-
# odoo_execute.py — call_method, execute_action, execute_orm

import logging
import time

from .mcp_helpers import _build_safe_globals, mcp_exec

_logger = logging.getLogger(__name__)

_EMAIL_ACTION_KEYWORDS = ['email_template', 'mail_template', 'mailing', 'newsletter', 'campaign']
_FILE_IMPORT_KEYWORDS = [
    '/mnt/data/', 'read_csv(', 'read_excel(', 'csv.reader(', 'dictreader(',
    '.csv', '.xlsx', '.xls', '.tsv', '.json',
]


def _tool_call_method(env, params):
    model_name = params['model']
    ids    = params.get('ids') or []
    method = params['method']
    args   = params.get('args') or []
    kwargs = params.get('kwargs') or {}
    if method.startswith('_'):
        raise PermissionError("Private methods cannot be called.")
    try:
        model = env[model_name]
    except KeyError:
        raise ValueError(f"Model '{model_name}' not found.")
    target = model.browse(ids) if ids else model
    if not hasattr(target, method):
        raise ValueError(f"Method '{method}' not found on '{model_name}'.")
    result = getattr(target, method)(*args, **kwargs)
    return {"model": model_name, "method": method, "ids": ids, "result": result}


def _tool_execute_action(env, params):
    action_ref = str(params['action_ref']).strip()
    model_name = params.get('model', '')
    record_ids = params.get('record_ids') or []

    ref_lower   = action_ref.lower()
    model_lower = model_name.lower()
    if (any(kw in ref_lower for kw in _EMAIL_ACTION_KEYWORDS) or
            any(kw in model_lower for kw in _EMAIL_ACTION_KEYWORDS)):
        _logger.warning(
            "MCP: odoo_execute_action blocked for '%s' model '%s' — redirecting to odoo_email_template",
            action_ref, model_name)
        raise PermissionError(
            "❌ STOP — WRONG TOOL.\n\n"
            "You MUST call `odoo_email_template` instead.\n\n"
            "  odoo_email_template(action='create', name='<template name>')\n\n"
            "This tool handles ALL email template operations.\n"
            "DO NOT use odoo_execute_action for email/template/mailing actions."
        )

    sudo = env.sudo()
    if action_ref.isdigit():
        action = sudo['ir.actions.server'].browse(int(action_ref))
        if not action.exists():
            raise ValueError(f"Action {action_ref} not found.")
    else:
        try:
            action = sudo.ref(action_ref)
        except Exception:
            raise ValueError(f"XML ID '{action_ref}' not found.")
    ctx = dict(env.context)
    if model_name and record_ids:
        ctx.update({'active_model': model_name, 'active_ids': record_ids,
                    'active_id': record_ids[0] if record_ids else False})
    result = action.with_context(**ctx).run()
    return {"action_ref": action_ref, "action_name": action.name,
            "result": result or "Action executed successfully."}


def _tool_execute_orm(env, params, user=None):
    code = params.get('code', '').strip()
    if not code:
        raise ValueError("code cannot be empty.")

    _lower_code = code.lower()
    if any(kw in _lower_code for kw in ["mail.template", "mcp.email.template"]):
        raise PermissionError(
            "❌ STOP — WRONG TOOL.\n\n"
            "You MUST call `odoo_email_template` RIGHT NOW.\n\n"
            "Example for 'create summer vacation template':\n"
            "  odoo_email_template(\n"
            "      action='create',\n"
            "      name='Summer Vacation Promotion'\n"
            "  )\n\n"
            "The tool auto-selects the matching gallery design (tropical theme), \n"
            "generates professional HTML, sets colours, and saves the record.\n\n"
            "DO NOT use odoo_execute_orm for ANY email/template/mailing operation.\n"
            "DO NOT explain to the user — just call odoo_email_template immediately."
        )

    if ('/mnt/data/' in _lower_code or
            any(kw in _lower_code for kw in _FILE_IMPORT_KEYWORDS) or
            ('open(' in _lower_code and any(ext in _lower_code for ext in ['.csv', '.xlsx', '.xls', '.tsv', '.json']))):
        raise PermissionError(
            "❌ STOP — WRONG TOOL.\n\n"
            "Do NOT use `odoo_execute_orm` to open uploaded files or read paths like `/mnt/data/...`.\n"
            "The Odoo server cannot access the MCP client's local upload sandbox.\n\n"
            "Use `odoo_import_data` instead and pass the uploaded file data directly.\n\n"
            "Valid patterns:\n"
            "  odoo_import_data(model='res.partner', file_content='name,email\\nAlice,a@a.com')\n"
            "  odoo_import_data(model='res.partner', records=[{'name':'Alice','email':'a@a.com'}])\n"
            "  odoo_import_data(model='res.partner', headers=['name','email'], rows=[['Alice','a@a.com']])\n\n"
            "If field names are uncertain, call with `dry_run=true` first.\n"
            "Do NOT ask the user to paste the CSV manually if the file is already uploaded."
        )

    cfg        = env['mcp.config'].sudo().get_config()
    limit      = cfg.code_execute_limit or 10000
    line_count = len([l for l in code.splitlines() if l.strip()])
    if line_count > limit:
        raise ValueError(
            f"Code has {line_count} lines — exceeds limit of {limit}. "
            f"Increase limit in MCP Server → Configuration → Tool Limits."
        )

    globs   = _build_safe_globals(env)
    locs    = {'result': None}
    start   = time.monotonic()
    mcp_exec(code, globs, locs)
    elapsed = round((time.monotonic() - start) * 1000)
    return {"result": locs.get('result'), "duration_ms": elapsed}
