# -*- coding: utf-8 -*-
# odoo_report.py — manage_report

import logging

from .mcp_helpers import _sudo_env
from . import mcp_security_helpers as _mcp_sec

_logger = logging.getLogger(__name__)

_REPORT_FIELDS = (
    'name', 'technical_name', 'description',
    'model_name', 'report_type', 'binding_model',
    'landscape', 'template_html', 'custom_css',
    'layout', 'paper_format', 'paper_width', 'paper_height',
)


def _report_read_env(env):
    return env['mcp.report']


def _report_manage_env(env):
    _mcp_sec.check_tool_allowed(env, env.user, 'odoo_manage_report')
    return _sudo_env(env, 'mcp.report')


def _tool_manage_report(env, params):
    action = (params.get('action') or '').strip().lower()
    RP     = _report_read_env(env)

    if action == 'list':
        rows = RP.search_read(
            [], ['id', 'name', 'model_name', 'report_type', 'state', 'report_url', 'write_date'],
            order='write_date desc',
        )
        return {"count": len(rows), "reports": rows}

    if action == 'get':
        ident = (params.get('name') or params.get('technical_name') or '').strip()
        rp    = RP.search(['|', ('name', '=', ident), ('technical_name', '=', ident)], limit=1)
        if not rp:
            raise ValueError(f"Report '{ident}' not found.")
        return {"id": rp.id, "name": rp.name, "model_name": rp.model_name,
                "report_key": rp.report_key, "state": rp.state,
                "report_url": rp.report_url or '', "template_html": rp.template_html or '',
                "paper_format": rp.paper_format,
                "paper_width": rp.paper_width,
                "paper_height": rp.paper_height,
                "install_log": rp.install_log or ''}

    if action == 'delete':
        RP = _report_manage_env(env)
        ident = (params.get('name') or params.get('technical_name') or '').strip()
        rp    = RP.search(['|', ('name', '=', ident), ('technical_name', '=', ident)], limit=1)
        if not rp:
            raise ValueError(f"Report '{ident}' not found.")
        label = rp.name
        if rp.state == 'installed':
            rp.action_uninstall()
        rp.unlink()
        return {"message": f"Report '{label}' deleted."}

    if action in ('create', 'update'):
        RP = _report_manage_env(env)
        tech = (params.get('technical_name') or '').strip().lower()
        if not tech and params.get('name'):
            tech = params['name'].lower().replace(' ', '_').replace('-', '_')
        if not tech:
            raise ValueError("'technical_name' or 'name' is required.")
        if action == 'create' and not params.get('model_name'):
            raise ValueError("'model_name' is required for create.")
        vals = {k: (v.strip() if isinstance(v, str) else v)
                for k in _REPORT_FIELDS if (v := params.get(k)) is not None}
        vals.setdefault('technical_name', tech)
        vals.setdefault('name', params.get('name') or tech)
        rp = RP.search([('technical_name', '=', tech)], limit=1)
        if action == 'create':
            rp = rp or RP.create(vals)
            rp.write(vals)
        else:
            if not rp:
                raise ValueError(f"Report '{tech}' not found for update.")
            rp.write(vals)
        rp.action_install()
        if rp.state != 'installed':
            raise ValueError(rp.install_log or f"Report '{rp.name}' failed to install.")
        return {"id": rp.id, "name": rp.name, "model_name": rp.model_name,
                "report_key": rp.report_key, "state": rp.state,
                "report_url": rp.report_url or '', "install_log": rp.install_log or '',
                "message": (f"Report '{rp.name}' installed for '{rp.model_name}'. "
                            f"Open any {rp.model_name} record → Print → {rp.name}. "
                            f"Preview: {rp.report_url}")}

    if action == 'install':
        RP = _report_manage_env(env)
        ident = (params.get('technical_name') or params.get('name') or '').strip()
        rp    = RP.search(['|', ('technical_name', '=', ident), ('name', '=', ident)], limit=1)
        if not rp:
            raise ValueError(f"Report '{ident}' not found.")
        rp.action_install()
        if rp.state != 'installed':
            raise ValueError(rp.install_log or f"Report '{rp.name}' failed to install.")
        return {"name": rp.name, "state": rp.state, "report_url": rp.report_url or ''}

    if action == 'uninstall':
        RP = _report_manage_env(env)
        ident = (params.get('technical_name') or params.get('name') or '').strip()
        rp    = RP.search(['|', ('technical_name', '=', ident), ('name', '=', ident)], limit=1)
        if not rp:
            raise ValueError(f"Report '{ident}' not found.")
        rp.action_uninstall()
        return {"name": rp.name, "state": rp.state}

    raise ValueError(f"Unknown action '{action}'. Allowed: create, update, get, list, delete, install, uninstall.")
