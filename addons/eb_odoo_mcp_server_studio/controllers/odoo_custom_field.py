# -*- coding: utf-8 -*-
# odoo_custom_field.py — add_custom_field

import logging

_logger = logging.getLogger(__name__)

_ALLOWED_FIELD_TYPES = {
    'char', 'text', 'integer', 'float', 'monetary', 'boolean',
    'date', 'datetime', 'selection', 'many2one', 'many2many',
    'one2many', 'html', 'binary', 'json',
}

_WIDGET_MAP = {
    'text':      'text',
    'monetary':  'monetary',
    'html':      'html',
    'binary':    'binary',
    'many2many': 'many2many_tags',
    'json':      'json',
}


def _tool_add_custom_field(env, params):
    model_name   = params['model']
    field_name   = params['field_name'].strip()
    field_label  = params['field_label'].strip()
    field_type   = params['field_type'].strip().lower()

    position_field = (params.get('position_field') or '').strip()
    position       = (params.get('position') or 'after').strip()
    is_required    = bool(params.get('required', False))
    is_readonly    = bool(params.get('readonly', False))
    is_index       = bool(params.get('index', False))
    do_copy        = params.get('copy', True)
    help_text      = (params.get('help') or '').strip()
    default_value  = params.get('default_value')

    relation       = (params.get('relation') or '').strip()
    inverse_name   = (params.get('inverse_name') or '').strip()
    relation_table = (params.get('relation_table') or '').strip()
    column1        = (params.get('column1') or '').strip()
    column2        = (params.get('column2') or '').strip()

    sel_vals       = params.get('selection_values') or []
    groups_str     = (params.get('groups') or '').strip()
    inject_list    = bool(params.get('inject_list_view', True))
    target_page    = (params.get('target_page') or '').strip()

    if field_type not in _ALLOWED_FIELD_TYPES:
        raise ValueError(
            f"Unsupported field_type '{field_type}'. "
            f"Allowed: {', '.join(sorted(_ALLOWED_FIELD_TYPES))}"
        )

    if not field_name.startswith('x_'):
        field_name = 'x_' + field_name

    if position not in ('after', 'before', 'inside'):
        position = 'after'

    try:
        sudo = env.sudo()
    except AttributeError:
        sudo = env

    ir_model = sudo['ir.model'].search([('model', '=', model_name)], limit=1)
    if not ir_model:
        similar = sudo['ir.model'].search_read(
            [('model', 'like', model_name.split('.')[0])], ['model', 'name'], limit=5)
        hint = ', '.join(r['model'] for r in similar)
        raise ValueError(
            f"Model '{model_name}' not found."
            + (f" Did you mean: {hint}?" if hint else "")
        )

    existing = sudo['ir.model.fields'].search(
        [('model_id', '=', ir_model.id), ('name', '=', field_name)], limit=1)
    if existing:
        raise ValueError(
            f"Field '{field_name}' already exists on '{model_name}' "
            f"(type={existing.ttype}). Use a different name."
        )

    if field_type == 'one2many':
        if not relation:
            raise ValueError("one2many requires 'relation' (comodel name).")
        if not inverse_name:
            candidate = sudo['ir.model.fields'].search([
                ('model', '=', relation), ('ttype', '=', 'many2one'),
                ('relation', '=', model_name),
            ], limit=1)
            if candidate:
                inverse_name = candidate.name
            else:
                raise ValueError(
                    f"one2many requires 'inverse_name' "
                    f"(a Many2one field on '{relation}' pointing to '{model_name}'). "
                    f"Create that Many2one first, then add the one2many."
                )

    if field_type in ('many2one', 'many2many') and not relation:
        raise ValueError(f"'{field_type}' requires 'relation' (comodel name).")

    if field_type == 'selection' and not sel_vals:
        raise ValueError(
            "selection field requires 'selection_values': "
            "list of [key, label] pairs, e.g. [['draft','Draft'],['done','Done']]"
        )

    currency_field = None
    if field_type == 'monetary':
        cur_f = sudo['ir.model.fields'].search([
            ('model_id', '=', ir_model.id),
            ('name', 'in', ['currency_id', 'x_currency_id']),
            ('ttype', '=', 'many2one'),
            ('relation', '=', 'res.currency'),
        ], limit=1)
        if cur_f:
            currency_field = cur_f.name

    vals = {
        'model_id':          ir_model.id,
        'name':              field_name,
        'field_description': field_label,
        'ttype':             field_type,
        'required':          is_required,
        'readonly':          is_readonly,
        'index':             is_index,
        'copied':            do_copy,
        'help':              help_text,
        'store':             True,
        'state':             'manual',
    }

    if field_type == 'selection':
        if isinstance(sel_vals, dict):
            sel_vals = list(sel_vals.items())
        pairs = [(str(k), str(v)) for item in sel_vals
                 for k, v in ([item] if isinstance(item, (list, tuple)) and len(item) == 2
                               else [(item, item)])]
        vals['selection'] = str(pairs)

    if field_type in ('many2one', 'many2many', 'one2many'):
        vals['relation'] = relation

    if field_type == 'one2many':
        vals['relation_field'] = inverse_name

    if field_type == 'many2many' and relation_table:
        vals['relation_table'] = relation_table
        if column1: vals['column1'] = column1
        if column2: vals['column2'] = column2

    if field_type == 'monetary' and currency_field:
        vals['currency_field'] = currency_field

    if default_value is not None:
        vals['default'] = str(default_value)

    if groups_str:
        group_ids = []
        for xml_id in [g.strip() for g in groups_str.split(',') if g.strip()]:
            try:
                group_ids.append(sudo.ref(xml_id).id)
            except Exception:
                _logger.warning("Group XML ID not found: %s", xml_id)
        if group_ids:
            vals['groups'] = [(6, 0, group_ids)]

    new_field  = sudo['ir.model.fields'].create(vals)
    widget     = _WIDGET_MAP.get(field_type, '')
    widget_attr = f' widget="{widget}"' if widget else ''

    if position_field:
        xpath_expr    = f"//field[@name='{position_field}']"
        position_attr = position
    elif target_page:
        xpath_expr    = f"//page[@string='{target_page}']"
        position_attr = 'inside'
    else:
        xpath_expr    = "//sheet"
        position_attr = 'inside'

    field_xml = f'<field name="{field_name}"{widget_attr}/>'
    arch = (
        f'<data>'
        f'<xpath expr="{xpath_expr}" position="{position_attr}">'
        f'{field_xml}'
        f'</xpath>'
        f'</data>'
    )

    def _find_view(view_type):
        v = sudo['ir.ui.view'].search(
            [('model', '=', model_name), ('type', '=', view_type),
             ('mode', 'in', ('primary', 'base')), ('active', '=', True)],
            order='priority asc', limit=1)
        if not v:
            v = sudo['ir.ui.view'].search(
                [('model', '=', model_name), ('type', '=', view_type), ('active', '=', True)],
                order='priority asc', limit=1)
        return v

    def _inject_view(view, view_type, view_arch):
        iname = f"mcp.{model_name.replace('.', '_')}.{field_name}.{view_type}"
        ev = sudo['ir.ui.view'].search([('name', '=', iname)], limit=1)
        if ev:
            ev.write({'arch': view_arch})
            return ev.id, 'updated'
        else:
            nv = sudo['ir.ui.view'].create({
                'name':       iname,
                'model':      model_name,
                'inherit_id': view.id,
                'arch':       view_arch,
                'type':       view_type,
                'mode':       'extension',
                'active':     True,
                'priority':   99,
            })
            return nv.id, 'created'

    view_results = {}

    form_view = _find_view('form')
    if form_view:
        vid, va = _inject_view(form_view, 'form', arch)
        view_results['form'] = f"View {va} (id={vid})"
    else:
        view_results['form'] = "No form view found"

    if inject_list and field_type not in ('html', 'binary', 'one2many', 'many2many'):
        list_arch = (
            f'<data>'
            f'<xpath expr="//list | //tree" position="inside">'
            f'<field name="{field_name}"{widget_attr}/>'
            f'</xpath>'
            f'</data>'
        )
        list_view = _find_view('list') or _find_view('tree')
        if list_view:
            vid, va = _inject_view(list_view, list_view.type, list_arch)
            view_results['list'] = f"View {va} (id={vid})"
        else:
            view_results['list'] = "No list view found"

    notes = []
    if field_type == 'monetary' and not currency_field:
        notes.append(
            "⚠ No currency_id field found on this model. "
            "Add a Many2one→res.currency field named 'x_currency_id' "
            "for proper monetary display."
        )
    if field_type == 'one2many':
        notes.append(f"ℹ one2many uses inverse_name='{inverse_name}' on '{relation}'.")

    return {
        "success":    True,
        "field_name": field_name,
        "field_id":   new_field.id,
        "field_type": field_type,
        "model":      model_name,
        "views":      view_results,
        "notes":      notes,
        "message": (
            f"Field '{field_label}' ({field_type}) created on '{model_name}'. "
            f"Views: {view_results}. "
            + (" | ".join(notes) if notes else "")
            + " Refresh browser to see it."
        ),
    }