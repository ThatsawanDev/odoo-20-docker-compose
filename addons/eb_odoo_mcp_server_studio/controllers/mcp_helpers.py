# -*- coding: utf-8 -*-
# mcp_helpers.py — shared utilities for all MCP tool files
import ast
import base64
import datetime
import hashlib
import hmac as _hmac_mod
import html as _html_mod
import itertools
import json
import logging
import math
import re as _re
import time as _time_mod
import traceback

from odoo import fields, http, SUPERUSER_ID
from odoo.http import request, Response
from odoo.tools.safe_eval import wrap_module

from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round, float_compare, float_is_zero
from collections import defaultdict, Counter

_logger = logging.getLogger(__name__)

try:
    import requests as _requests_mod
except ImportError:
    _requests_mod = None

try:
    import pytz as _pytz_mod
except ImportError:
    _pytz_mod = None

try:
    import dateutil as _dateutil_mod
    import dateutil.parser as _dateutil_parser
    import dateutil.tz as _dateutil_tz
except ImportError:
    _dateutil_mod = None
    _dateutil_parser = None
    _dateutil_tz = None


# ── mcp_exec ─────────────────────────────────────────────────────────────────

def mcp_exec(code, globals_dict, locals_dict):
    import inspect as _insp
    from odoo.tools import safe_eval as _se_mod

    fn = _se_mod if callable(_se_mod) else _se_mod.safe_eval
    ns = {}
    ns.update(globals_dict or {})
    ns.update(locals_dict or {})

    try:
        code_obj = compile(code, '<mcp_data_code>', 'exec')
    except SyntaxError:
        raise

    executed = False

    try:
        fn(code_obj, ns)
        executed = True
    except TypeError:
        pass

    if not executed:
        try:
            params = set(_insp.signature(fn).parameters.keys())
            if 'locals_dict' in params:
                fn(code, globals_dict or {}, locals_dict or {}, mode='exec')
                executed = True
        except TypeError:
            pass

    if not executed:
        exec(code_obj, ns)  # noqa: S102

    g_keys = set(globals_dict or {})
    for k, v in ns.items():
        if k not in g_keys or k == 'result':
            locals_dict[k] = v


# ── _build_safe_globals ───────────────────────────────────────────────────────

