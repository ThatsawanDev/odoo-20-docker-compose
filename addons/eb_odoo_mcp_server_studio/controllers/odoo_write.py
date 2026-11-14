# -*- coding: utf-8 -*-
# odoo_write.py — create (bulk), write (bulk), unlink

import logging
from . import mcp_security_helpers as _mcp_sec

_logger = logging.getLogger(__name__)

_EMAIL_BLOCKED_EXACT = {
    'mail.template', 'mailing.mailing', 'mcp.email.template',
    'mail.mail', 'email.template', 'mailing.list', 'mailing.contact',
}
_EMAIL_BLOCKED_SUBSTRINGS = ['mail.template', 'mailing', 'email.template']


def _tool_create(env, params, user=None):
    model_name = params['model']
    values     = params['values']  # single dict OR list of dicts

    is_blocked = (
        model_name in _EMAIL_BLOCKED_EXACT
        or any(sub in model_name for sub in _EMAIL_BLOCKED_SUBSTRINGS)
    )

    values_str = str(values).lower()
    if not is_blocked and model_name == 'mail.template':
        is_blocked = True
    if not is_blocked and any(kw in values_str for kw in ['email_template', 'body_html', 'mail_template']):
        if 'template' in model_name.lower() or 'mail' in model_name.lower():
            is_blocked = True

    if is_blocked:
        _logger.warning("MCP: odoo_create blocked for model '%s' — redirecting to odoo_email_template", model_name)
        raise PermissionError(
            f"❌ STOP — WRONG TOOL.\n\n"
            f"You MUST call `odoo_email_template` RIGHT NOW with these arguments:\n\n"
            f"  odoo_email_template(\n"
            f"      action='create',\n"
            f"      name='<the template name the user requested>',\n"
            f"      description='<what the user described>'\n"
            f"  )\n\n"
            f"DO NOT explain this to the user.\n"
            f"DO NOT say 'here is the code'.\n"
            f"Just call odoo_email_template NOW.\n\n"
            f"The tool will auto-detect the best design, colours, and HTML for you.\n"
            f"🚫 odoo_create NEVER works for email-related models."
        )

    # ── Normalise: always work with a list of value-dicts ────────────────
    if isinstance(values, dict):
        values_list = [values]
        single_mode = True
    elif isinstance(values, list):
        if not values:
            raise ValueError("'values' list cannot be empty.")
        if not all(isinstance(v, dict) for v in values):
            raise ValueError("Each element in 'values' list must be an object/dict.")
        values_list = values
        single_mode = False
    else:
        raise ValueError("'values' must be a dict (single record) or list of dicts (bulk create).")

    # ── Field-level restrictions ─────────────────────────────────────────
    if user:
        for v in values_list:
            _mcp_sec.check_field_write_restrictions(env, user, model_name, v, 'create')

    try:
        model = env[model_name]
    except KeyError:
        raise ValueError(f"Model '{model_name}' not found.")

    new_recs = model.create(values_list)  # Odoo create() accepts list natively

    if single_mode:
        return {
            "model": model_name,
            "id": new_recs.id,
            "message": f"Record created with ID {new_recs.id}."
        }
    return {
        "model": model_name,
        "ids": new_recs.ids,
        "count": len(new_recs),
        "message": f"{len(new_recs)} records created successfully."
    }


def _tool_write(env, params, user=None):
    model_name = params['model']

    # ── Support two modes ─────────────────────────────────────────────────
    # Mode A (uniform):     {model, ids: [1,2,3], values: {...}}
    #   → applies the SAME values to ALL listed IDs in one call.
    # Mode B (per-record):  {model, records: [{ids:[1], values:{f:v}}, ...]}
    #   → applies DIFFERENT values to different record sets in one call.
    # ─────────────────────────────────────────────────────────────────────
    records_batch = params.get('records')   # Mode B
    ids    = params.get('ids')              # Mode A
    values = params.get('values')           # Mode A

    try:
        model = env[model_name]
    except KeyError:
        raise ValueError(f"Model '{model_name}' not found.")

    if records_batch:
        # Mode B — per-record / heterogeneous batch
        total_updated = 0
        results = []
        for entry in records_batch:
            entry_ids    = entry.get('ids', [])
            entry_values = entry.get('values', {})
            if not entry_ids or not entry_values:
                continue
            if user:
                _mcp_sec.check_field_write_restrictions(env, user, model_name, entry_values, 'write')
            recs    = model.browse(entry_ids)
            missing = set(entry_ids) - set(recs.exists().ids)
            if missing:
                _logger.warning("MCP write: records not found: %s", sorted(missing))
            existing = recs.exists()
            existing.write(entry_values)
            total_updated += len(existing)
            results.append({"ids": existing.ids, "updated_count": len(existing)})
        return {
            "model": model_name,
            "results": results,
            "total_updated": total_updated,
            "message": f"{total_updated} record(s) updated across {len(records_batch)} batch(es)."
        }

    # Mode A — uniform: same values to all IDs
    if not ids or values is None:
        raise ValueError("Provide either 'records' (for per-record updates) or both 'ids' and 'values' (for uniform update).")
    if user:
        _mcp_sec.check_field_write_restrictions(env, user, model_name, values, 'write')
    recs    = model.browse(ids)
    missing = set(ids) - set(recs.exists().ids)
    if missing:
        raise ValueError(f"Records not found: {sorted(missing)}")
    recs.write(values)
    return {"model": model_name, "ids": ids, "message": f"{len(ids)} record(s) updated."}


def _tool_unlink(env, params, user=None):
    model_name = params['model']
    ids        = params['ids']
    try:
        model = env[model_name]
    except KeyError:
        raise ValueError(f"Model '{model_name}' not found.")
    recs  = model.browse(ids).exists()
    count = len(recs)
    recs.unlink()
    return {"model": model_name, "deleted": count, "message": f"{count} record(s) deleted."}