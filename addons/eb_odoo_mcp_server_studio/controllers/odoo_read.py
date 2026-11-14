# -*- coding: utf-8 -*-
# odoo_read.py — list_models, get_model_info, get_fields

import logging
from . import mcp_security_helpers as _mcp_sec

_logger = logging.getLogger(__name__)


def _tool_list_models(env, params, user=None):
    filter_str = (params.get('filter') or '').lower()
    limit      = min(int(params.get('limit') or 200), 500)
    rows = env['ir.model'].search_read(
        [('transient', '=', False)], ['model', 'name'], order='model asc', limit=limit)
    if filter_str:
        rows = [r for r in rows if filter_str in r['model'].lower() or filter_str in r['name'].lower()]

    # ── Filter out fully-blocked models (block_read = True) ──────────────
    if user and not _mcp_sec.is_mcp_admin(user):
        blocked_models = set()
        Group = env['mcp.model.group'].sudo()
        for g in Group.search([('active', '=', True)]):
            if g.user_ids and user.id not in g.user_ids.ids:
                continue
            for line in g.line_ids:
                if line.block_read:
                    blocked_models.add(line.model_name)
        if blocked_models:
            rows = [r for r in rows if r['model'] not in blocked_models]

    return {"count": len(rows), "models": [{"model": r["model"], "label": r["name"]} for r in rows]}


def _tool_get_model_info(env, params, user=None):
    model_name = params['model']
    ir_model   = env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)
    if not ir_model:
        raise ValueError(f"Model '{model_name}' not found.")
    all_fields  = env[model_name].fields_get(attributes=['type'])

    # ── Remove restricted fields from the count/summary ──────────────────
    if user:
        hidden = _mcp_sec.get_restricted_field_names(env, user, model_name, 'read')
        if hidden:
            all_fields = {k: v for k, v in all_fields.items() if k not in hidden}

    type_counts = {}
    for f in all_fields.values():
        t = f['type']
        type_counts[t] = type_counts.get(t, 0) + 1
    return {
        "model":       model_name,
        "label":       ir_model.name,
        "description": ir_model.description or '',
        "transient":   ir_model.transient,
        "field_count": len(all_fields),
        "fields_by_type": type_counts,
    }


def _tool_get_fields(env, params, user=None):
    model_name  = params['model']
    attrs       = params.get('attributes') or ['string', 'type', 'required', 'readonly', 'help', 'selection']
    filter_type = (params.get('filter_type') or '').strip()
    filter_name = (params.get('filter_name') or '').lower()
    try:
        fi = env[model_name].fields_get(attributes=attrs)
    except KeyError:
        raise ValueError(f"Model '{model_name}' not found.")
    if filter_type:
        fi = {k: v for k, v in fi.items() if v.get('type') == filter_type}
    if filter_name:
        fi = {k: v for k, v in fi.items() if filter_name in k.lower()}

    # ── Remove restricted fields so AI never learns about them ───────────
    if user:
        hidden = _mcp_sec.get_restricted_field_names(env, user, model_name, 'read')
        if hidden:
            fi = {k: v for k, v in fi.items() if k not in hidden}

    return {"model": model_name, "field_count": len(fi), "fields": fi}