def _build_safe_globals(env):


    def _resolve_group_value(mapping, key):
        if key in mapping:
            return mapping[key]

        if not isinstance(key, str):
            raise KeyError(key)

        text = key.strip()
        if not text:
            raise KeyError(key)

        candidates = [text]

        if text == '__count' or text.startswith('__count:'):
            candidates.extend(['id:count', 'id_count', '__count', 'count_id'])

        if ':' in text:
            base, func = text.split(':', 1)
            candidates.extend([
                f'{base}_{func}',
                f'{func}_{base}',
                base,
            ])
        else:
            for suffix in ('sum', 'avg', 'min', 'max', 'count', 'count_distinct'):
                if text.endswith('_' + suffix):
                    base = text[:-(len(suffix) + 1)]
                    candidates.extend([
                        f'{base}:{suffix}',
                        base,
                    ])
                    break
                prefix = suffix + '_'
                if text.startswith(prefix):
                    base = text[len(prefix):]
                    candidates.extend([
                        f'{base}:{suffix}',
                        base,
                    ])
                    break
            else:
                candidates.extend([
                    f'{text}:sum',
                    f'{text}:count',
                    f'{text}:avg',
                    f'{text}:max',
                    f'{text}:min',
                    f'{text}:count_distinct',
                ])

        for candidate in candidates:
            if candidate in mapping:
                return mapping[candidate]

        raise KeyError(key)


    class _ReadGroupRow:
        def __init__(self, values, mapping):
            self._values = tuple(values)
            self._mapping = mapping
        def __iter__(self):
            return iter(self._values)
        def __len__(self):
            return len(self._values)
        def __getitem__(self, key):
            if isinstance(key, str):
                return _resolve_group_value(self._mapping, key)
            if isinstance(key, int):
                try:
                    return self._values[key]
                except IndexError:
                    return None
            return self._values[key]
        def get(self, key, default=None):
            try:
                return _resolve_group_value(self._mapping, key)
            except KeyError:
                return default
        def keys(self):
            return self._mapping.keys()
        def items(self):
            return self._mapping.items()
        def values(self):
            return self._mapping.values()
        def __repr__(self):
            return repr(self._values)


    def _inventory_alias(model_name, field_name):
        if model_name in ('product.product', 'product.template') and field_name == 'qty_on_hand':
            return 'qty_available'
        return field_name


    def _normalize_order_term(part):
        text = str(part).strip()
        if not text:
            return ''
        lower = text.lower()
        if lower.endswith(':asc') and ' ' not in text:
            return text[:-4] + ' asc'
        if lower.endswith(':desc') and ' ' not in text:
            return text[:-5] + ' desc'
        return text


    def _normalize_group_order(order):
        if not order:
            return False
        if isinstance(order, (list, tuple)):
            parts = [_normalize_order_term(part) for part in order if str(part).strip()]
            return ', '.join(parts) if parts else False
        if isinstance(order, str):
            text = order.strip()
            if not text:
                return False
            if text[0] in '[(' and text[-1] in '])':
                try:
                    parsed = ast.literal_eval(text)
                except Exception:
                    parsed = None
                if isinstance(parsed, (list, tuple)):
                    parts = [_normalize_order_term(part) for part in parsed if str(part).strip()]
                    return ', '.join(parts) if parts else False
            return ', '.join(filter(None, (_normalize_order_term(part) for part in text.split(','))))
        return _normalize_order_term(order) or False


    def _normalize_group_having(having):
        if not having:
            return ()
        if isinstance(having, str):
            text = having.strip()
            if not text:
                return ()
            if text[0] in '[(' and text[-1] in '])':
                try:
                    parsed = ast.literal_eval(text)
                except Exception:
                    parsed = None
                if isinstance(parsed, (list, tuple)):
                    return parsed
            return (having,)
        if isinstance(having, (list, tuple)):
            return having
        return (having,)


    def _normalize_order_for_specs(order, groupby, aggregates):
        if not order:
            return order
        aggregate_map = {}
        for spec in aggregates or []:
            if not isinstance(spec, str) or ':' not in spec:
                continue
            base, func = spec.split(':', 1)
            aggregate_map[base] = spec
            aggregate_map[spec] = spec
            aggregate_map[f"{base}_{func}"] = spec
        group_terms = set()
        for spec in groupby or []:
            if not isinstance(spec, str):
                continue
            group_terms.add(spec)
            group_terms.add(spec.split(':', 1)[0])
        normalized_parts = []
        for part in [part.strip() for part in str(order).split(',') if part.strip()]:
            tokens = part.split()
            term = tokens[0]
            direction = ' '.join(tokens[1:])
            normalized_term = term
            if (
                term not in group_terms
                and term not in aggregate_map
                and ':' not in term
                and term != 'id'
                and term.endswith('_count')
            ):
                normalized_term = 'id:count'
            elif term not in group_terms and term in aggregate_map:
                normalized_term = aggregate_map[term]
            elif term not in group_terms and term not in aggregate_map and ':' not in term:
                inferred = aggregate_map.get(f"{term}:sum")
                if inferred:
                    normalized_term = inferred
            if normalized_term == 'id:desc':
                normalized_term = 'id desc'
            elif normalized_term == 'id:asc':
                normalized_term = 'id asc'
            normalized_parts.append((normalized_term + (' ' + direction if direction else '')).strip())
        return ', '.join(normalized_parts) if normalized_parts else order


    def _row_value_for_mapping(val):
        if hasattr(val, 'id'):
            return (val.id, val.display_name) if val else False
        return val


    def _aggregate_aliases(col):
        if col == 'id:count':
            return ['id:count', 'id_count', '__count', 'count_id']
        if ':' in col:
            base, func = col.split(':', 1)
            return [col, base, f'{base}_{func}', f'{func}_{base}']
        return [col]


    def _wrap_read_group_rows(groupby, aggregates, rows):
        all_cols = list(groupby or []) + list(aggregates or [])
        wrapped = []
        for row in rows or []:
            mapping = {}
            for col, val in zip(all_cols, row):
                key = col.split(':')[0]
                mapped_val = _row_value_for_mapping(val)
                mapping[key] = mapped_val
                mapping[col] = mapped_val
                for alias in _aggregate_aliases(col):
                    mapping[alias] = mapped_val
            wrapped.append(_ReadGroupRow(row, mapping))
        return wrapped


    def _python_group_value(record, spec):
        field_name = _inventory_alias(record._name, spec.split(':', 1)[0])
        granularity = spec.split(':', 1)[1] if ':' in spec else None
        value = getattr(record, field_name, False)
        if hasattr(value, 'ids'):
            return value[:1] if value else value
        if granularity and value:
            if granularity == 'month':
                return value.replace(day=1)
            if granularity == 'year':
                return value.replace(month=1, day=1)
        return value


    def _python_aggregate_value(record, spec):
        if spec == 'id:count':
            return 1
        field_name, func = spec.split(':', 1)
        field_name = _inventory_alias(record._name, field_name)
        value = getattr(record, field_name, 0)
        if hasattr(value, 'ids'):
            value = len(value.ids)
        if func in ('sum', 'avg', 'max', 'min'):
            return value or 0
        if func == 'count':
            return 1 if value not in (False, None) else 0
        if func == 'count_distinct':
            return value
        return value or 0


    def _python_reduce_aggregate(spec, values):
        if spec == 'id:count':
            return len(values)
        field_name, func = spec.split(':', 1)
        if func == 'sum':
            return sum(values)
        if func == 'avg':
            return (sum(values) / len(values)) if values else 0
        if func == 'max':
            return max(values) if values else 0
        if func == 'min':
            return min(values) if values else 0
        if func == 'count':
            return sum(1 for value in values if value not in (False, None))
        if func == 'count_distinct':
            return len({value for value in values if value not in (False, None)})
        return sum(values) if values else 0


    def _python_sort_groups(groupby, aggregates, rows, order):
        if not order:
            return rows
        def _term_key(row_map, term):
            return row_map.get(term)
        for part in reversed([part.strip() for part in str(order).split(',') if part.strip()]):
            tokens = part.split()
            term = tokens[0]
            reverse = len(tokens) > 1 and tokens[1].lower() == 'desc'
            rows.sort(key=lambda row: (_term_key(row[1], term) is None, _term_key(row[1], term)), reverse=reverse)
        return rows


    def _python_inventory_read_group(model_obj, domain, groupby, aggregates, limit=None, offset=0, order=None):
        records = model_obj.search(domain or [])
        grouped = {}
        for record in records:
            group_vals = tuple(_python_group_value(record, spec) for spec in groupby)
            bucket = grouped.setdefault(group_vals, {spec: [] for spec in aggregates})
            for spec in aggregates:
                bucket[spec].append(_python_aggregate_value(record, spec))
        rows = []
        for group_vals, aggregate_map in grouped.items():
            aggregate_vals = tuple(_python_reduce_aggregate(spec, aggregate_map[spec]) for spec in aggregates)
            row_values = tuple(group_vals) + tuple(aggregate_vals)
            row_mapping = {}
            for col, val in zip(list(groupby) + list(aggregates), row_values):
                mapped_val = _row_value_for_mapping(val)
                row_mapping[col] = mapped_val
                row_mapping[col.split(':')[0]] = mapped_val
                for alias in _aggregate_aliases(col):
                    row_mapping[alias] = mapped_val
            rows.append((row_values, row_mapping))
        rows = _python_sort_groups(groupby, aggregates, rows, order)
        sliced = rows[offset or 0:]
        if limit:
            sliced = sliced[:limit]
        return [_ReadGroupRow(values, mapping) for values, mapping in sliced]


    def _compat_read_group(model_obj, domain, fields, groupby, lazy=False,
                           limit=None, offset=0, orderby=False):
        try:
            groupby = groupby or []
            fields = fields or []
            gb_fields = [g.split(':')[0] for g in groupby]
            gb_exprs = set(groupby)
            gb_field_set = set(gb_fields)
            date_granularities = {'day', 'week', 'month', 'quarter', 'year', 'hour', 'minute'}
            aggregate_specs = []
            aggregate_aliases = {}
            for field_name in fields:
                if field_name in gb_exprs or field_name in gb_field_set:
                    continue
                if field_name == '__count' or field_name.startswith('__count:'):
                    aggregate_specs.append('id:count')
                    aggregate_aliases['id:count'] = ['__count', 'id_count', 'id:count']
                    continue
                if ':' in field_name:
                    base, suffix = field_name.split(':', 1)
                    if base == '__count':
                        aggregate_specs.append('id:count')
                        aggregate_aliases['id:count'] = ['__count', 'id_count', 'id:count', field_name]
                        continue
                    if base in gb_field_set and suffix in date_granularities:
                        continue
                    aggregate_specs.append(field_name)
                    aggregate_aliases.setdefault(field_name, [field_name, base])
                    continue
                aggregate_specs.append(field_name + ':sum')
                aggregate_aliases[field_name + ':sum'] = [field_name, field_name + ':sum']
            aggregates = aggregate_specs if aggregate_specs else []
            order      = _normalize_group_order(orderby)
            rows = model_obj._read_group(
                domain=domain, groupby=groupby, aggregates=aggregates,
                limit=limit, offset=offset, order=order,
            )
            all_cols = list(groupby) + aggregates
            result = []
            for row in rows:
                d = {}
                for col, val in zip(all_cols, row):
                    key = col.split(':')[0]
                    aliases = aggregate_aliases.get(col, [])
                    if hasattr(val, 'id'):
                        d[key] = (val.id, val.display_name) if val else False
                    elif hasattr(val, 'strftime'):
                        d[key] = val
                        d[col] = val
                    else:
                        d[key] = val
                        d[col] = val
                    for alias in aliases:
                        d[alias] = d.get(col, val)
                result.append(d)
            return result
        except AttributeError:
            kw = {'lazy': lazy}
            if limit:   kw['limit']   = limit
            if offset:  kw['offset']  = offset
            if orderby: kw['orderby'] = orderby
            return model_obj.read_group(domain, fields, groupby, **kw)

    class _EnvProxy:
        def __init__(self, e):
            object.__setattr__(self, '_env', e)
        def __getitem__(self, model):
            env_obj = object.__getattribute__(self, '_env')
            try:
                return _ModelProxy(env_obj[model])
            except KeyError as exc:
                raise KeyError(
                    f"Model '{model}' is not installed or not available in this Odoo database. "
                    f"Check installed models first with odoo_list_models / odoo_get_fields, "
                    f"or guard optional modules with env.has_model('{model}')."
                ) from exc
        def __contains__(self, model):
            return self.has_model(model)
        def has_model(self, model):
            try:
                object.__getattribute__(self, '_env')[model]
                return True
            except KeyError:
                return False
        def get_model(self, model, default=None):
            try:
                return self[model]
            except KeyError:
                return default
        def __getattr__(self, name):
            return getattr(object.__getattribute__(self, '_env'), name)

    class _ModelProxy:
        def __init__(self, model):
            object.__setattr__(self, '_m', model)
        def _read_group(self, domain=None, groupby=None, aggregates=None, having=None,
                        limit=None, offset=0, order=None, **kwargs):
            model_obj = object.__getattribute__(self, '_m')
            domain = domain if domain is not None else kwargs.get('domain', [])
            groupby = groupby if groupby is not None else kwargs.get('groupby', [])
            aggregates = aggregates if aggregates is not None else kwargs.get('aggregates')
            if aggregates is None and kwargs.get('fields'):
                aggregates = kwargs.get('fields')
            aggregates = aggregates or []
            norm_groupby = [spec.replace('qty_on_hand', 'qty_available') if isinstance(spec, str) else spec for spec in groupby]
            norm_aggregates = [spec.replace('qty_on_hand', 'qty_available') if isinstance(spec, str) else spec for spec in aggregates]
            having = _normalize_group_having(having if having is not None else kwargs.get('having'))
            limit = limit if limit is not None else kwargs.get('limit')
            offset = offset if offset else kwargs.get('offset', 0)
            order = _normalize_group_order(order or kwargs.get('orderby') or kwargs.get('order'))
            order = _normalize_order_for_specs(order, norm_groupby, norm_aggregates)
            norm_order = order.replace('qty_on_hand', 'qty_available') if isinstance(order, str) else order
            try:
                rows = model_obj._read_group(
                    domain=domain,
                    groupby=norm_groupby,
                    aggregates=norm_aggregates,
                    having=having,
                    limit=limit,
                    offset=offset,
                    order=norm_order,
                )
                return _wrap_read_group_rows(norm_groupby, norm_aggregates, rows)
            except Exception as exc:
                message = str(exc)
                if (
                    model_obj._name in ('product.product', 'product.template')
                    and any(
                        token in message
                        for token in (
                            "qty_on_hand",
                            "qty_available",
                            "free_qty",
                            "virtual_available",
                            "incoming_qty",
                            "outgoing_qty",
                        )
                    )
                ):
                    return _python_inventory_read_group(
                        model_obj,
                        domain=domain,
                        groupby=norm_groupby,
                        aggregates=norm_aggregates,
                        limit=limit,
                        offset=offset,
                        order=norm_order,
                    )
                raise
        def read_group(self, domain=None, fields=None, groupby=None, lazy=False,
                       limit=None, offset=0, orderby=False, **kwargs):
            model_obj = object.__getattribute__(self, '_m')

            # Compatibility for clients that accidentally use read_group(...)
            # with Odoo 19 _read_group-style kwargs.
            if 'aggregates' in kwargs or 'order' in kwargs:
                domain = domain if domain is not None else kwargs.get('domain', [])
                groupby = groupby if groupby is not None else kwargs.get('groupby', [])
                aggregates = kwargs.get('aggregates', [])
                limit = limit if limit is not None else kwargs.get('limit')
                offset = offset if offset else kwargs.get('offset', 0)
                order = _normalize_group_order(kwargs.get('order') or kwargs.get('orderby') or orderby)
                return self._read_group(
                    domain=domain,
                    groupby=groupby,
                    aggregates=aggregates,
                    limit=limit,
                    offset=offset,
                    order=order,
                )

            domain = domain if domain is not None else kwargs.get('domain', [])
            fields = fields if fields is not None else kwargs.get('fields', [])
            groupby = groupby if groupby is not None else kwargs.get('groupby', [])
            lazy = kwargs.get('lazy', lazy)
            limit = limit if limit is not None else kwargs.get('limit')
            offset = offset if offset else kwargs.get('offset', 0)
            orderby = _normalize_group_order(kwargs.get('orderby', orderby) or kwargs.get('order', orderby))
            return _compat_read_group(
                model_obj,
                domain, fields, groupby, lazy=lazy,
                limit=limit, offset=offset, orderby=orderby)
        def __getattr__(self, name):
            return getattr(object.__getattribute__(self, '_m'), name)
        def __iter__(self):
            return iter(object.__getattribute__(self, '_m'))
        def __len__(self):
            return len(object.__getattribute__(self, '_m'))

    safe_env = _EnvProxy(env)

    def _has_model(model_name):
        return safe_env.has_model(model_name)

    # ── ref() shortcut ─────────────────────────────────────────────────────
    def _ref(xml_id):
        """Shortcut for env.ref(xml_id) — XML ID lookup."""
        return env.ref(xml_id)

    # ── Command class (One2many / Many2many ops) ───────────────────────────
    try:
        from odoo.fields import Command as _Command
    except ImportError:
        try:
            from odoo.models import Command as _Command
        except ImportError:
            _Command = None

    g = {
        # Core Odoo
        'env':             safe_env,
        'has_model':       _has_model,
        'user':            env.user,
        'uid':             env.uid,
        'ref':             _ref,
        'UserError':       UserError,
        'ValidationError': ValidationError,
        'logger':          _logger,
        # Date / Time
        'datetime':        datetime,
        'date':            datetime.date,
        'timedelta':       datetime.timedelta,
        'time':            wrap_module(_time_mod, ['time','sleep','strftime','strptime','gmtime','localtime','mktime']),
        # Math
        'math':            wrap_module(math, ['ceil','floor','sqrt','pi','log','exp','pow','fabs','inf','isnan','isfinite']),
        'float_round':     float_round,
        'float_compare':   float_compare,
        'float_is_zero':   float_is_zero,
        # Collections / Iteration
        'defaultdict':     __import__('collections').defaultdict,
        'Counter':         __import__('collections').Counter,
        'itertools':       wrap_module(itertools, ['chain','groupby','product','combinations','islice','zip_longest','accumulate']),
        # Serialisation
        'json':            wrap_module(__import__('json'), ['dumps','loads']),
        'base64':          wrap_module(base64, ['b64encode','b64decode','urlsafe_b64encode','urlsafe_b64decode']),
        # Security / Crypto
        'hashlib':         wrap_module(hashlib, ['sha256','sha512','md5','sha1','new']),
        'hmac':            wrap_module(_hmac_mod, ['new','compare_digest','digest']),
        # Text / Regex
        're':              wrap_module(_re, ['match','search','findall','sub','split','compile','IGNORECASE','MULTILINE','DOTALL']),
        'html':            wrap_module(_html_mod, ['escape','unescape']),
        # Compat read_group helper
        'read_group':      _compat_read_group,
        # Placeholders — filled below
        'relativedelta':   None,
        'dateutil':        None,
        'timezone':        None,
        'Command':         _Command,
    }

    # ── dateutil ───────────────────────────────────────────────────────────
    try:
        from dateutil.relativedelta import relativedelta
        g['relativedelta'] = relativedelta
    except ImportError:
        pass

    if _dateutil_parser and _dateutil_tz:
        try:
            g['dateutil'] = type('dateutil', (), {
                'parser': _dateutil_parser,
                'tz':     _dateutil_tz,
            })()
        except Exception:
            pass

    # ── pytz / timezone ────────────────────────────────────────────────────
    if _pytz_mod:
        g['timezone'] = _pytz_mod.timezone
        g['pytz']     = wrap_module(_pytz_mod, ['timezone','utc','all_timezones','country_timezones'])

    # ── requests (get/post/put/patch/delete) ───────────────────────────────
    if _requests_mod:
        g['requests'] = wrap_module(_requests_mod, ['get','post','put','delete','patch','head','request','Session'])

    return g


