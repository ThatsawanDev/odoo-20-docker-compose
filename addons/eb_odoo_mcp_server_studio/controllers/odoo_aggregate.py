# -*- coding: utf-8 -*-
# odoo_aggregate.py — aggregate, read_group

import logging
from . import mcp_security_helpers as _mcp_sec

_logger = logging.getLogger(__name__)


def _tool_aggregate(env, params, user=None):
    model_name = params['model']
    group_by   = params['group_by']
    agg_field  = params.get('agg_field') or ''
    agg_func   = (params.get('agg_func') or 'sum').lower()
    domain     = params.get('domain') or []
    limit      = min(int(params.get('limit') or 80), 500)
    order_by   = params.get('order_by') or False
    try:
        model = env[model_name]
    except KeyError:
        raise ValueError(f"Model '{model_name}' not found.")

    # ── Field-level restrictions: block aggregation on restricted fields ──
    if user:
        check_fields = list(group_by)
        if agg_field:
            check_fields.append(agg_field)
        _mcp_sec.check_field_aggregation_restrictions(env, user, model_name, check_fields)

    try:
        aggregates = []
        if agg_field:
            aggregates.append(f'{agg_field}:{agg_func}')
        kw = {}
        if limit:    kw['limit'] = limit
        if order_by: kw['order'] = order_by

        rows = model._read_group(
            domain=domain,
            groupby=group_by,
            aggregates=aggregates,
            **kw,
        )
        all_cols = list(group_by) + aggregates
        clean = []
        for row in rows:
            d = {}
            for col, val in zip(all_cols, row):
                key = col.split(':')[0]
                if hasattr(val, 'id'):
                    d[key] = (val.id, val.display_name) if val else False
                elif hasattr(val, 'strftime'):
                    d[key] = val.strftime('%Y-%m-%d')
                else:
                    d[key] = val
            clean.append(d)
    except (AttributeError, TypeError):
        agg_fields = list(group_by) + ([agg_field] if agg_field else [])
        kw = {'lazy': False}
        if order_by: kw['orderby'] = order_by
        groups = model.read_group(domain, agg_fields, group_by, limit=limit, **kw)
        clean  = [{k: v for k, v in g.items() if not k.startswith('__')} for g in groups]

    return {"model": model_name, "group_by": group_by, "count": len(clean), "groups": clean}


def _tool_read_group(env, params, user=None):
    model_name = params['model']
    domain     = params.get('domain') or []
    groupby    = params['groupby']
    aggregates = params.get('aggregates') or []
    limit      = min(int(params.get('limit') or 80), 500)
    offset     = int(params.get('offset') or 0)
    orderby    = params.get('orderby') or None
    try:
        model = env[model_name]
    except KeyError:
        raise ValueError(f"Model '{model_name}' not found.")

    # ── Field-level restrictions: block aggregation on restricted fields ──
    if user:
        check_fields = list(groupby) + list(aggregates)
        _mcp_sec.check_field_aggregation_restrictions(env, user, model_name, check_fields)

    try:
        rows = model._read_group(
            domain=domain, groupby=groupby, aggregates=aggregates,
            limit=limit, offset=offset, order=orderby,
        )
    except TypeError:
        rows = model._read_group(
            domain=domain, groupby=groupby, aggregates=aggregates,
            limit=limit, offset=offset,
        )
    gb_keys  = [g.split(':')[0] for g in groupby]
    agg_keys = [a.split(':')[0] for a in aggregates]
    all_cols = gb_keys + agg_keys
    result   = []
    for row in rows:
        d = {}
        for col, val in zip(all_cols, row):
            if hasattr(val, 'id') and val:
                d[col] = (val.id, val.display_name)
            elif hasattr(val, 'strftime'):
                d[col] = val.strftime('%Y-%m-%d') if val else None
            else:
                d[col] = val
        result.append(d)
    return {"model": model_name, "groupby": groupby, "count": len(result), "groups": result}