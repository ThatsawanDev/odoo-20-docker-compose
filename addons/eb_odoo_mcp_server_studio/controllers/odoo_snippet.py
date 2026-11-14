# -*- coding: utf-8 -*-
# odoo_snippet.py — manage_snippet

import logging

from .mcp_helpers import _sudo_env

_logger = logging.getLogger(__name__)

_SNIPPET_FIELDS = (
    'name', 'technical_name', 'description',
    'template_xml', 'scss_code', 'js_code', 'thumbnail_svg',
)


def _tool_manage_snippet(env, params):
    action = (params.get('action') or '').strip().lower()
    SN     = _sudo_env(env, 'mcp.snippet')

    if action == 'list':
        rows = SN.search_read(
            [], ['id', 'name', 'snippet_class', 'state', 'write_date'],
            order='write_date desc',
        )
        return {"count": len(rows), "snippets": rows}

    if action == 'get':
        ident = (params.get('name') or params.get('technical_name') or '').strip()
        sn    = SN.search(['|', ('name', '=', ident), ('technical_name', '=', ident)], limit=1)
        if not sn:
            raise ValueError(f"Snippet '{ident}' not found.")
        return {
            "id":            sn.id,
            "name":          sn.name,
            "snippet_class": sn.snippet_class,
            "state":         sn.state,
            "template_xml":  sn.template_xml or '',
            "scss_code":     sn.scss_code or '',
            "install_log":   sn.install_log or '',
        }

    if action == 'delete':
        ident = (params.get('name') or params.get('technical_name') or '').strip()
        sn    = SN.search(['|', ('name', '=', ident), ('technical_name', '=', ident)], limit=1)
        if not sn:
            raise ValueError(f"Snippet '{ident}' not found.")
        label = sn.name
        if sn.state == 'installed':
            sn.action_uninstall()
        sn.unlink()
        return {"message": f"Snippet '{label}' deleted."}

    if action in ('create', 'update'):
        tech = (params.get('technical_name') or '').strip().lower()
        if not tech and params.get('name'):
            tech = params['name'].lower().replace(' ', '_').replace('-', '_')
        if not tech:
            raise ValueError("'technical_name' or 'name' is required.")

        vals = {}
        for k in _SNIPPET_FIELDS:
            v = params.get(k)
            if v is not None:
                vals[k] = v.strip() if isinstance(v, str) else v

        vals.setdefault('technical_name', tech)
        vals.setdefault('name', params.get('name') or tech)

        sn = SN.search([('technical_name', '=', tech)], limit=1)

        if action == 'create':
            if not sn:
                sn = SN.create(vals)
            else:
                sn.write(vals)
        else:
            if not sn:
                raise ValueError(f"Snippet '{tech}' not found for update.")
            sn.write(vals)

        sn.action_install()
        return {
            "id":            sn.id,
            "name":          sn.name,
            "snippet_class": sn.snippet_class,
            "state":         sn.state,
            "install_log":   sn.install_log or '',
            "message": (
                f"Snippet '{sn.name}' (class: {sn.snippet_class}) installed. "
                f"Hard-refresh browser (Ctrl+Shift+R), "
                f"then Website → Edit → Blocks panel."
            ),
        }

    if action == 'install':
        ident = (params.get('technical_name') or params.get('name') or '').strip()
        sn    = SN.search(['|', ('technical_name', '=', ident), ('name', '=', ident)], limit=1)
        if not sn:
            raise ValueError(f"Snippet '{ident}' not found.")
        sn.action_install()
        return {"name": sn.name, "state": sn.state, "install_log": sn.install_log or ''}

    if action == 'uninstall':
        ident = (params.get('technical_name') or params.get('name') or '').strip()
        sn    = SN.search(['|', ('technical_name', '=', ident), ('name', '=', ident)], limit=1)
        if not sn:
            raise ValueError(f"Snippet '{ident}' not found.")
        sn.action_uninstall()
        return {"name": sn.name, "state": sn.state}

    raise ValueError(
        f"Unknown action '{action}'. "
        "Allowed: create, update, get, list, delete, install, uninstall."
    )