# ── _sudo_env ─────────────────────────────────────────────────────────────────

def _sudo_env(env, model_name):
    try:
        return env.sudo()[model_name]
    except AttributeError:
        return env[model_name]


# ── Binary Field Resource Extraction ───────────────────────────────
#
# Binary (image / attachment) fields can be several MB of base64 data.
# Sending that raw into LLM context wastes massive tokens and may truncate
# the response.  Instead we:
#   1. Detect any binary-looking field value (base64 string >= 256 chars)
#   2. Replace it in the record with a lightweight resource URI
#   3. Carry the actual payload in a sidecar "resources" list
#
# The resource URI format is:  mcp-resource://binary/<model>/<id>/<field>
# The embedding object follows the MCP spec:  {uri, mimeType, blob}
# ─────────────────────────────────────────────────────────────

_B64_THRESHOLD = 256  # shorter strings are unlikely to be binary blobs


def _mime_from_b64(b64_str):
    """
    Peek at the first decoded bytes to guess the MIME type.
    Falls back to application/octet-stream.
    """
    try:
        header = base64.b64decode(b64_str[:64] + '==')[:8]
        sigs   = {
            b'\x89PNG':           'image/png',
            b'\xff\xd8\xff':      'image/jpeg',
            b'GIF8':              'image/gif',
            b'RIFF':              'image/webp',
            b'%PDF':              'application/pdf',
            b'PK\x03\x04':       'application/zip',
        }
        for sig, mime in sigs.items():
            if header.startswith(sig):
                return mime
    except Exception:
        pass
    return 'application/octet-stream'


