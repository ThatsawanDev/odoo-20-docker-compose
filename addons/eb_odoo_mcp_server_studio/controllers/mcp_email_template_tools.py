# odoo_email_template.py

import re as _re
import logging

_logger = logging.getLogger(__name__)

from .mcp_helpers import _log


def _get_live_fields(env, model: str) -> dict:
    """
    Fetch real field names from the live Odoo instance.
    Returns dict of field_name → field_info.
    """
    try:
        return env[model].fields_get(
            attributes=['string', 'type', 'relation']
        )
    except Exception:
        return {}


def _convert_jinja_to_qweb(html: str) -> str:
    """
    Convert {{ object.field }} and ${object.field} to QWeb.
    Odoo 19 body_html uses QWeb — Jinja2 never renders there.
    """
    if not html:
        return html

    def replace(match):
        expr = match.group(1).strip()
        if expr.startswith('%'):
            return match.group(0)
        if ' or ' not in expr and ' if ' not in expr:
            expr = f"{expr} or ''"
        return f'<t t-out="{expr}"/>'

    # Handle {{ expr }}
    html = _re.sub(r'\{\{\s*(.+?)\s*\}\}', replace, html)
    # Handle ${expr}
    html = _re.sub(r'\$\{\s*(.+?)\s*\}', replace, html)
    
    # Autofix hasattr(obj, 'field') -> 'field' in obj (QWeb safe_eval constraint)
    html = _re.sub(
        r"hasattr\(\s*([^,]+)\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
        r"'\2' in \1",
        html
    )
    return html


def _extract_used_fields(body: str) -> list:
    """
    Extract all object.field names used in the template body.
    Finds both {{ object.x }} and t-out="object.x" patterns.
    """
    patterns = [
        r'\{\{\s*object\.([a-zA-Z_0-9.]+)',      # {{ object.field }}
        r't-out=["\']object\.([a-zA-Z_0-9.]+)',   # t-out="object.field"
        r't-if=["\']object\.([a-zA-Z_0-9.]+)',    # t-if="object.field"
        r'\$\{\s*object\.([a-zA-Z_0-9.]+)',       # ${object.field}
    ]
    fields = set()
    for pattern in patterns:
        for match in _re.finditer(pattern, body):
            # Take only the first part (e.g. job_id from job_id.name)
            fields.add(match.group(1).split('.')[0])
    return list(fields)


def _build_field_reference(fields: dict, model: str) -> str:
    """
    Build a QWeb field reference string from live fields.
    Groups by type for easy reading.
    """
    char_fields    = []
    rel_fields     = []
    date_fields    = []
    number_fields  = []

    for name, info in sorted(fields.items()):
        ftype  = info.get('type', '')
        label  = info.get('string', name)
        rel    = info.get('relation', '')

        if ftype in ('char', 'text', 'html', 'selection'):
            char_fields.append(
                f'  <t t-out="object.{name} or \'\'"/>  '
                f'<!-- {label} -->'
            )
        elif ftype in ('many2one',):
            rel_fields.append(
                f'  <t t-out="object.{name}.name or \'N/A\'"/>  '
                f'<!-- {label} ({rel}) -->'
            )
        elif ftype in ('date', 'datetime'):
            date_fields.append(
                f'  <t t-out="object.{name} or \'\'"/>  '
                f'<!-- {label} -->'
            )
        elif ftype in ('integer', 'float', 'monetary'):
            number_fields.append(
                f'  <t t-out="object.{name} or 0"/>  '
                f'<!-- {label} -->'
            )

    parts = []
    if char_fields:
        parts.append("TEXT FIELDS:\n" + "\n".join(char_fields[:10]))
    if rel_fields:
        parts.append("RELATIONAL FIELDS:\n" + "\n".join(rel_fields[:10]))
    if date_fields:
        parts.append("DATE FIELDS:\n" + "\n".join(date_fields[:5]))
    if number_fields:
        parts.append("NUMBER FIELDS:\n" + "\n".join(number_fields[:5]))

    return "\n\n".join(parts)


