# -*- coding: utf-8 -*-
# odoo_webapp.py — manage_webapp

import logging

from .mcp_helpers import _sudo_env

_logger = logging.getLogger(__name__)


def _tool_manage_webapp(env, params):
    action = (params.get('action') or '').strip().lower()
    WA = _sudo_env(env, 'mcp.webapp')

    if action == 'list':
        rows = WA.search_read([], ['id','name','slug','description','is_public','app_url','share_url','write_date'])
        return {"count": len(rows), "apps": rows}

    if action == 'get':
        slug = params.get('slug') or ''
        app  = WA.search([('slug','=',slug)], limit=1)
        if not app: raise ValueError(f"App '{slug}' not found.")
        return {"id": app.id, "name": app.name, "slug": app.slug,
                "jsx_code": app.jsx_code or '', "data_code": app.data_code or '',
                "app_url": app.app_url, "share_url": app.share_url or ''}

    if action == 'delete':
        slug = params.get('slug') or ''
        app  = WA.search([('slug','=',slug)], limit=1)
        if not app: raise ValueError(f"App '{slug}' not found.")
        name = app.name; app.unlink()
        return {"message": f"App '{name}' deleted."}

    if action == 'create':
        name = params.get('name') or ''
        if not name: raise ValueError("name required for create.")
        vals = {'name': name,
                'jsx_code':    params.get('jsx_code') or '',
                'data_code':   params.get('data_code') or '',
                'description': params.get('description') or '',
                'is_public':   bool(params.get('is_public', False))}
        if params.get('slug'): vals['slug'] = params['slug']

        # ── Pages ────────────────────────────────────────────────────────────
        raw_pages = params.get('pages')
        if isinstance(raw_pages, str):
            try:
                import json
                raw_pages = json.loads(raw_pages)
            except Exception:
                pass

        if isinstance(raw_pages, list) and raw_pages:
            vals['page_ids'] = []
            for i, p in enumerate(raw_pages):
                if not isinstance(p, dict): continue
                seq = p.get('sequence')
                seq = int(seq) if seq not in (None, '') else (i + 1) * 10
                vals['page_ids'].append((0, 0, {
                    'sequence':   seq,
                    'name':       p.get('name') or f'Page {i + 1}',
                    'route_path': p.get('route_path') or p.get('path') or '',
                    'page_title': p.get('page_title') or p.get('title') or '',
                    'jsx_code':   p.get('jsx_code') or '',
                }))

        # ── API Endpoints ─────────────────────────────────────────────────────
        raw_endpoints = params.get('endpoints')
        if isinstance(raw_endpoints, str):
            try:
                import json
                raw_endpoints = json.loads(raw_endpoints)
            except Exception:
                pass

        if isinstance(raw_endpoints, list) and raw_endpoints:
            vals['endpoint_ids'] = []
            for i, e in enumerate(raw_endpoints):
                if not isinstance(e, dict): continue
                seq = e.get('sequence')
                seq = int(seq) if seq not in (None, '') else (i + 1) * 10
                vals['endpoint_ids'].append((0, 0, {
                    'sequence':     seq,
                    'name':         e.get('name') or f'Endpoint {i + 1}',
                    'method':       str(e.get('method') or 'POST').upper(),
                    'path':         e.get('path') or '',
                    'description':  e.get('description') or '',
                    'handler_code': e.get('handler_code') or '',
                }))

        app = WA.create(vals)
        return {"id": app.id, "name": app.name, "slug": app.slug, "app_url": app.app_url,
                "share_url": app.share_url or '',
                "pages_created": len(vals.get('page_ids', [])),
                "endpoints_created": len(vals.get('endpoint_ids', [])),
                "message": f"App created. Open: {app.app_url}"}

    if action == 'update':
        slug = params.get('slug') or ''
        app  = WA.search([('slug','=',slug)], limit=1)
        if not app: raise ValueError(f"App '{slug}' not found.")
        upd = {}
        for k in ('name','jsx_code','data_code','description','is_public'):
            if k in params and params[k] is not None: upd[k] = params[k]

        # ── Pages (replace all) ───────────────────────────────────────────────
        raw_pages = params.get('pages')
        # Only overwrite if explicitly provided as a non-empty list
        if isinstance(raw_pages, list) and len(raw_pages) > 0:
            upd['page_ids'] = [(5, 0, 0)]
            for i, p in enumerate(raw_pages):
                if not isinstance(p, dict): continue
                seq = p.get('sequence')
                seq = int(seq) if seq not in (None, '') else (i + 1) * 10
                upd['page_ids'].append((0, 0, {
                    'sequence':   seq,
                    'name':       p.get('name') or f'Page {i + 1}',
                    'route_path': p.get('route_path') or p.get('path') or '',
                    'page_title': p.get('page_title') or p.get('title') or '',
                    'jsx_code':   p.get('jsx_code') or '',
                }))

        # ── Endpoints (replace all) ───────────────────────────────────────────
        raw_endpoints = params.get('endpoints')
        # Only overwrite if explicitly provided as a non-empty list
        if isinstance(raw_endpoints, list) and len(raw_endpoints) > 0:
            upd['endpoint_ids'] = [(5, 0, 0)]
            for i, e in enumerate(raw_endpoints):
                if not isinstance(e, dict): continue
                seq = e.get('sequence')
                seq = int(seq) if seq not in (None, '') else (i + 1) * 10
                upd['endpoint_ids'].append((0, 0, {
                    'sequence':     seq,
                    'name':         e.get('name') or f'Endpoint {i + 1}',
                    'method':       str(e.get('method') or 'POST').upper(),
                    'path':         e.get('path') or '',
                    'description':  e.get('description') or '',
                    'handler_code': e.get('handler_code') or '',
                }))

        app.write(upd)
        return {"id": app.id, "slug": app.slug, "app_url": app.app_url,
                "share_url": app.share_url or '',
                "pages_count":     len(app.page_ids),
                "endpoints_count": len(app.endpoint_ids),
                "message": f"App '{app.name}' updated."}

    raise ValueError(f"Unknown action '{action}'. Use: create, update, get, list, delete.")