def _extract_binary_resources(model_name, records):
    """
    Scan a list of record dicts.  For every field whose value looks like a
    large base64 blob, replace it with a resource URI and collect the
    resource descriptor in the returned list.

    Parameters
    ----------
    model_name : str
        Odoo model technical name (e.g. 'res.partner').
    records : list[dict]
        Records as returned by search_read / read  (mutated in-place).

    Returns
    -------
    resources : list[dict]
        MCP-style embedded resource dicts::

            [
                {
                    "uri":      "mcp-resource://binary/res.partner/42/image_1920",
                    "mimeType": "image/png",
                    "blob":     "<base64 data>"
                },
                ...
            ]
    """
    resources = []
    for rec in records:
        rec_id = rec.get('id', 0)
        for field, val in list(rec.items()):
            if not isinstance(val, str):
                continue
            if len(val) < _B64_THRESHOLD:
                continue
            # Heuristic: real base64 has very high alphanumeric density
            alnum = sum(1 for c in val[:128] if c.isalnum() or c in ('+', '/', '='))
            if alnum / 128 < 0.85:
                continue
            # Looks like binary — extract it
            uri  = f'mcp-resource://binary/{model_name}/{rec_id}/{field}'
            mime = _mime_from_b64(val)
            resources.append({'uri': uri, 'mimeType': mime, 'blob': val})
            rec[field] = uri  # replace blob with lightweight URI
    return resources



