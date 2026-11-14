# -*- coding: utf-8 -*-
# odoo_search.py — search_read, get_record

import logging
from . import mcp_security_helpers as _mcp_sec
from .mcp_helpers import _extract_binary_resources

_logger = logging.getLogger(__name__)


def _tool_search_read(env, params, user=None):
    model_name = params['model']
    domain  = params.get('domain') or []
    fields  = params.get('fields') or []
    limit   = min(int(params.get('limit') or 80), 500)
    offset  = int(params.get('offset') or 0)
    order   = params.get('order') or False
    try:
        model = env[model_name]
    except KeyError:
        raise ValueError(f"Model '{model_name}' not found.")

    # ── Field-level restrictions: strip restricted fields ────────────────
    if user:
        hidden = _mcp_sec.get_restricted_field_names(env, user, model_name, 'read')
        if hidden and fields:
            fields = [f for f in fields if f not in hidden]

    kw = {'limit': limit, 'offset': offset}
    if order:
        kw['order'] = order
    records = model.search_read(domain, fields, **kw)
    count   = model.search_count(domain)

    # ── Strip restricted fields from results (catches all-fields case) ───
    if user:
        _mcp_sec.apply_field_restrictions(env, user, model_name, records, 'read')

    # ── Extract binary blobs as embedded MCP resources ─────────────────
    resources = _extract_binary_resources(model_name, records)
    result    = {"model": model_name, "total": count, "offset": offset,
                 "limit": limit, "records": records}
    if resources:
        result["resources"] = resources
    return result


def _tool_get_record(env, params, user=None):
    model_name = params['model']
    record_id  = int(params['record_id'])
    fields     = params.get('fields') or []
    try:
        model = env[model_name]
    except KeyError:
        raise ValueError(f"Model '{model_name}' not found.")

    # ── Field-level restrictions: strip restricted fields ────────────────
    if user:
        hidden = _mcp_sec.get_restricted_field_names(env, user, model_name, 'read')
        if hidden and fields:
            fields = [f for f in fields if f not in hidden]

    rec = model.browse(record_id)
    if not rec.exists():
        raise ValueError(f"Record {record_id} not found in '{model_name}'.")
    data = rec.read(fields) if fields else rec.read()

    # ── Strip restricted fields from results ───────────────────────
    if user:
        _mcp_sec.apply_field_restrictions(env, user, model_name, data, 'read')

    # ── Extract binary blobs as embedded MCP resources ─────────────────
    resources = _extract_binary_resources(model_name, data)
    result    = {"model": model_name, "record": data[0] if data else {}}
    if resources:
        result["resources"] = resources
    return result