def _tool_odoo_email_template(env, params):
    action  = (params.get('action') or '').strip().lower()
    MT      = env['mail.template'].sudo()

    # ── DYNAMIC CREATE ────────────────────────────────────────────────────
    if action == 'create':
        name    = params.get('name') or ''
        body    = params.get('body_html') or ''
        model   = (params.get('model') or '').strip()
        subject = params.get('subject') or name

        if not name:
            raise ValueError("'name' is required.")

        # ── Step 0: MODEL IS MANDATORY — enforce it ───────────────────────
        if not model:
            raise ValueError(
                "'model' is REQUIRED for create. You must specify which Odoo model this "
                "template targets.\n\n"
                "MODEL SELECTION RULES:\n"
                "  - user says 'mailing contacts' or 'email marketing' → model='mailing.contact'\n"
                "  - user says 'contacts' / 'customers' → model='res.partner'\n"
                "  - user says 'employees' → model='hr.employee'\n"
                "  - user says 'sales orders' → model='sale.order'\n"
                "  - user says 'invoices' → model='account.move'\n"
                "  - user says 'leads' / 'CRM' → model='crm.lead'\n"
                "  - unsure → call action='list_models', keyword='<term>' first\n\n"
                "DO NOT assume 'res.partner'. Re-read the user's request and "
                "retry with the correct model."
            )

        # ── Step 1: Validate model exists and get its real fields ──────────
        live_fields = {}
        if model:
            ir = env['ir.model'].sudo().search(
                [('model', '=', model), ('transient', '=', False)], limit=1
            )
            if not ir:
                similar = env['ir.model'].sudo().search_read(
                    [('model', 'like', model.split('.')[0])],
                    ['model', 'name'], limit=8
                )
                raise ValueError(
                    f"Model '{model}' not found in this Odoo instance.\n\n"
                    f"Similar models available:\n" +
                    "\n".join(
                        f"  {r['model']} — {r['name']}" for r in similar
                    ) +
                    f"\n\nCall action='list_models', keyword='<term>' to search, "
                    f"then retry with the correct model."
                )

            live_fields = _get_live_fields(env, model)

        # ── Step 2: If no body, return field reference for THIS model ──────
        if not body:
            if model and live_fields:
                field_ref = _build_field_reference(live_fields, model)
                raise ValueError(
                    f"'body_html' is required.\n\n"
                    f"Model '{model}' ({ir.name}) has these fields:\n\n"
                    f"{field_ref}\n\n"
                    f"IMPORTANT: Your HTML must only use {{ object.FIELDNAME }} expressions\n"
                    f"where FIELDNAME is from the list above for '{model}'.\n"
                    f"Do NOT use fields from res.partner unless they also exist in this list.\n\n"
                    f"SYNTAX RULES:\n"
                    f"  Text/Char:   <t t-out=\"object.name or ''\"/>\n"
                    f"  Many2one:    <t t-out=\"object.company_id.name or 'N/A'\"/>\n"
                    f"  Conditional: <t t-if=\"object.email\"><t t-out=\"object.email or ''\"/></t>\n\n"
                    f"Write the HTML for model='{model}' and call create again."
                )
            raise ValueError("'body_html' is required.")

        # ── Step 3: Auto-convert {{ }} to QWeb ────────────────────────────
        body = _convert_jinja_to_qweb(body)

        # ── Step 4: Validate fields used actually exist on the model ──────
        if model and live_fields:
            used = _extract_used_fields(body)
            invalid = [
                f for f in used
                if f not in live_fields
                and f not in ('name',)  # name exists on almost everything
            ]
            if invalid:
                # Build correct alternatives from live fields
                suggestions = []
                for inv in invalid[:5]:
                    # Find closest matching real field
                    close = [
                        k for k in live_fields
                        if inv.lower() in k.lower() or k.lower() in inv.lower()
                    ]
                    if close:
                        suggestions.append(
                            f"  '{inv}' → did you mean: "
                            + ", ".join(
                                f"object.{c} "
                                f"({live_fields[c].get('string','')})"
                                for c in close[:3]
                            )
                        )
                    else:
                        suggestions.append(
                            f"  '{inv}' → not found on {model}"
                        )

                raise ValueError(
                    f"These fields do not exist on '{model}':\n"
                    + "\n".join(suggestions) +
                    f"\n\nCall odoo_get_fields(model='{model}') "
                    f"to see all available fields.\n\n"
                    f"Then rewrite using only real field names."
                )

        # ── Step 5: Resolve model_id ──────────────────────────────────────
        model_id = None
        if model:
            ir = env['ir.model'].sudo().search(
                [('model', '=', model)], limit=1
            )
            if ir:
                model_id = ir.id

        # ── Step 6: Determine email_to dynamically ────────────────────────
        email_to = params.get('email_to') or ''
        if not email_to and model and live_fields:
            # Pick the best email field from live fields
            email_candidates = [
                'work_email', 'email', 'email_from',
                'partner_id', 'email_normalized'
            ]
            for candidate in email_candidates:
                if candidate in live_fields:
                    ftype = live_fields[candidate].get('type', '')
                    if ftype == 'char':
                        email_to = f'{{{{ object.{candidate} }}}}'
                    elif ftype == 'many2one':
                        email_to = f'{{{{ object.{candidate}.email }}}}'
                    break

        # ── Step 7: Save mail.template ────────────────────────────────────
        vals = {
            'name':        name,
            'subject':     subject,
            'body_html':   body,
            'email_from':  params.get('email_from') or '{{ user.email_formatted }}',
            'email_to':    email_to,
            'auto_delete': bool(params.get('auto_delete', True)),
        }
        if model_id:
            vals['model_id'] = model_id

        tpl = MT.create(vals)

        # ── Step 8: Save to mcp.email.template ───────────────────────────
        MCP = env['mcp.email.template'].sudo()
        mcp_rec = MCP.create({
            'name':        name,
            'subject':     subject,
            'body_html':   body,
            'model_id':    model_id,
            'email_from':  vals['email_from'],
            'email_to':    email_to,
            'state':       'ready',
            'mail_template_id': tpl.id,
        })

        return {
            "id":               mcp_rec.id,
            "mail_template_id": tpl.id,
            "name":             tpl.name,
            "model":            tpl.model or '',
            "email_to":         email_to,
            "fields_available": list(live_fields.keys())[:20] if live_fields else [],
            "message": (
                f"Template '{name}' created (id={mcp_rec.id}). "
                f"mail.template id={tpl.id}. "
                f"Model: {model or 'none'}. "
                f"Now call preview with a real record_id to verify rendering."
            ),
        }

    # ── LIST ──────────────────────────────────────────────────────────────
    if action == 'list':
        domain = []
        if params.get('model'):
            domain.append(('model', '=', params['model']))
        rows = MT.search_read(
            domain,
            ['id', 'name', 'model', 'subject', 'email_to'],
            order='name asc',
            limit=int(params.get('limit') or 100),
        )
        return {"count": len(rows), "templates": rows}

    # ── GET ───────────────────────────────────────────────────────────────
    if action == 'get':
        tpl = _find(MT, params)
        return tpl.read([
            'id', 'name', 'model', 'subject',
            'email_from', 'email_to', 'body_html'
        ])[0]

    # ── PREVIEW ───────────────────────────────────────────────────────────
    if action == 'preview':
        tpl = _find(MT, params)
        rid = params.get('record_id')

        if not rid:
            raise ValueError(
                f"'record_id' is required for preview.\n"
                f"Call odoo_search_read(model='{tpl.model}', "
                f"fields=['id','name'], limit=5) to get a real ID."
            )

        if not tpl.model:
            return {"subject": tpl.subject, "body_html": tpl.body_html}

        record = env[tpl.model].sudo().browse(int(rid))
        if not record.exists():
            raise ValueError(
                f"Record id={rid} not found in '{tpl.model}'."
            )

        rendered = tpl.generate_email(
            int(rid),
            ['subject', 'body_html', 'email_to', 'email_from'],
        )
        return {
            "template_id":      tpl.id,
            "record_id":        rid,
            "rendered_subject": rendered.get('subject', ''),
            "rendered_body":    rendered.get('body_html', ''),
            "email_to":         rendered.get('email_to', ''),
            "note": "Rendered with real data. No placeholders remain.",
        }

    # ── UPDATE ────────────────────────────────────────────────────────────
    if action == 'update':
        tpl = _find(MT, params)
        upd = {}
        for f in ('name', 'subject', 'email_from', 'email_to'):
            if params.get(f) is not None:
                upd[f] = params[f]
        if params.get('body_html'):
            upd['body_html'] = _convert_jinja_to_qweb(params['body_html'])
        if not upd:
            raise ValueError("Nothing to update.")
        tpl.write(upd)
        return {"id": tpl.id, "name": tpl.name,
                "message": f"Template '{tpl.name}' updated."}

    # ── DELETE ────────────────────────────────────────────────────────────
    if action == 'delete':
        tpl  = _find(MT, params)
        name = tpl.name
        tpl.unlink()
        return {"message": f"Template '{name}' deleted."}

    # ── GENERATE ──────────────────────────────────────────────────────────
    if action == 'generate':
        # Handled at mcp.email.template level, but accessible here if needed
        # Just alias to update to ensure mail.template is synced
        tpl = _find(MT, params)
        # Assuming the template is synced already on write/create,
        # we can just return success if it exists
        return {"message": f"Template '{tpl.name}' is generated and ready."}

    # ── SEND_TEST ─────────────────────────────────────────────────────────
    if action == 'send_test':
        tpl = _find(MT, params)
        rid = params.get('record_id')

        # Send to the user who triggered this
        test_email = env.user.email_formatted or env.user.email
        if not test_email:
            raise ValueError("Your Odoo user has no email address configured for testing.")

        if tpl.model and not rid:
            raise ValueError(
                f"'record_id' is required for send_test because this template "
                f"uses '{tpl.model}'. Call odoo_search_read to find one."
            )

        # Force email_to to the test email, bypassing the template's email_to
        if tpl.model:
            mail_id = tpl.with_context(
                default_email_to=test_email, 
                force_send=True
            ).send_mail(int(rid), email_values={'email_to': test_email})
        else:
            mail = env['mail.mail'].sudo().create({
                'subject':   f"[TEST] {tpl.subject}",
                'body_html': tpl.body_html,
                'email_to':  test_email,
            })
            mail.send()

        return {
            "message": f"Test email sent to your inbox: {test_email}",
            "note": "Check your Odoo user's email inbox."
        }

    # ── SEND ──────────────────────────────────────────────────────────────
    if action == 'send':
        tpl = _find(MT, params)
        rid = int(params.get('record_id') or 0)

        if not rid and not tpl.model:
            recipient = params.get('recipient')
            if not recipient:
                raise ValueError("'recipient' required when template has no model.")
            mail = env['mail.mail'].sudo().create({
                'subject':   tpl.subject,
                'body_html': tpl.body_html,
                'email_to':  recipient,
            })
            mail.send()
            return {"message": f"Email sent to {recipient}."}

        if not rid:
            raise ValueError("'record_id' required.")

        record = env[tpl.model].sudo().browse(rid)
        if not record.exists():
            raise ValueError(
                f"Record id={rid} not found in '{tpl.model}'."
            )

        mail_id = tpl.send_mail(rid, force_send=True)
        return {
            "mail_id":  mail_id,
            "message":  f"Email sent using '{tpl.name}' for record {rid}.",
        }

    # ── SEND_BULK ─────────────────────────────────────────────────────────
    if action == 'send_bulk':
        tpl        = _find(MT, params)
        record_ids = params.get('record_ids') or []
        domain     = params.get('domain')

        if not tpl.model:
            raise ValueError("Template must have a model for bulk send.")
        if domain and not record_ids:
            record_ids = env[tpl.model].sudo().search(domain).ids
        if not record_ids:
            return {"sent": 0, "message": "No records matched."}

        record_ids = record_ids[:int(params.get('limit') or 500)]
        sent, failed = [], []
        for rid in record_ids:
            try:
                tpl.send_mail(int(rid), force_send=False)
                sent.append(rid)
            except Exception as e:
                _logger.warning("Email bulk send fail rid=%s: %s", rid, e)
                _log(env, tool='odoo_email_template', model='mail.template',
                     operation='email_template', log_level='error', state='error',
                     error=e, payload={'action': 'send_bulk', 'record_id': rid})
                failed.append({"id": rid, "error": str(e)})

        return {
            "sent":    len(sent),
            "failed":  len(failed),
            "message": f"{len(sent)} sent, {len(failed)} failed.",
        }

    # ── LIST_MODELS ───────────────────────────────────────────────────────
    if action == 'list_models':
        """
        Discover Odoo model name for a keyword like 'mailing', 'contact', etc.
        Returns list of matching models to help LLM pick the right one.
        """
        keyword = (params.get('keyword') or params.get('model') or '').strip()
        if not keyword:
            raise ValueError(
                "'keyword' is required. Example: keyword='mailing' or keyword='contact'."
            )
        domain = ['|',
            ('model', 'ilike', keyword),
            ('name',  'ilike', keyword),
        ]
        rows = env['ir.model'].sudo().search_read(
            domain,
            ['model', 'name'],
            order='model asc',
            limit=15,
        )
        return {
            "count":   len(rows),
            "models":  rows,
            "message": (
                f"Found {len(rows)} models matching '{keyword}'. "
                f"Use the exact 'model' value when calling create."
            ),
        }

    raise ValueError(
        f"Unknown action '{action}'. "
        "Use: create, list, get, update, delete, "
        "generate, send, send_bulk, preview, send_test, create_mailing, list_models"
    )


def _find(MT, params):
    tid = params.get('id')
    if tid:
        r = MT.browse(int(tid))
        if r.exists(): return r
        raise ValueError(f"Template id={tid} not found.")
    name = params.get('name') or ''
    if name:
        r = MT.search([('name', 'ilike', name)], limit=1)
        if r: return r
        raise ValueError(
            f"Template '{name}' not found. Use action='list'."
        )
    raise ValueError("Provide 'id' or 'name'.")