# ── HTTP response helpers ─────────────────────────────────────────────────────

def _json_response(data, status=200, extra_headers=None):
    h = {
        'Access-Control-Allow-Origin':  '*',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Expose-Headers': 'WWW-Authenticate',
        'Cache-Control':                'no-store',
    }
    if extra_headers:
        h.update(extra_headers)
    return Response(
        json.dumps(data, default=str),
        status=status,
        content_type='application/json',
        headers=h,
    )


def _ok(req_id, result):
    return _json_response({"jsonrpc": "2.0", "id": req_id, "result": result})


def _err(req_id, code, message, data=None):
    body = {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
    if data is not None:
        body["error"]["data"] = data
    return _json_response(body)


def _error_page(title, msg):
    t = str(title).replace('<', '&lt;')
    m = str(msg).replace('<', '&lt;')
    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>' + t + '</title>'
        '<style>body{font-family:sans-serif;padding:48px;background:#0f172a;color:#f1f5f9}'
        'h1{color:#f87171}p{color:#94a3b8;margin-top:8px}</style></head>'
        '<body><h1>' + t + '</h1><p>' + m + '</p></body></html>'
    )


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _resolve_env(raw_token, expected_audience=''):
    Token = request.env['mcp.api.token'].sudo()
    rec = Token.resolve_access_token(raw_token, expected_audience=expected_audience)
    if not rec:
        return None, None, None
    return request.env(user=rec.user_id.id), rec.user_id, rec


def _get_db():
    return (
        request.httprequest.environ.get('HTTP_X_ODOO_DBNAME', '')
        or request.session.db
        or ''
    )


# ── Audit log ─────────────────────────────────────────────────────────────────

def _masked_log_data(env, user, model_name, data):
    if not data or not model_name or not user:
        return data
    try:
        from . import mcp_security_helpers as _mcp_sec
        hidden = set()
        for op_name in ('read', 'create', 'write'):
            hidden |= _mcp_sec.get_restricted_field_names(env, user, model_name, op_name)
        if not hidden:
            return data

        def _mask(val):
            if isinstance(val, dict):
                return {
                    key: ('[RESTRICTED]' if key in hidden else _mask(sub_val))
                    for key, sub_val in val.items()
                }
            if isinstance(val, list):
                return [_mask(item) for item in val]
            return val

        return _mask(data)
    except Exception:
        return data


def _summarize_for_log(data, depth=0):
    if data is None:
        return None
    if depth >= 2:
        if isinstance(data, dict):
            return {'type': 'dict', 'keys': list(data.keys())[:20], 'count': len(data)}
        if isinstance(data, list):
            return {'type': 'list', 'count': len(data)}
        if isinstance(data, str):
            return data[:200]
        return data
    if isinstance(data, dict):
        summary = {}
        for idx, (key, value) in enumerate(data.items()):
            if idx >= 20:
                summary['__truncated__'] = f"{len(data) - 20} more key(s)"
                break
            summary[key] = _summarize_for_log(value, depth + 1)
        return summary
    if isinstance(data, list):
        items = [_summarize_for_log(item, depth + 1) for item in data[:10]]
        if len(data) > 10:
            items.append({'__truncated__': f"{len(data) - 10} more item(s)"})
        return items
    if isinstance(data, str):
        return data[:500]
    return data


def _serialise_log_value(env, user, model_name, value, *, log_full_payload, mask_sensitive):
    if value is None:
        return ''
    prepared = value
    if mask_sensitive:
        prepared = _masked_log_data(env, user, model_name, prepared)
    if not log_full_payload:
        prepared = _summarize_for_log(prepared)
    if isinstance(prepared, (dict, list)):
        return json.dumps(prepared, default=str)
    return str(prepared)


def _log(env, *, tool='', model='', operation='', user=None, payload=None,
         result_summary=None, state='ok', error=None, duration_ms=0,
         ip_address=None, log_level='info', method='', request_id='',
         session_id='', tb='', response_size=0):
    """
    Write a structured log entry to mcp.log.

    All new parameters have defaults so existing callers work unchanged.
    """
    try:
        config = env['mcp.config'].sudo().get_config()
        log_full_payload = bool(config.log_full_payload)
        mask_sensitive = bool(config.mask_sensitive_in_logs)
        ip_addr = ip_address or (
            request.httprequest.environ.get('REMOTE_ADDR', '') if request else '')
        payload_str = _serialise_log_value(
            env, user, model or '', payload,
            log_full_payload=log_full_payload,
            mask_sensitive=mask_sensitive,
        )
        result_str = _serialise_log_value(
            env, user, model or '', result_summary,
            log_full_payload=log_full_payload,
            mask_sensitive=mask_sensitive,
        )
        env['mcp.log'].sudo().create({
            'tool_name':      tool or '',
            'model_name':     model or '',
            'method':         method or '',
            'operation':      operation or False,
            'user_id':        user.id if user else False,
            'payload':        payload_str[:8000],
            'result_summary': result_str[:4000],
            'state':          state,
            'log_level':      log_level,
            'error_message':  str(error)[:4000] if error else False,
            'traceback_info': str(tb)[:8000] if tb else False,
            'duration_ms':    duration_ms,
            'ip_address':     ip_addr,
            'session_id':     session_id or '',
            'request_id':     str(request_id) if request_id else '',
            'response_size':  response_size,
        })
    except Exception:
        _logger.warning("MCP audit log write failed", exc_info=True)
