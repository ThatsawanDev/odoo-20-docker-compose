# -*- coding: utf-8 -*-
# mcp_controller.py — main controller (thin orchestrator)
# All tool logic lives in individual odoo_*.py files.

import json
import ipaddress
import logging
import time
import traceback
from datetime import timedelta

from odoo import fields, http, SUPERUSER_ID
from odoo.http import request, Response
from werkzeug.wrappers import Response as WerkzeugResponse

# ── Shared helpers ────────────────────────────────────────────────────────────
from .mcp_helpers import (
    _build_safe_globals, mcp_exec,
    _json_response, _ok, _err, _error_page,
    _resolve_env, _get_db, _log,
)

# ── Prompts / Resources / Tools meta ─────────────────────────────────────────
from .mcp_prompts import MCP_PROMPTS, MCP_RESOURCES, _resource_content, _PROMPT_MODULE_INSTALL_HINT
from .mcp_tools_meta import TOOLS

# ── Security ──────────────────────────────────────────────────────────────────
from . import mcp_security_helpers as _mcp_sec

# ── Email template (already separate) ────────────────────────────────────────
from .mcp_email_template_tools import _tool_odoo_email_template

# ── Read / Query ──────────────────────────────────────────────────────────────
from .odoo_read import _tool_list_models, _tool_get_model_info, _tool_get_fields

# ── Search ────────────────────────────────────────────────────────────────────
from .odoo_search import _tool_search_read, _tool_get_record

# ── Write / Mutate ────────────────────────────────────────────────────────────
from .odoo_write import _tool_create, _tool_write, _tool_unlink
from .odoo_import_data import _tool_import_data

# ── Custom field ──────────────────────────────────────────────────────────────
from .odoo_custom_field import _tool_add_custom_field

# ── Aggregate ─────────────────────────────────────────────────────────────────
from .odoo_aggregate import _tool_aggregate, _tool_read_group

# ── Execute ───────────────────────────────────────────────────────────────────
from .odoo_execute import _tool_call_method, _tool_execute_action, _tool_execute_orm

# ── Build / Manage ────────────────────────────────────────────────────────────
from .odoo_echart import _tool_manage_echart, _prepare_echart_data_code, _normalize_echart_result
from .odoo_webapp import _tool_manage_webapp
from .odoo_module import _tool_manage_module
from .odoo_snippet import _tool_manage_snippet
from .odoo_report import _tool_manage_report

# ── Code search ───────────────────────────────────────────────────────────────
from .odoo_code_search import (
    _tool_code_search, _tool_code_read,
    _tool_search_webapp_code, _tool_search_module_code,
)

_logger = logging.getLogger(__name__)

# ── Tool dispatch table ───────────────────────────────────────────────────────

TOOL_DISPATCH = {
    'odoo_list_models':        (_tool_list_models,          'list_models'),
    'odoo_get_model_info':     (_tool_get_model_info,       'list_models'),
    'odoo_get_fields':         (_tool_get_fields,           'get_fields'),
    'odoo_search_read':        (_tool_search_read,          'search_read'),
    'odoo_get_record':         (_tool_get_record,           'search_read'),
    'odoo_create':             (_tool_create,               'create'),
    'odoo_write':              (_tool_write,                'write'),
    'odoo_unlink':             (_tool_unlink,               'unlink'),
    'odoo_import_data':        (_tool_import_data,          'create'),
    'odoo_aggregate':          (_tool_aggregate,            'search_read'),
    'odoo_call_method':        (_tool_call_method,          'write'),
    'odoo_execute_action':     (_tool_execute_action,       'write'),
    'odoo_add_custom_field':   (_tool_add_custom_field,     'create'),
    'odoo_execute_orm':        (_tool_execute_orm,          'execute'),
    'odoo_manage_echart':      (_tool_manage_echart,        'echart'),
    'odoo_manage_webapp':      (_tool_manage_webapp,        'webapp'),
    'odoo_manage_module':      (_tool_manage_module,        'module'),
    'odoo_read_group':         (_tool_read_group,           'search_read'),
    'odoo_code_search':        (_tool_code_search,          'code'),
    'odoo_code_read':          (_tool_code_read,            'code'),
    'odoo_search_webapp_code': (_tool_search_webapp_code,   'code'),
    'odoo_search_module_code': (_tool_search_module_code,   'code'),
    'odoo_manage_snippet':     (_tool_manage_snippet,       'snippet'),
    'odoo_manage_report':      (_tool_manage_report,        'report'),
    'odoo_email_template':     (_tool_odoo_email_template,  'email_template'),
}


# ═════════════════════════════════════════════════════════════════════════════
# McpController — HTTP routes only, zero tool logic
# ═════════════════════════════════════════════════════════════════════════════

class McpController(http.Controller):

    def _get_client_name_from_token(self, raw_token):
        """Resolve the MCP client type from a bearer token when available."""
        if not raw_token:
            return ''
        try:
            rec = request.env['mcp.api.token'].sudo().search(
                [('token', '=', raw_token), ('active', '=', True)], limit=1)
            return rec.mcp_client or ''
        except Exception:
            return ''

    def _visible_tools(self, env, user, client_name=''):
        return _mcp_sec.get_visible_tools(env, user, TOOLS, client_name=client_name)

    def _get_base_url(self):
        proto = request.httprequest.headers.get('X-Forwarded-Proto', '')
        host  = (request.httprequest.headers.get('X-Forwarded-Host', '')
                 or request.httprequest.headers.get('Host', ''))
        if proto and host:
            return f"{proto}://{host}"
        url = request.env['ir.config_parameter'].sudo().get_str('web.base.url', '')
        if url:
            return url.rstrip('/')
        return f"https://{request.httprequest.host}"

    def _oauth_resource_value(self):
        return f"{self._get_base_url()}/mcp/v1"

    def _normalize_scope(self, scope_value):
        return {s.strip() for s in str(scope_value or '').replace('+', ' ').split() if s.strip()}

    def _scopes_to_string(self, scopes):
        ordered = ['read', 'write', 'execute', 'offline_access']
        remaining = sorted(set(scopes) - set(ordered))
        return ' '.join([s for s in ordered if s in scopes] + remaining)

    def _normalize_resource(self, resource):
        return str(resource or '').strip()

    def _validate_resource(self, resource):
        expected = self._oauth_resource_value()
        if not resource:
            return expected, None
        if self._normalize_resource(resource).rstrip('/') != expected.rstrip('/'):
            return '', 'invalid_target'
        return expected, None

    def _get_oauth_client(self, client_id):
        if not client_id:
            return request.env['mcp.oauth.client']
        return request.env['mcp.oauth.client'].sudo().search(
            [('client_id', '=', client_id), ('active', '=', True)], limit=1)

    def _infer_oauth_mcp_client(self, client_rec=None, redirect_uri=''):
        haystacks = [
            str(getattr(client_rec, 'client_name', '') or '').lower(),
            str(redirect_uri or '').lower(),
            str(getattr(client_rec, 'redirect_uris', '') or '').lower(),
        ]
        text = '\n'.join(part for part in haystacks if part)
        if any(key in text for key in ('anthropic', 'claude.ai', 'claudeusercontent', 'claude')):
            return 'claude_web'
        if any(key in text for key in ('chatgpt', 'openai', 'chat.openai')):
            return 'chatgpt_web'
        return 'chatgpt_web'

    def _infer_request_mcp_client(self, messages):
        for item in messages or []:
            if not isinstance(item, dict):
                continue
            params = item.get('params') or {}
            client = params.get('clientInfo') or {}
            haystack = ' '.join([
                str(client.get('name', '') or ''),
                str(client.get('version', '') or ''),
                str(request.httprequest.headers.get('User-Agent', '') or ''),
            ]).lower()
            if any(key in haystack for key in ('anthropic', 'claude')):
                return 'claude_web'
            if any(key in haystack for key in ('chatgpt', 'openai')):
                return 'chatgpt_web'
        return ''

    def _validate_scope_request(self, client_rec, requested_scope):
        client_scopes = self._normalize_scope(client_rec.scope)
        scopes = self._normalize_scope(requested_scope or client_rec.scope)
        if not scopes:
            scopes = client_scopes
        if not scopes:
            return '', 'invalid_scope'
        if client_scopes and not scopes.issubset(client_scopes):
            return '', 'invalid_scope'
        return self._scopes_to_string(scopes), None

    def _required_scope_for_tool(self, tool_name):
        return _mcp_sec.TOOL_CATEGORY.get(tool_name, 'read')

    def _scope_allows_tool(self, token_rec, tool_name):
        granted = self._normalize_scope(getattr(token_rec, 'scope', '') or '')
        if not granted:
            return True
        return self._required_scope_for_tool(tool_name) in granted

    def _get_request_ip(self):
        forwarded_for = request.httprequest.headers.get('X-Forwarded-For', '')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        real_ip = request.httprequest.headers.get('X-Real-IP', '')
        if real_ip:
            return real_ip.strip()
        return (request.httprequest.environ.get('REMOTE_ADDR', '') or '').strip()

    def _split_ip_rules(self, raw_text):
        entries = []
        for chunk in str(raw_text or '').replace('\n', ',').split(','):
            chunk = chunk.strip()
            if chunk:
                entries.append(chunk)
        return entries

    def _ip_matches(self, client_ip, rule):
        try:
            addr = ipaddress.ip_address(client_ip)
            if '/' in rule:
                return addr in ipaddress.ip_network(rule, strict=False)
            return addr == ipaddress.ip_address(rule)
        except ValueError:
            _logger.warning("MCP security: invalid IP rule ignored: %s", rule)
            return False

    def _security_json_error(self, message, status=403):
        return Response(
            json.dumps({'error': 'access_denied', 'error_description': message}),
            status=status,
            content_type='application/json',
            headers={'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store'},
        )

    def _enforce_ip_policy(self, cfg, *, req_id=None, html=False, env=None, user=None, route_name=''):
        client_ip = self._get_request_ip()
        blacklist = self._split_ip_rules(cfg.ip_blacklist)
        whitelist = self._split_ip_rules(cfg.ip_whitelist)

        blocked = any(self._ip_matches(client_ip, rule) for rule in blacklist)
        if not blocked and whitelist:
            blocked = not any(self._ip_matches(client_ip, rule) for rule in whitelist)

        if not blocked:
            return None

        message = f"Access denied from IP {client_ip or 'unknown'}."
        log_env = env or request.env
        try:
            _log(log_env, tool='', method='security/ip', operation='protocol',
                 user=user, log_level='warning', state='error',
                 error=message, ip_address=client_ip,
                 payload={'route': route_name or request.httprequest.path})
        except Exception:
            pass

        if html:
            return Response(_error_page("Access Denied", message), status=403, mimetype='text/html')
        if req_id is not None:
            return _err(req_id, -32001, message)
        return self._security_json_error(message, status=403)

    def _enforce_rate_limit(self, env, user, req_id, *, route_name=''):
        cfg = env['mcp.config'].sudo().get_config()
        if not cfg.rate_limit_enabled:
            return None
        limit = int(cfg.rate_limit_per_minute or 0)
        if limit <= 0 or not user:
            return None

        cutoff = fields.Datetime.now() - timedelta(minutes=1)
        recent_count = env['mcp.log'].sudo().search_count([
            ('user_id', '=', user.id),
            ('method', '=', 'tools/call'),
            ('create_date', '>=', cutoff),
        ])
        if recent_count < limit:
            return None

        message = (
            f"Rate limit exceeded: maximum {limit} MCP tool call(s) per minute. "
            f"Please retry shortly."
        )
        _log(env, tool='', method='security/rate_limit', operation='protocol',
             user=user, log_level='warning', state='error',
             error=message, request_id=req_id, ip_address=self._get_request_ip(),
             payload={'route': route_name or request.httprequest.path, 'limit': limit})
        return _err(req_id, -32029, message)

    def _get_session_env_user(self):
        uid = request.session.uid
        if not uid:
            return None, None
        env = request.env(user=uid)
        user = env['res.users'].browse(uid)
        return env, user

    def _is_internal_builder_user(self, user):
        if not user:
            return False
        try:
            return (
                user.has_group('eb_odoo_mcp_server_studio.group_mcp_user')
                or user.has_group('eb_odoo_mcp_server_studio.group_mcp_admin')
                or user.has_group('base.group_system')
            )
        except Exception:
            return False

    def _is_builder_admin(self, user):
        if not user:
            return False
        try:
            return (
                user.has_group('eb_odoo_mcp_server_studio.group_mcp_admin')
                or user.has_group('base.group_system')
            )
        except Exception:
            return False

    def _access_denied_response(self, *, message, html=False, status=403):
        if html:
            return Response(_error_page("Access Denied", message), status=status, mimetype='text/html')
        return _json_response({'error': message}, status)

    def _get_portal_home_slug(self):
        slug = ''
        try:
            slug = request.env['ir.config_parameter'].sudo().get_str(
                'mcp.portal_home_slug', ''
            )
        except Exception:
            slug = ''
        return (slug or 'sales-portal').strip()

    def _resolve_public_record_access(self, rec, *, share_token='', html=False, route_name=''):
        if not rec or not rec.exists() or not rec.active:
            return None, None, None, self._access_denied_response(
                message="Requested content was not found.",
                html=html,
                status=404,
            )

        cfg = request.env['mcp.config'].sudo().get_config()
        ip_err = self._enforce_ip_policy(cfg, html=html, route_name=route_name)
        if ip_err:
            return None, None, None, ip_err

        sess_env, sess_user = self._get_session_env_user()
        rec_model = getattr(rec, '_name', '')
        if sess_user and self._is_internal_builder_user(sess_user):
            if self._is_builder_admin(sess_user):
                return sess_env, sess_user, 'session_admin', None
            owner_id = rec.user_id.id if getattr(rec, 'user_id', False) else False
            if not owner_id or sess_user.id == owner_id or getattr(rec, 'is_public', False):
                return sess_env, sess_user, 'session', None

        if sess_user and rec_model == 'mcp.webapp':
            return request.env(user=sess_user.id), sess_user, 'session_authenticated', None

        if share_token:
            expected = getattr(rec, 'share_token', '') or ''
            if not getattr(rec, 'is_public', False):
                return None, None, None, self._access_denied_response(
                    message="This content is not publicly shared.",
                    html=html,
                )
            if not expected or expected != share_token:
                return None, None, None, self._access_denied_response(
                    message="Invalid share token.",
                    html=html,
                )
            owner = rec.user_id or request.env.user
            return request.env(user=owner.id), owner, 'share', None

        return None, None, None, self._access_denied_response(
            message="Login is required to access this content.",
            html=html,
        )

    def _oauth_meta(self):
        base = self._get_base_url()
        return _json_response({
            "resource":                 self._oauth_resource_value(),
            "authorization_servers":    [base],
            "bearer_methods_supported": ["header"],
            "scopes_supported":         ["read", "write", "execute", "offline_access"],
        })

    def _oauth_auth_server_meta(self):
        base   = self._get_base_url()
        db     = _get_db()
        prefix = f"/{db}" if db else ""
        return _json_response({
            "issuer":                               base,
            "authorization_endpoint":               f"{base}{prefix}/oauth/authorize",
            "token_endpoint":                       f"{base}{prefix}/oauth/token",
            "registration_endpoint":                f"{base}/mcp/oauth/register",
            "response_types_supported":             ["code"],
            "grant_types_supported":                ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported":     ["S256"],
            "scopes_supported":                     ["read", "write", "execute", "offline_access"],
            "token_endpoint_auth_methods_supported": ["none"],
        })

    # ── Well-known discovery ───────────────────────────────────────────────

    @http.route('/.well-known/oauth-protected-resource',
                type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False, save_session=False)
    def well_known_root(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return Response('', status=200, headers={'Access-Control-Allow-Origin': '*'})
        return self._oauth_meta()

    @http.route('/mcp/v1/.well-known/oauth-protected-resource',
                type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False, save_session=False)
    def well_known_mcp(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return Response('', status=200, headers={'Access-Control-Allow-Origin': '*'})
        return self._oauth_meta()

    @http.route('/.well-known/oauth-authorization-server',
                type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False, save_session=False)
    def well_known_oauth_auth_server(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return Response('', status=200, headers={'Access-Control-Allow-Origin': '*'})
        return self._oauth_auth_server_meta()

    @http.route('/mcp/v1/.well-known/oauth-authorization-server',
                type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False, save_session=False)
    def well_known_oauth_auth_server_mcp(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return Response('', status=200, headers={'Access-Control-Allow-Origin': '*'})
        return self._oauth_auth_server_meta()

    @http.route('/.well-known/oauth-protected-resource/mcp/v1',
                type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False, save_session=False)
    def well_known_resource_mcp_path(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return Response('', status=200, headers={'Access-Control-Allow-Origin': '*'})
        return self._oauth_meta()

    @http.route('/.well-known/oauth-authorization-server/mcp/v1',
                type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False, save_session=False)
    def well_known_auth_server_mcp_path(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return Response('', status=200, headers={'Access-Control-Allow-Origin': '*'})
        return self._oauth_auth_server_meta()

    @http.route('/.well-known/openid-configuration',
                type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False, save_session=False)
    def well_known_openid_config(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return Response('', status=200, headers={'Access-Control-Allow-Origin': '*'})
        return self._oauth_auth_server_meta()

    @http.route('/mcp/v1/.well-known/openid-configuration',
                type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False, save_session=False)
    def well_known_openid_config_mcp(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return Response('', status=200, headers={'Access-Control-Allow-Origin': '*'})
        return self._oauth_auth_server_meta()

    # ── OAuth register ────────────────────────────────────────────────────

    @http.route('/mcp/oauth/register', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, save_session=False)
    def oauth_register(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return Response('', status=200, headers={
                'Access-Control-Allow-Origin':  '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
            })
        cfg = request.env['mcp.config'].sudo().get_config()
        ip_err = self._enforce_ip_policy(cfg, route_name='oauth_register')
        if ip_err:
            return ip_err
        try:
            body = request.httprequest.data
            data = json.loads(body.decode()) if isinstance(body, bytes) else json.loads(body or '{}')
        except Exception:
            return Response(
                json.dumps({'error': 'invalid_request', 'error_description': 'Invalid JSON'}),
                status=400, content_type='application/json',
                headers={'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store'},
            )
        client_name   = data.get('client_name', 'MCP Client')
        redirect_uris = data.get('redirect_uris', [])
        scope         = data.get('scope', 'read write execute offline_access')
        grant_types   = data.get('grant_types', ['authorization_code', 'refresh_token'])
        if isinstance(grant_types, list):
            grant_types = ' '.join(grant_types)
        result = request.env['mcp.oauth.client'].sudo().register_client(
            client_name=client_name, redirect_uris=redirect_uris,
            scope=scope, grant_types=grant_types,
        )
        return _json_response(result)

    # ── OAuth authorize ───────────────────────────────────────────────────

    @http.route('/<string:db>/oauth/authorize', type='http', auth='user',
                methods=['GET', 'POST'], csrf=False, save_session=True)
    def oauth_authorize(self, db, **kw):
        cfg = request.env['mcp.config'].sudo().get_config()
        ip_err = self._enforce_ip_policy(cfg, html=True, env=request.env,
                                         user=request.env.user, route_name='oauth_authorize')
        if ip_err:
            return ip_err
        is_mcp_user  = request.env.user.has_group('eb_odoo_mcp_server_studio.group_mcp_user')
        is_mcp_admin = request.env.user.has_group('eb_odoo_mcp_server_studio.group_mcp_admin')
        is_sys_admin = request.env.user.has_group('base.group_system')
        if not (is_mcp_user or is_mcp_admin or is_sys_admin):
            return Response('<h1>Access denied</h1><p>Your account does not have MCP access.</p>',
                            status=403, content_type='text/html')

        response_type         = kw.get('response_type', 'code')
        client_id             = kw.get('client_id', '')
        redirect_uri          = kw.get('redirect_uri', '')
        scope                 = kw.get('scope', 'read write execute offline_access')
        state                 = kw.get('state', '')
        resource              = kw.get('resource', '')
        code_challenge        = kw.get('code_challenge', '')
        code_challenge_method = kw.get('code_challenge_method', 'S256')

        if response_type != 'code' or not client_id or not redirect_uri:
            return self._oauth_error(redirect_uri, 'invalid_request', state)
        client_rec = self._get_oauth_client(client_id)
        if not client_rec or not client_rec.validate_client(client_id, redirect_uri):
            return self._oauth_error('', 'invalid_client', state)
        scope, scope_err = self._validate_scope_request(client_rec, scope)
        if scope_err:
            return self._oauth_error(redirect_uri, scope_err, state)
        resource, resource_err = self._validate_resource(resource)
        if resource_err:
            return self._oauth_error(redirect_uri, resource_err, state)
        if code_challenge_method != 'S256' or not code_challenge:
            return self._oauth_error(redirect_uri, 'invalid_request', state)

        if request.httprequest.method == 'POST':
            if kw.get('consent') != 'allow':
                return self._oauth_error(redirect_uri, 'access_denied', state)
            code = request.env['mcp.oauth.code'].create_code(
                user_id=request.env.uid, client_id=client_id, redirect_uri=redirect_uri,
                scope=scope, state=state, code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
                resource=resource,
            )
            sep      = '&' if '?' in redirect_uri else '?'
            url      = f"{redirect_uri}{sep}code={code}"
            if state: url += f"&state={state}"
            safe_url = url.replace('"', '%22').replace('<', '%3C').replace('>', '%3E')
            html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta http-equiv="refresh" content="0;url={safe_url}">
<title>Redirecting...</title>
<style>body{{font-family:sans-serif;display:flex;align-items:center;
justify-content:center;height:100vh;margin:0;background:#0f172a;color:#94a3b8}}</style>
</head><body>
<script>window.location.replace("{safe_url}");</script>
<p>Redirecting to application&hellip;</p>
</body></html>'''
            return Response(html, status=200, content_type='text/html',
                            headers={'Cache-Control': 'no-store', 'Access-Control-Allow-Origin': '*'})

        from html import escape as _he
        h           = lambda s: _he(str(s), quote=True) if s else ''
        scope_list  = [s.strip() for s in scope.replace('+', ' ').split() if s.strip()]
        html = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Authorize MCP Access</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #f1f5f9; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px; }}
.card {{ background: #fff; border-radius: 16px; padding: 40px 36px; max-width: 440px; width: 100%;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,.07); border: 1px solid #e2e8f0; }}
.logo {{ width: 56px; height: 56px; background: linear-gradient(135deg,#6366f1,#8b5cf6);
  border-radius: 14px; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center; font-size: 26px; }}
h1 {{ font-size: 20px; font-weight: 700; color: #0f172a; text-align: center; margin-bottom: 6px; }}
.sub {{ font-size: 13px; color: #64748b; text-align: center; margin-bottom: 24px; }}
.user-info {{ background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px;
  padding: 10px 14px; font-size: 13px; color: #166534; margin-bottom: 24px; }}
.actions {{ display: flex; gap: 10px; }}
.btn {{ flex: 1; padding: 12px; border-radius: 10px; font-size: 14px; font-weight: 600; cursor: pointer; border: none; }}
.btn-allow {{ background: linear-gradient(135deg,#6366f1,#8b5cf6); color: #fff; }}
.btn-deny {{ background: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0; }}
.footer {{ font-size: 11px; color: #94a3b8; text-align: center; margin-top: 16px; }}
</style></head><body>
<div class="card">
  <div class="logo">🔌</div>
  <h1>Authorize MCP Access</h1>
  <p class="sub">An AI application wants to connect to your Odoo instance</p>
  <div class="user-info">✅ Authorizing as: <strong>{request.env.user.name}</strong></div>
  <form method="post" style="margin:0">
    <input type="hidden" name="consent" value="allow"/>
    <input type="hidden" name="response_type" value="{h(response_type)}"/>
    <input type="hidden" name="client_id" value="{h(client_id)}"/>
    <input type="hidden" name="redirect_uri" value="{h(redirect_uri)}"/>
    <input type="hidden" name="scope" value="{h(scope)}"/>
    <input type="hidden" name="state" value="{h(state)}"/>
    <input type="hidden" name="resource" value="{h(resource)}"/>
    <input type="hidden" name="code_challenge" value="{h(code_challenge)}"/>
    <input type="hidden" name="code_challenge_method" value="{h(code_challenge_method)}"/>
    <div class="actions"><button type="submit" class="btn btn-allow">✓ Allow Access</button></div>
  </form>
  <form method="post" style="margin-top:10px">
    <input type="hidden" name="consent" value="deny"/>
    <input type="hidden" name="redirect_uri" value="{h(redirect_uri)}"/>
    <input type="hidden" name="state" value="{h(state)}"/>
    <button type="submit" class="btn btn-deny" style="width:100%">✗ Deny</button>
  </form>
  <p class="footer">🔒 OAuth 2.1 + PKCE · Token tied to your Odoo account</p>
</div></body></html>'''
        return Response(html, content_type='text/html')

    # ── OAuth token ───────────────────────────────────────────────────────

    @http.route('/<string:db>/oauth/token', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, save_session=False)
    def oauth_token(self, db, **kw):
        if request.httprequest.method == 'OPTIONS':
            return Response('', status=200, headers={
                'Access-Control-Allow-Origin':  '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
            })
        cfg = request.env['mcp.config'].sudo().get_config()
        ip_err = self._enforce_ip_policy(cfg, route_name='oauth_token')
        if ip_err:
            return ip_err

        import base64 as _b64
        import hashlib as _hl

        form = request.httprequest.form
        if form:
            grant_type    = form.get('grant_type', '')
            code          = form.get('code', '')
            redirect_uri  = form.get('redirect_uri', '')
            client_id     = form.get('client_id', '')
            resource      = form.get('resource', '')
            code_verifier = form.get('code_verifier', '')
            raw_refresh   = form.get('refresh_token', '')
        else:
            raw = request.httprequest.data
            try:
                body          = json.loads(raw or b'{}')
                grant_type    = body.get('grant_type', '')
                code          = body.get('code', '')
                redirect_uri  = body.get('redirect_uri', '')
                client_id     = body.get('client_id', '')
                resource      = body.get('resource', '')
                code_verifier = body.get('code_verifier', '')
                raw_refresh   = body.get('refresh_token', '')
            except Exception:
                return self._oauth_token_error('invalid_request', 400)

        Token = request.env['mcp.api.token'].sudo()

        if grant_type == 'authorization_code':
            if not code or not code_verifier or not client_id or not redirect_uri:
                return self._oauth_token_error('invalid_grant', 400)
            client_rec = self._get_oauth_client(client_id)
            if not client_rec or not client_rec.validate_client(client_id, redirect_uri):
                return self._oauth_token_error('invalid_client', 400)
            resource, resource_err = self._validate_resource(resource)
            if resource_err:
                return self._oauth_token_error(resource_err, 400)
            rec = request.env['mcp.oauth.code'].sudo().search(
                [('code', '=', code), ('consumed', '=', False)], limit=1)
            if not rec or fields.Datetime.now() > rec.expiry:
                return self._oauth_token_error('invalid_grant', 400)
            if rec.client_id != client_id or rec.redirect_uri != redirect_uri:
                return self._oauth_token_error('invalid_grant', 400)
            if (rec.resource or '').rstrip('/') != resource.rstrip('/'):
                return self._oauth_token_error('invalid_target', 400)
            computed = _b64.urlsafe_b64encode(
                _hl.sha256(code_verifier.encode()).digest()
            ).rstrip(b'=').decode()
            if computed != rec.code_challenge:
                return self._oauth_token_error('invalid_grant', 400)
            rec.consumed  = True
            granted_scope = rec.scope or client_rec.scope or 'read write execute offline_access'
            token_rec     = Token.create([{
                'name':    f'MCP OAuth ({client_id or "client"})',
                'user_id': rec.user_id.id,
                'scope': granted_scope,
                'audience': resource,
                'client_id': client_id,
                'mcp_client': self._infer_oauth_mcp_client(client_rec, redirect_uri),
            }])[0]
            payload = {
                'access_token':  token_rec.token,
                'token_type':    'Bearer',
                'expires_in':    max(int((token_rec.expires_at - fields.Datetime.now()).total_seconds()), 0),
                'scope':         granted_scope,
                'resource':      resource,
            }
            if 'offline_access' in self._normalize_scope(granted_scope):
                payload['refresh_token'] = token_rec.refresh_token
            return _json_response(payload)

        if grant_type == 'refresh_token':
            if not raw_refresh:
                return self._oauth_token_error('invalid_grant', 400)
            old = Token.resolve_refresh_token(raw_refresh)
            if not old:
                return self._oauth_token_error('invalid_grant', 400)
            if 'offline_access' not in self._normalize_scope(old.scope or ''):
                return self._oauth_token_error('invalid_grant', 400)
            if old.client_id and client_id and old.client_id != client_id:
                return self._oauth_token_error('invalid_client', 400)
            if not client_id:
                client_id = old.client_id or ''
            resource, resource_err = self._validate_resource(resource or old.audience)
            if resource_err:
                return self._oauth_token_error(resource_err, 400)
            if old.audience and old.audience.rstrip('/') != resource.rstrip('/'):
                return self._oauth_token_error('invalid_target', 400)
            old.write({'active': False})
            new_tok = Token.create({
                'name': old.name,
                'user_id': old.user_id.id,
                'scope': old.scope,
                'audience': old.audience or resource,
                'client_id': old.client_id or client_id,
                'mcp_client': old.mcp_client or self._infer_oauth_mcp_client(
                    self._get_oauth_client(old.client_id or client_id)
                ),
            })
            return _json_response({
                'access_token':  new_tok.token,
                'refresh_token': new_tok.refresh_token,
                'token_type':    'Bearer',
                'expires_in':    max(int((new_tok.expires_at - fields.Datetime.now()).total_seconds()), 0),
                'scope':         new_tok.scope or 'read write execute offline_access',
                'resource':      new_tok.audience or resource,
            })

        return self._oauth_token_error('unsupported_grant_type', 400)

    def _oauth_error(self, redirect_uri, error, state):
        if redirect_uri:
            sep      = '&' if '?' in redirect_uri else '?'
            url      = f"{redirect_uri}{sep}error={error}"
            if state: url += f"&state={state}"
            safe_url = url.replace('"', '%22').replace('<', '%3C').replace('>', '%3E')
            html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta http-equiv="refresh" content="0;url={safe_url}">
</head><body>
<script>window.location.replace("{safe_url}");</script>
<p>Redirecting...</p>
</body></html>'''
            return Response(html, status=200, content_type='text/html',
                            headers={'Cache-Control': 'no-store', 'Access-Control-Allow-Origin': '*'})
        return Response(f"OAuth error: {error}", status=400)

    def _oauth_token_error(self, error, status=400):
        return Response(
            json.dumps({'error': error, 'error_description': error}),
            status=status, content_type='application/json',
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Expose-Headers': 'WWW-Authenticate',
                'Cache-Control': 'no-store',
            },
        )

    def _oauth_resource_metadata_url(self):
        return f"{self._get_base_url()}/mcp/v1/.well-known/oauth-protected-resource"

    def _oauth_www_authenticate_header(self, *, error=None, message=None, scope=None):
        def _quote(value):
            return str(value or '').replace('\\', '\\\\').replace('"', '\\"')

        parts = [
            f'Bearer resource_metadata="{_quote(self._oauth_resource_metadata_url())}"',
        ]
        if scope:
            parts.append(f'scope="{_quote(scope)}"')
        if error:
            parts.append(f'error="{_quote(error)}"')
        if message:
            parts.append(f'error_description="{_quote(message)}"')
        return ', '.join(parts)

    def _oauth_unauthorized_response(self, message="Authorization required", *, invalid_token=False):
        scope = "read write execute offline_access"
        error = 'invalid_token' if invalid_token else None
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Expose-Headers': 'WWW-Authenticate',
            'Cache-Control': 'no-store',
            'WWW-Authenticate': self._oauth_www_authenticate_header(
                error=error,
                message=message,
                scope=scope,
            ),
        }
        return Response(
            json.dumps({
                'error': 'invalid_token',
                'error_description': message,
            }),
            status=401,
            content_type='application/json',
            headers=headers,
        )

    def _is_valid_oauth_access_token(self, token_rec, required_client=''):
        if not token_rec:
            return False
        if not getattr(token_rec, 'client_id', ''):
            return False
        if not getattr(token_rec, 'audience', ''):
            return False
        client_rec = self._get_oauth_client(token_rec.client_id)
        if not client_rec:
            return False
        if required_client and getattr(token_rec, 'mcp_client', '') != required_client:
            return False
        return True

    def _resolve_oauth_bearer_env(self, raw_token, required_client=''):
        resolved_env, resolved_user, token_rec = _resolve_env(
            raw_token,
            expected_audience=self._oauth_resource_value(),
        )
        if resolved_env is None or not self._is_valid_oauth_access_token(
            token_rec, required_client=required_client
        ):
            return None, None, None
        return resolved_env, resolved_user, token_rec

    def _mcp_public_method(self, method):
        # Remote OAuth connectors behave more reliably with per-server auth:
        # every JSON-RPC request to /mcp/v1 should already have a bearer token.
        return False

    def _mcp_messages_need_bearer(self, messages):
        for item in messages:
            if not isinstance(item, dict):
                continue
            if not self._mcp_public_method(item.get('method', '')):
                return True
        return False

    # ── Standard MCP endpoints ────────────────────────────────────────────

    @http.route('/mcp/v1/', type='http', auth='none', methods=['OPTIONS'],
                csrf=False, save_session=False)
    def cors_preflight(self, **kwargs):
        return Response('', status=200, headers={
            'Access-Control-Allow-Origin':  '*',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Expose-Headers': 'WWW-Authenticate',
        })

    @http.route('/mcp/v1/health', type='http', auth='none', methods=['GET'],
                csrf=False, save_session=False)
    def health(self, **kwargs):
        return _json_response({"status": "ok", "service": "odoo-mcp-server", "tools": len(TOOLS)})

    @http.route('/mcp/v1/', type='http', auth='none', methods=['GET'],
                csrf=False, save_session=False)
    def info(self, **kwargs):
        cfg = request.env['mcp.config'].sudo().get_config()
        ip_err = self._enforce_ip_policy(cfg, route_name='mcp_info')
        if ip_err:
            return ip_err
        auth_header = request.httprequest.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            # Compatibility fallback for remote web clients that probe the MCP
            # root URL directly instead of following the 401 challenge path.
            # POST /mcp/v1 remains protected and still forces OAuth.
            return self._oauth_meta()
        raw_token = auth_header[7:].strip()
        resolved_env, resolved_user, token_rec = self._resolve_oauth_bearer_env(raw_token)
        if resolved_env is None:
            return self._oauth_meta()
        _logger.debug("MCP GET /mcp/v1/ info request")
        return _json_response({
            "name": "Odoo MCP Server", "version": "2.0.0",
            "protocolVersion": "2024-11-05", "tools_count": len(TOOLS),
            "capabilities": {
                "tools":     {"listChanged": False},
                "prompts":   {"listChanged": True},
                "resources": {"listChanged": False},
            },
        })

    @http.route('/mcp/v1/', type='http', auth='none', methods=['POST'],
                csrf=False, save_session=False)
    def handle(self, **kwargs):
        try:
            body = json.loads(request.httprequest.data or b'{}')
        except Exception:
            return _err(None, -32700, "Parse error: invalid JSON")

        cfg = request.env['mcp.config'].sudo().get_config()
        if not cfg.server_enabled:
            if isinstance(body, dict):
                return _err(body.get('id'), -32000, "MCP Server is disabled by administrator.")
            return _err(None, -32000, "MCP Server is disabled by administrator.")

        messages = body if isinstance(body, list) else [body]
        required_client = self._infer_request_mcp_client(messages)
        if self._mcp_messages_need_bearer(messages):
            auth_header = request.httprequest.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return self._oauth_unauthorized_response(
                    "Authorization required for protected MCP methods.",
                )
            raw_token = auth_header[7:].strip()
            resolved_env, resolved_user, token_rec = self._resolve_oauth_bearer_env(
                raw_token,
                required_client=required_client,
            )
            if resolved_env is None:
                return self._oauth_unauthorized_response(
                    "The access token is invalid or expired.",
                    invalid_token=True,
                )

        if isinstance(body, list):
            if not body:
                return _err(None, -32600, "Invalid Request")
            responses = []
            for item in body:
                if not isinstance(item, dict):
                    responses.append(_err(None, -32600, "Invalid Request"))
                    continue
                resp = self._handle_rpc_message(item, cfg)
                if isinstance(resp, WerkzeugResponse):
                    payload = resp.get_data(as_text=True)
                    if payload:
                        responses.append(json.loads(payload))
                elif resp is not None:
                    responses.append(resp)
            return _json_response(responses)

        if not isinstance(body, dict):
            return _err(None, -32600, "Invalid Request")
        return self._handle_rpc_message(body, cfg)

    def _handle_rpc_message(self, body, cfg):
        req_id = body.get('id')
        method = body.get('method', '')
        params = body.get('params') or {}
        ip_err = self._enforce_ip_policy(cfg, req_id=req_id, route_name='mcp_handle')
        if ip_err:
            return ip_err
        _logger.info("MCP ← %s  id=%s", method, req_id)
        if method == 'initialize':
            return self._handle_initialize(req_id, params)
        if method == 'notifications/initialized':
            return Response(status=204)
        if method == 'ping':
            return _ok(req_id, {})
        if method == 'resources/list':
            return _ok(req_id, {"resources": MCP_RESOURCES})
        if method == 'resources/read':
            uri = params.get('uri', '')
            return _ok(req_id, {
                "contents": [{"uri": uri, "mimeType": "text/plain", "text": _resource_content(uri)}]
            })

        auth_header = request.httprequest.headers.get('Authorization', '')
        _logger.debug("MCP auth: %s", 'Bearer ***' if auth_header.startswith('Bearer ') else 'session')
        env = request.env
        user = env.user
        client_name = ''
        token_rec = None
        if auth_header.startswith('Bearer '):
            raw_token = auth_header[7:].strip()
            resolved_env, resolved_user, token_rec = self._resolve_oauth_bearer_env(raw_token)
            if resolved_env is None:
                return self._oauth_unauthorized_response(
                    "The access token is invalid or expired.",
                    invalid_token=True,
                )
            env = resolved_env
            user = resolved_user
            client_name = self._get_client_name_from_token(raw_token)
        else:
            return self._oauth_unauthorized_response(
                "Authorization required for protected MCP methods.",
            )

        if method == 'tools/list':
            visible_tools = self._visible_tools(env, user, client_name=client_name)
            if token_rec and token_rec.scope:
                visible_tools = [
                    tool for tool in visible_tools
                    if self._scope_allows_tool(token_rec, tool.get('name', ''))
                ]
            _logger.debug("MCP tools/list — returning %d tools for client=%s user=%s",
                          len(visible_tools), client_name or 'session',
                          user.login if user else '?')
            return _ok(req_id, {"tools": visible_tools})
        if method == 'ping':
            return _ok(req_id, {})

        if method == 'prompts/list':
            _logger.debug("MCP prompts/list")
            pub = [{k: v for k, v in p.items() if k != '_text'} for p in MCP_PROMPTS]

            user_auth_id = SUPERUSER_ID
            if auth_header.startswith('Bearer '):
                raw_token = auth_header[7:].strip()
                resolved_env, resolved_user, _token_rec = _resolve_env(
                    raw_token, expected_audience=self._oauth_resource_value())
                if resolved_env is not None:
                    user_auth_id = resolved_user.id
            else:
                uid = request.session.uid
                if uid:
                    user_auth_id = uid

            try:
                templates = request.env['mcp.prompt.template'].get_prompts_for_user(user_auth_id)
                if templates:
                    pub = templates + pub
            except Exception as e:
                _logger.warning("Error fetching prompt templates: %s", e)
            return _ok(req_id, {"prompts": pub})

        if method == 'prompts/get':
            name = params.get('name') or ''
            args = params.get('arguments') or {}

            tpl = request.env['mcp.prompt.template'].sudo().search(
                [('name', '=', name), ('active', '=', True)], limit=1)
            if tpl:
                text = tpl.render_for(args)
                return _ok(req_id, {
                    "description": tpl.description,
                    "messages": [{"role": "user", "content": {"type": "text", "text": text}}]
                })

            prompt = next((p for p in MCP_PROMPTS if p['name'] == name), None)
            if not prompt:
                return _err(req_id, -32602, f"Prompt '{name}' not found")

            text = prompt['_text']
            for k, v in args.items():
                text = text.replace('{{' + k + '}}', str(v))
            return _ok(req_id, {
                "description": prompt['description'],
                "messages": [{"role": "user", "content": {"type": "text", "text": text}}]
            })

        if method == 'resources/list':
            return _ok(req_id, {"resources": MCP_RESOURCES})
        if method == 'resources/read':
            uri = params.get('uri', '')
            _logger.debug("MCP resources/read uri=%s", uri)
            return _ok(req_id, {
                "contents": [{"uri": uri, "mimeType": "text/plain", "text": _resource_content(uri)}]
            })

        try:
            if method == 'tools/call':
                rate_err = self._enforce_rate_limit(env, user, req_id, route_name='mcp_handle')
                if rate_err:
                    return rate_err
                if token_rec and token_rec.scope:
                    tool_name = (params.get('name') or '')
                    if not self._scope_allows_tool(token_rec, tool_name):
                        return _err(req_id, -32001, f"Token scope does not allow tool '{tool_name}'")
                return self._dispatch_tool(req_id, params, env, user)
            else:
                _logger.warning("MCP unknown method: %s", method)
                return _err(req_id, -32601, f"Method not found: {method}")
        except Exception as exc:
            tb_str = traceback.format_exc()
            _logger.error("MCP unhandled: %s", tb_str)
            _log(env, tool='', method=method, operation='protocol',
                 user=user, log_level='error', state='error',
                 error=exc, tb=tb_str, request_id=req_id)
            return _err(req_id, -32603, "Internal error", str(exc))

    def _handle_initialize(self, req_id, params):
        client = (params.get('clientInfo') or {})
        client_name = client.get('name', '?')
        client_ver  = client.get('version', '')
        _logger.info("MCP initialize: client=%s v%s", client_name, client_ver)

        # Log the initialization event
        try:
            env = request.env
            _log(env, method='initialize', operation='protocol',
                 log_level='info', request_id=req_id,
                 payload={'client': client_name, 'version': client_ver},
                 result_summary=f"Session started: {client_name} {client_ver}")
        except Exception:
            pass  # Don't fail initialization if logging fails

        system_prompt = next(
            (p['_text'] for p in MCP_PROMPTS if p['name'] == 'system'), ''
        )
        return _ok(req_id, {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "odoo-mcp-server", "version": "2.0.0"},
            "capabilities": {
                "tools": {"listChanged": False},
                "prompts": {"listChanged": True},
                "resources": {"listChanged": False},
            },
            "instructions": system_prompt,
        })

    def _dispatch_tool(self, req_id, params, env, user):
        tool_name = params.get('name') or ''
        _logger.info("MCP tools/call → %s  id=%s  user=%s",
                     tool_name, req_id, user.login if user else '?')
        tool_input = params.get('arguments') or params.get('input') or {}

        if tool_name not in TOOL_DISPATCH:
            _logger.warning("MCP unknown tool: %s", tool_name)
            return _err(req_id, -32602,
                        f"Unknown tool '{tool_name}'. "
                        f"Available: {', '.join(sorted(TOOL_DISPATCH.keys()))}")

        try:
            _mcp_sec.check_tool_allowed(env, user, tool_name)
        except PermissionError as e:
            _logger.warning("MCP security: tool %s blocked for %s — %s",
                            tool_name, user.login if user else '?', e)
            return _err(req_id, -32001, str(e))

        model_hint = tool_input.get('model', '')
        _logger.debug("MCP dispatch: tool=%s model=%s", tool_name, model_hint)
        if tool_name not in _mcp_sec.MODEL_RESTRICTION_EXCLUDED and model_hint:
            op_map = {
                'search_read': 'read', 'list_models': 'read', 'get_fields': 'read',
                'create': 'create', 'write': 'write', 'unlink': 'unlink', 'execute': 'execute'
            }
            check_op = op_map.get(TOOL_DISPATCH[tool_name][1], 'read')
            try:
                _mcp_sec.check_model_restriction(env, user, model_hint, check_op)
            except PermissionError as e:
                _logger.warning("MCP security: model %s/%s blocked — %s",
                                model_hint, check_op, e)
                return _err(req_id, -32001, str(e))

        # ── Inject relevant prompt text into every tool response ──────────────
        _TOOL_PROMPT_MAP = {
            'odoo_email_template':     'create_email_template',
            'odoo_manage_echart':      'create_echart',
            'odoo_manage_webapp':      'create_webapp',
            'odoo_manage_snippet':     'create_snippet',
            'odoo_manage_report':      'create_report',
            'odoo_search_read':        'query_data',
            'odoo_aggregate':          'query_data',
            'odoo_read_group':         'query_data',
            'odoo_execute_orm':        'query_data',
            'odoo_add_custom_field':   'add_field',
            'odoo_create':             'bulk_crud',
            'odoo_write':              'bulk_crud',
            'odoo_unlink':             'bulk_crud',
            'odoo_import_data':        'import_data',
        }

        prompt_name = _TOOL_PROMPT_MAP.get(tool_name)
        injected_prompt = ''
        if prompt_name:
            injected_prompt = next(
                (p['_text'] for p in MCP_PROMPTS if p['name'] == prompt_name),
                ''
            )

        # ── Action-aware injection for odoo_manage_module ────────────────────
        if tool_name == 'odoo_manage_module':
            module_action = tool_input.get('action', 'create')
            if module_action == 'create':
                injected_prompt = next(
                    (p['_text'] for p in MCP_PROMPTS if p['name'] == 'create_module'),
                    ''
                )
                _logger.debug("MCP module action=create → full prompt injected")
            else:
                injected_prompt = _PROMPT_MODULE_INSTALL_HINT
                _logger.debug("MCP module action=%s → short hint injected", module_action)

        _logger.debug("MCP prompt injection: %d chars", len(injected_prompt))
        fn, operation = TOOL_DISPATCH[tool_name]
        start = time.monotonic()

        try:
            # Pass user to tool functions that support field-level restrictions
            try:
                result = fn(env, tool_input, user=user)
            except TypeError:
                result = fn(env, tool_input)
            duration_ms = round((time.monotonic() - start) * 1000)

            # Compute response size for monitoring
            result_json = json.dumps(result, default=str)
            resp_size = len(result_json.encode('utf-8'))

            _logger.info("MCP ✓ %s  %dms  %d bytes", tool_name, duration_ms, resp_size)
            _log(env, tool=tool_name, model=model_hint, operation=operation,
                 user=user, payload=tool_input, result_summary=result,
                 duration_ms=duration_ms, method='tools/call',
                 request_id=req_id, log_level='info',
                 response_size=resp_size)

            # Build content array — prepend injected prompt so LLM reads rules
            # first, then reads the tool result.
            content = []
            if injected_prompt:
                content.append({
                    "type": "text",
                    "text": injected_prompt,
                })
            content.append({
                "type": "text",
                "text": result_json,
            })

            return _ok(req_id, {"content": content})

        except (ValueError, PermissionError) as exc:
            duration_ms = round((time.monotonic() - start) * 1000)
            _logger.warning("MCP ✗ %s  %dms  %s: %s",
                            tool_name, duration_ms, type(exc).__name__, exc)
            _log(env, tool=tool_name, model=model_hint, operation=operation,
                 user=user, payload=tool_input, result_summary=None,
                 state='error', error=exc, duration_ms=duration_ms,
                 method='tools/call', request_id=req_id,
                 log_level='warning')
            msg = str(exc)
            if isinstance(exc, PermissionError) and 'WRONG TOOL' in msg:
                data = {"tool_name": tool_name}
                if 'odoo_import_data' in msg:
                    data["required_tool"] = 'odoo_import_data'
                elif 'odoo_email_template' in msg:
                    data["required_tool"] = 'odoo_email_template'
                return _err(req_id, -32002, msg, data)
            return _ok(req_id, {
                "content": [{"type": "text", "text": f"Error: {msg}"}],
                "isError": True,
            })

        except Exception as exc:
            duration_ms = round((time.monotonic() - start) * 1000)
            tb_str = traceback.format_exc()
            _logger.error("MCP ✗ %s  %dms  UNHANDLED:\n%s",
                          tool_name, duration_ms, tb_str)
            _log(env, tool=tool_name, model=model_hint, operation=operation,
                 user=user, payload=tool_input, result_summary=None,
                 state='error', error=exc, duration_ms=duration_ms,
                 method='tools/call', request_id=req_id,
                 log_level='error', tb=tb_str)
            return _ok(req_id, {
                "content": [{"type": "text", "text": f"Unexpected error: {exc}"}],
                "isError": True,
            })

    # =========================================================================
    # Claude Desktop — Bearer-token auth endpoint 99999999999999999999999
    #
    # Validates the token in claude_desktop_config.json against mcp.api.token
    # (active=True, mcp_client='claude_desktop'), then re-uses the existing
    # _handle_initialize / _dispatch_tool pipeline so ALL MCP tools work.
    #
    # Config snippet:
    #   {
    #     "mcpServers": {
    #       "odoo": {
    #         "type": "http",
    #         "url": "<base_url>/claude_desktop/auth",
    #         "headers": { "Authorization": "Bearer <token>" }
    #       }
    #     }
    #   }444444444444444444444444444444
    # =========================================================================
    def _cd_resolve_token(self):
        """
        Extract and validate the Bearer token for Claude Desktop.

        Returns (env, user, error_response).
        If error_response is not None, return it immediately.
        """
        auth = request.httprequest.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return None, None, _json_response(
                {'error': {'code': 401, 'message': 'Missing Authorization header.'}}, 401)

        cfg = request.env['mcp.config'].sudo().get_config()
        ip_err = self._enforce_ip_policy(cfg, route_name='claude_desktop_auth')
        if ip_err:
            return None, None, ip_err

        raw_token = auth[7:].strip()
        Token = request.env['mcp.api.token'].sudo()
        rec = Token.resolve_access_token(raw_token)
        if rec and rec.mcp_client != 'claude_desktop':
            rec = Token.browse()

        if not rec:
            _logger.warning(
                "Claude Desktop: unknown/inactive token (prefix=%s…)", raw_token[:8])
            return None, None, _json_response(
                {'error': {'code': 403, 'message': 'Invalid or inactive Claude Desktop token.'}}, 403)

        env = request.env(user=rec.user_id.id)
        user = rec.user_id
        _logger.info("Claude Desktop: authenticated as %s (uid=%s)", user.name, user.id)
        return env, user, None

    def _cd_server_info(self, user):
        """Return server capabilities for GET / initialize requests."""
        base_url = request.env['ir.config_parameter'].sudo().get_str('web.base.url', '')
        return {
            'protocolVersion': '2024-11-05',
            'serverInfo': {'name': 'Odoo MCP Server', 'version': '2.0.0'},
            'capabilities': {
                'tools': {'listChanged': False},
                'prompts': {'listChanged': True},
                'resources': {'listChanged': False},
            },
            'auth': {
                'status': 'authenticated',
                'user': user.name,
                'uid': user.id,
                'base_url': base_url,
            },
        }

    @http.route(
        '/claude_desktop/auth',
        type='http',
        auth='none',
        methods=['GET', 'POST', 'OPTIONS'],
        csrf=False,
        save_session=False,
    )
    def claude_desktop_auth(self, **kwargs):
        """
        Single endpoint consumed by Claude Desktop via claude_desktop_config.json.

        GET  — capability handshake / health check (no body required)
        POST — JSON-RPC 2.0 message dispatch (initialize, tools/list, tools/call, …)
        OPTIONS — CORS pre-flight
        """
        method = request.httprequest.method

        if method == 'OPTIONS':
            return Response('', status=204, headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
            })

        env, user, err = self._cd_resolve_token()
        if err:
            return err

        if method == 'GET':
            return _json_response(self._cd_server_info(user))

        try:
            raw = request.httprequest.data or b'{}'
            body = json.loads(raw)
        except Exception:
            return _err(None, -32700, 'Parse error: invalid JSON')

        if isinstance(body, list):
            return _json_response([self._cd_dispatch(item, env, user) for item in body])

        return _json_response(self._cd_dispatch(body, env, user))

    def _cd_dispatch(self, body, env, user):
        """
        Route a single JSON-RPC 2.0 request through the existing MCP pipeline.
        Returns a plain dict (caller wraps it in _json_response).
        """
        req_id = body.get('id')
        method = body.get('method', '')
        params = body.get('params') or {}

        _logger.debug("Claude Desktop ← method=%s id=%s user=%s", method, req_id, user.name)

        # ── MCP handshake ────────────────────────────────────────────────────
        if method == 'initialize':
            result = self._cd_server_info(user)
            return {'jsonrpc': '2.0', 'id': req_id, 'result': result}

        if method in ('notifications/initialized', 'ping'):
            return {'jsonrpc': '2.0', 'id': req_id, 'result': {}}

        # ── Tool listing ─────────────────────────────────────────────────────
        if method == 'tools/list':
            visible_tools = self._visible_tools(env, user, client_name='claude_desktop')
            return {'jsonrpc': '2.0', 'id': req_id, 'result': {'tools': visible_tools}}

        # ── Prompt listing ───────────────────────────────────────────────────
        if method == 'prompts/list':
            pub = [{k: v for k, v in p.items() if k != '_text'} for p in MCP_PROMPTS]
            return {'jsonrpc': '2.0', 'id': req_id, 'result': {'prompts': pub}}

        if method == 'prompts/get':
            name = params.get('name') or ''
            args = params.get('arguments') or {}
            prompt = next((p for p in MCP_PROMPTS if p['name'] == name), None)
            if not prompt:
                return {'jsonrpc': '2.0', 'id': req_id,
                        'error': {'code': -32602, 'message': f"Prompt '{name}' not found"}}
            text = prompt['_text']
            for k, v in args.items():
                text = text.replace('{{' + k + '}}', str(v))
            return {'jsonrpc': '2.0', 'id': req_id, 'result': {
                'description': prompt['description'],
                'messages': [{'role': 'user', 'content': {'type': 'text', 'text': text}}],
            }}

        # ── Resources ────────────────────────────────────────────────────────
        if method == 'resources/list':
            return {'jsonrpc': '2.0', 'id': req_id, 'result': {'resources': MCP_RESOURCES}}

        if method == 'resources/read':
            uri = params.get('uri', '')
            return {'jsonrpc': '2.0', 'id': req_id, 'result': {
                'contents': [{'uri': uri, 'mimeType': 'text/plain',
                              'text': _resource_content(uri)}]
            }}

        # ── Tool execution — re-use existing _dispatch_tool ───────────────────
        if method == 'tools/call':
            rate_err = self._enforce_rate_limit(env, user, req_id, route_name='claude_desktop_auth')
            if rate_err:
                return json.loads(rate_err.data)
            # _dispatch_tool returns a Response; extract the JSON body as a dict
            resp = self._dispatch_tool(req_id, params, env, user)
            try:
                return json.loads(resp.data)
            except Exception:
                _logger.warning("Claude Desktop dispatch decode failed")
                _log(env, tool='', method='tools/call', operation='protocol',
                     log_level='error', state='error',
                     error='Internal dispatch decode error',
                     payload={'source': 'claude_desktop'})
                return {'jsonrpc': '2.0', 'id': req_id,
                        'error': {'code': -32603, 'message': 'Internal dispatch error'}}

        return {'jsonrpc': '2.0', 'id': req_id,
                'error': {'code': -32601, 'message': f'Method not found: {method}'}}

    # =========================================================================
    # Gemini CLI  (/gemini_cli/auth)
    # =========================================================================
    # Validates the token stored in mcp.api.token (mcp_client='gemini_cli')
    # and re-uses the existing MCP pipeline so ALL tools work identically.
    #
    # gemini mcp add command:
    #   gemini mcp add odoo \
    #     --transport http \
    #     --url <base_url>/gemini_cli/auth \
    #     --header "Authorization: Bearer <token>"
    #
    # Or via ~/.gemini/settings.json:
    #   {
    #     "mcpServers": {
    #       "odoo": {
    #         "httpUrl": "<base_url>/gemini_cli/auth",
    #         "headers": { "Authorization": "Bearer <token>" }
    #       }
    #     }
    #   }
    # =========================================================================

    def _gc_resolve_token(self):
        """
        Extract and validate the Bearer token for Gemini CLI.

        Returns (env, user, error_response).
        If error_response is not None, return it immediately.
        """
        auth = request.httprequest.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return None, None, _json_response(
                {'error': {'code': 401, 'message': 'Missing Authorization header. '
                           'Pass: Authorization: Bearer <token>'}}, 401)

        cfg = request.env['mcp.config'].sudo().get_config()
        ip_err = self._enforce_ip_policy(cfg, route_name='gemini_cli_auth')
        if ip_err:
            return None, None, ip_err

        raw_token = auth[7:].strip()
        Token = request.env['mcp.api.token'].sudo()
        rec = Token.resolve_access_token(raw_token)
        if rec and rec.mcp_client != 'gemini_cli':
            rec = Token.browse()

        if not rec:
            _logger.warning(
                "Gemini CLI: unknown/inactive token (prefix=%s…)", raw_token[:8])
            return None, None, _json_response(
                {'error': {'code': 403,
                           'message': 'Invalid or inactive Gemini CLI token.'}}, 403)

        env = request.env(user=rec.user_id.id)
        user = rec.user_id
        _logger.info("Gemini CLI: authenticated as %s (uid=%s)", user.name, user.id)
        return env, user, None

    def _gc_server_info(self, user):
        """Return MCP server capabilities for Gemini CLI."""
        base_url = request.env['ir.config_parameter'].sudo().get_str('web.base.url', '')
        return {
            'protocolVersion': '2024-11-05',
            'serverInfo': {'name': 'Odoo MCP Server', 'version': '2.0.0'},
            'capabilities': {
                'tools': {'listChanged': False},
                'prompts': {'listChanged': False},
                'resources': {'listChanged': False},
            },
            'auth': {
                'status': 'authenticated',
                'user': user.name,
                'uid': user.id,
                'base_url': base_url,
                'client': 'gemini_cli',
            },
        }

    @http.route(
        '/gemini_cli/auth',
        type='http',
        auth='none',
        methods=['GET', 'POST', 'OPTIONS'],
        csrf=False,
        save_session=False,
    )
    def gemini_cli_auth(self, **kwargs):
        """
        Single endpoint consumed by Gemini CLI.

        GET  — capability handshake / health check
        POST — JSON-RPC 2.0 message dispatch (initialize, tools/list, tools/call, …)
        OPTIONS — CORS pre-flight
        """
        method = request.httprequest.method

        # ── CORS pre-flight ──────────────────────────────────────────────────
        if method == 'OPTIONS':
            return Response('', status=204, headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Authorization, Content-Type',
            })

        # ── Authenticate ────────────────────────────────────────────────────
        env, user, err = self._gc_resolve_token()
        if err:
            return err

        # ── GET: server-info / capability handshake ──────────────────────────
        if method == 'GET':
            return _json_response(self._gc_server_info(user))

        # ── POST: JSON-RPC 2.0 ───────────────────────────────────────────────
        try:
            raw = request.httprequest.data or b'{}'
            body = json.loads(raw)
        except Exception:
            return _err(None, -32700, 'Parse error: invalid JSON')

        # Support JSON-RPC batch (list of requests)
        if isinstance(body, list):
            return _json_response(
                [self._gc_dispatch(item, env, user) for item in body])

        return _json_response(self._gc_dispatch(body, env, user))

    def _gc_dispatch(self, body, env, user):
        """
        Route a single JSON-RPC 2.0 request through the existing MCP pipeline.
        Returns a plain dict (caller wraps it in _json_response).
        """
        req_id = body.get('id')
        method = body.get('method', '')
        params = body.get('params') or {}

        _logger.debug("Gemini CLI ← method=%s id=%s user=%s", method, req_id, user.name)

        # ── MCP handshake ────────────────────────────────────────────────────
        if method == 'initialize':
            result = self._gc_server_info(user)
            return {'jsonrpc': '2.0', 'id': req_id, 'result': result}

        if method in ('notifications/initialized', 'ping'):
            return {'jsonrpc': '2.0', 'id': req_id, 'result': {}}

        # ── Tool listing ─────────────────────────────────────────────────────
        if method == 'tools/list':
            visible_tools = self._visible_tools(env, user, client_name='gemini_cli')
            return {'jsonrpc': '2.0', 'id': req_id, 'result': {'tools': visible_tools}}

        # ── Prompt listing ───────────────────────────────────────────────────
        if method == 'prompts/list':
            pub = [{k: v for k, v in p.items() if k != '_text'} for p in MCP_PROMPTS]
            return {'jsonrpc': '2.0', 'id': req_id, 'result': {'prompts': pub}}

        if method == 'prompts/get':
            name = params.get('name') or ''
            args = params.get('arguments') or {}
            prompt = next((p for p in MCP_PROMPTS if p['name'] == name), None)
            if not prompt:
                return {'jsonrpc': '2.0', 'id': req_id,
                        'error': {'code': -32602,
                                  'message': f"Prompt '{name}' not found"}}
            text = prompt['_text']
            for k, v in args.items():
                text = text.replace('{{' + k + '}}', str(v))
            return {'jsonrpc': '2.0', 'id': req_id, 'result': {
                'description': prompt['description'],
                'messages': [{'role': 'user',
                              'content': {'type': 'text', 'text': text}}],
            }}

        # ── Resources ────────────────────────────────────────────────────────
        if method == 'resources/list':
            return {'jsonrpc': '2.0', 'id': req_id,
                    'result': {'resources': MCP_RESOURCES}}

        if method == 'resources/read':
            uri = params.get('uri', '')
            return {'jsonrpc': '2.0', 'id': req_id, 'result': {
                'contents': [{'uri': uri, 'mimeType': 'text/plain',
                              'text': _resource_content(uri)}]
            }}

        # ── Tool execution — re-use existing _dispatch_tool ───────────────────
        if method == 'tools/call':
            rate_err = self._enforce_rate_limit(env, user, req_id, route_name='gemini_cli_auth')
            if rate_err:
                return json.loads(rate_err.data)
            resp = self._dispatch_tool(req_id, params, env, user)
            try:
                return json.loads(resp.data)
            except Exception:
                _logger.warning("Gemini CLI dispatch decode failed")
                _log(env, tool='', method='tools/call', operation='protocol',
                     log_level='error', state='error',
                     error='Internal dispatch decode error',
                     payload={'source': 'gemini_cli'})
                return {'jsonrpc': '2.0', 'id': req_id,
                        'error': {'code': -32603,
                                  'message': 'Internal dispatch error'}}

        return {'jsonrpc': '2.0', 'id': req_id,
                'error': {'code': -32601,
                          'message': f'Method not found: {method}'}}

    # ── EChart HTML builder & routes ──────────────────────────────────────

    def _build_echart_html(self, chart, embed=False, data_url=''):
        static_raw = (chart.echart_option or '').strip()
        opt_parsed = {}

        def _parse_rgb(value):
            if not isinstance(value, str):
                return None
            color = value.strip().lower()
            if not color:
                return None
            if color.startswith('#'):
                hex_color = color[1:]
                if len(hex_color) == 3:
                    hex_color = ''.join(ch * 2 for ch in hex_color)
                if len(hex_color) == 6:
                    try:
                        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
                    except ValueError:
                        return None
            if color.startswith('rgb(') and color.endswith(')'):
                try:
                    parts = [int(part.strip()) for part in color[4:-1].split(',')[:3]]
                    if len(parts) == 3:
                        return tuple(parts)
                except ValueError:
                    return None
            return None

        def _is_light_background(value):
            rgb = _parse_rgb(value)
            if not rgb:
                return False
            brightness = (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000
            return brightness >= 180

        def _harmonize_option_theme(option):
            if not isinstance(option, dict):
                return option
            is_light = _is_light_background(option.get('backgroundColor'))
            if is_light:
                replace_palette = {'#f1f5f9', '#e2e8f0', '#cbd5e1', '#94a3b8', '#ffffff', '#fff'}
                strong_text = '#0f172a'
                normal_text = '#334155'
                muted_text = '#475569'
                line_text = '#cbd5e1'
            else:
                replace_palette = {
                    '#000', '#000000', '#111', '#111111', '#222', '#222222',
                    '#333', '#333333', '#444', '#444444', '#555', '#555555',
                    '#666', '#666666', '#111827', '#1f2937', '#374151',
                }
                strong_text = '#f8fafc'
                normal_text = '#e2e8f0'
                muted_text = '#cbd5e1'
                line_text = '#334155'

            def _set_color(container, key, preferred):
                if not isinstance(container, dict):
                    return
                current = container.get(key)
                if current is None:
                    container[key] = preferred
                    return
                if isinstance(current, str) and current.strip().lower() in replace_palette:
                    container[key] = preferred

            def _normalize_text_style(container, preferred):
                if not isinstance(container, dict):
                    return
                style = container.get('textStyle')
                if not isinstance(style, dict):
                    style = {}
                    container['textStyle'] = style
                _set_color(style, 'color', preferred)

            def _normalize_axis(axis_obj):
                axes = axis_obj if isinstance(axis_obj, list) else [axis_obj]
                for axis in axes:
                    if not isinstance(axis, dict):
                        continue
                    axis_label = axis.get('axisLabel')
                    if not isinstance(axis_label, dict):
                        axis_label = {}
                        axis['axisLabel'] = axis_label
                    _set_color(axis_label, 'color', normal_text)

                    name_style = axis.get('nameTextStyle')
                    if not isinstance(name_style, dict):
                        name_style = {}
                        axis['nameTextStyle'] = name_style
                    _set_color(name_style, 'color', normal_text)

                    split_line = axis.get('splitLine')
                    if isinstance(split_line, dict):
                        line_style = split_line.get('lineStyle')
                        if not isinstance(line_style, dict):
                            line_style = {}
                            split_line['lineStyle'] = line_style
                        _set_color(line_style, 'color', line_text)

            _normalize_text_style(option.get('title'), strong_text)
            legends = option.get('legend')
            if isinstance(legends, list):
                for legend in legends:
                    _normalize_text_style(legend, normal_text)
            else:
                _normalize_text_style(legends, normal_text)

            visual_maps = option.get('visualMap')
            if isinstance(visual_maps, list):
                for visual_map in visual_maps:
                    _normalize_text_style(visual_map, normal_text)
            else:
                _normalize_text_style(visual_maps, normal_text)

            _normalize_axis(option.get('xAxis'))
            _normalize_axis(option.get('yAxis'))
            _normalize_axis(option.get('singleAxis'))

            radar = option.get('radar')
            if isinstance(radar, dict):
                name_style = radar.get('name')
                if not isinstance(name_style, dict):
                    name_style = {}
                    radar['name'] = name_style
                _set_color(name_style, 'color', normal_text)

            for series in option.get('series', []):
                if not isinstance(series, dict):
                    continue
                label = series.get('label')
                if not isinstance(label, dict):
                    label = {}
                    series['label'] = label
                _set_color(label, 'color', normal_text)

                upper_label = series.get('upperLabel')
                if not isinstance(upper_label, dict):
                    upper_label = {}
                    series['upperLabel'] = upper_label
                _set_color(upper_label, 'color', normal_text)

                detail = series.get('detail')
                if not isinstance(detail, dict):
                    detail = {}
                    series['detail'] = detail
                _set_color(detail, 'color', strong_text)

                axis_label = series.get('axisLabel')
                if not isinstance(axis_label, dict):
                    axis_label = {}
                    series['axisLabel'] = axis_label
                _set_color(axis_label, 'color', muted_text)

            return option

        def _normalize_dashboard_layout(option):
            if not isinstance(option, dict):
                return option

            raw_series = option.get('series')
            if not isinstance(raw_series, list):
                return option

            component_counts = []
            for key in ('grid', 'xAxis', 'yAxis', 'title', 'legend', 'visualMap', 'geo', 'radar'):
                value = option.get(key)
                if isinstance(value, list):
                    component_counts.append(len(value))

            series_meta = []
            for idx, series in enumerate(raw_series):
                if not isinstance(series, dict):
                    continue
                series_type = (series.get('type') or '').strip().lower()
                if not series_type:
                    continue
                series_meta.append((idx, series_type, series))

            unique_types = {series_type for _, series_type, _ in series_meta}
            is_dashboard = (
                chart.chart_type == 'custom'
                or len(unique_types) > 1
                or max(component_counts or [1]) > 1
            )
            if not is_dashboard:
                return option

            cartesian_types = {'bar', 'line', 'scatter', 'heatmap'}
            center_types = {'pie', 'gauge', 'radar', 'sunburst'}

            def _parse_percent(value):
                if isinstance(value, (int, float)):
                    return float(value)
                if isinstance(value, str):
                    text = value.strip()
                    if text.endswith('%'):
                        text = text[:-1].strip()
                    try:
                        return float(text)
                    except (TypeError, ValueError):
                        return None
                return None

            def _is_default_center(center):
                if not center:
                    return True
                if isinstance(center, list) and len(center) == 2:
                    left = _parse_percent(center[0])
                    top = _parse_percent(center[1])
                    if left is None or top is None:
                        return False
                    return abs(left - 50.0) < 0.01 and abs(top - 50.0) < 0.01
                return False

            def _panel_box(pos, total):
                cols = 1 if total <= 1 else 2
                rows = (total + cols - 1) // cols
                row, col = divmod(pos, cols)
                left = 8 if col == 0 else 54
                width = 38 if cols == 2 else 84
                row_gap = 10
                available = 78 - (rows - 1) * row_gap
                height = max(18, int(available / max(rows, 1)))
                top = 14 + row * (height + row_gap)
                return {
                    'left': f'{left}%',
                    'top': f'{top}%',
                    'width': f'{width}%',
                    'height': f'{height}%',
                    'center': [f'{left + (width / 2):.1f}%', f'{top + (height / 2):.1f}%'],
                }

            def _center_point(series):
                center = series.get('center')
                if not isinstance(center, list) or len(center) != 2:
                    return None
                left = _parse_percent(center[0])
                top = _parse_percent(center[1])
                if left is None or top is None:
                    return None
                return (left, top)

            def _outer_radius(series):
                radius = series.get('radius')
                if isinstance(radius, list) and len(radius) >= 2:
                    return _parse_percent(radius[1]) or 28.0
                if radius is not None:
                    return _parse_percent(radius) or 28.0
                series_type = (series.get('type') or '').strip().lower()
                if series_type == 'gauge':
                    return 30.0
                if series_type == 'radar':
                    return 26.0
                return 28.0

            cartesian = [(idx, series) for idx, series_type, series in series_meta if series_type in cartesian_types]
            if cartesian:
                grid_list = option.get('grid')
                if isinstance(grid_list, dict):
                    grid_list = [dict(grid_list) for _ in range(len(cartesian))]
                elif isinstance(grid_list, list):
                    grid_list = [dict(item) if isinstance(item, dict) else {} for item in grid_list]
                else:
                    grid_list = []
                while len(grid_list) < len(cartesian):
                    grid_list.append({})
                option['grid'] = grid_list

                x_axes = option.get('xAxis')
                if isinstance(x_axes, dict):
                    x_axes = [dict(x_axes) for _ in range(len(cartesian))]
                elif isinstance(x_axes, list):
                    x_axes = [dict(item) if isinstance(item, dict) else {} for item in x_axes]
                else:
                    x_axes = [{} for _ in range(len(cartesian))]
                while len(x_axes) < len(cartesian):
                    x_axes.append({})

                y_axes = option.get('yAxis')
                if isinstance(y_axes, dict):
                    y_axes = [dict(y_axes) for _ in range(len(cartesian))]
                elif isinstance(y_axes, list):
                    y_axes = [dict(item) if isinstance(item, dict) else {} for item in y_axes]
                else:
                    y_axes = [{} for _ in range(len(cartesian))]
                while len(y_axes) < len(cartesian):
                    y_axes.append({})

                for pos, (series_idx, series) in enumerate(cartesian):
                    box = _panel_box(pos, len(cartesian))
                    grid = grid_list[pos]
                    for key in ('left', 'top', 'width', 'height'):
                        grid.setdefault(key, box[key])
                    x_axes[pos].setdefault('gridIndex', pos)
                    y_axes[pos].setdefault('gridIndex', pos)
                    series.setdefault('xAxisIndex', pos)
                    series.setdefault('yAxisIndex', pos)

                option['xAxis'] = x_axes
                option['yAxis'] = y_axes

            center_based = [(idx, series) for idx, series_type, series in series_meta if series_type in center_types]
            if center_based:
                titles = option.get('title')
                title_slots = []
                if isinstance(titles, list):
                    for pos, title in enumerate(titles):
                        if not isinstance(title, dict):
                            continue
                        box = _panel_box(pos, max(len(titles), len(center_based)))
                        left = _parse_percent(title.get('left'))
                        top = _parse_percent(title.get('top'))
                        slot = dict(box)
                        if left is not None:
                            slot['center'][0] = f'{left:.1f}%'
                        if top is not None:
                            adjusted_top = min(max(top + 12.0, 18.0), 86.0)
                            slot['center'][1] = f'{adjusted_top:.1f}%'
                        title_slots.append(slot)
                if not title_slots:
                    title_slots = [_panel_box(pos, len(center_based)) for pos in range(len(center_based))]

                overlap_detected = False
                for pos, (_, series) in enumerate(center_based):
                    point_a = _center_point(series)
                    if point_a is None:
                        continue
                    radius_a = _outer_radius(series)
                    for _, other_series in center_based[pos + 1:]:
                        point_b = _center_point(other_series)
                        if point_b is None:
                            continue
                        radius_b = _outer_radius(other_series)
                        dx = point_a[0] - point_b[0]
                        dy = point_a[1] - point_b[1]
                        distance = (dx * dx + dy * dy) ** 0.5
                        if distance < max((radius_a + radius_b) * 0.72, 18.0):
                            overlap_detected = True
                            break
                    if overlap_detected:
                        break

                for pos, (_, series) in enumerate(center_based):
                    if not _is_default_center(series.get('center')) and not overlap_detected:
                        continue
                    slot = title_slots[pos] if pos < len(title_slots) else _panel_box(pos, len(center_based))
                    series['center'] = slot['center']
                    series_type = (series.get('type') or '').strip().lower()
                    if overlap_detected or 'radius' not in series:
                        if series_type == 'gauge':
                            series['radius'] = '38%'
                        elif series_type == 'radar':
                            series['radius'] = '28%'
                        else:
                            series['radius'] = ['14%', '28%'] if series_type == 'pie' else '28%'

            titles = option.get('title')
            if isinstance(titles, list) and titles:
                for pos, title in enumerate(titles):
                    if not isinstance(title, dict):
                        continue
                    box = _panel_box(pos, len(titles))
                    title.setdefault('left', box['left'])
                    title.setdefault('top', box['top'])

            return option

        raw_option_js = 'null'
        try:
            opt_parsed = json.loads(static_raw)
            opt_parsed = _harmonize_option_theme(opt_parsed)
            opt_parsed = _normalize_dashboard_layout(opt_parsed)
            static_str = json.dumps(opt_parsed)
        except (json.JSONDecodeError, ValueError):
            raw_option_js = json.dumps(static_raw) if (static_raw or '').strip() else 'null'
            static_str = json.dumps({"title": {"text": chart.name}, "series": []})
        try:
            json.loads(static_str)
        except json.JSONDecodeError:
            static_str = json.dumps({"title": {"text": chart.name}, "series": []})

        name        = (chart.name or '').replace('<', '&lt;').replace('>', '&gt;')
        desc        = (chart.description or '').replace('<', '&lt;').replace('>', '&gt;')
        has_data    = bool(chart.data_code and chart.data_code.strip())
        slug        = chart.slug
        data_url    = data_url or f"/mcp/echart/{slug}/data"
        pre_js      = (chart.pre_init_js or '').replace('</script>', '<\\/script>')
        post_js     = (chart.post_init_js or '').replace('</script>', '<\\/script>')
        needs_chartjs = 'true' if (
            'chart.js' in (chart.pre_init_js or '').lower()
            or 'chart.js' in (chart.post_init_js or '').lower()
            or 'new Chart' in (chart.pre_init_js or '')
            or 'new Chart' in (chart.post_init_js or '')
            or 'typeof Chart' in (chart.pre_init_js or '')
            or 'typeof Chart' in (chart.post_init_js or '')
        ) else 'false'
        badge_cls   = "live" if has_data else "static"
        badge_text  = "&#9679; Live" if has_data else "Static"
        desc_html   = f'<span class="desc">{desc}</span>' if desc else ''
        hdr_style   = 'display:none' if embed else ''
        has_data_js = 'true' if has_data else 'false'

        layout_meta = opt_parsed.get('mcp_layout') if isinstance(opt_parsed, dict) else {}
        if not isinstance(layout_meta, dict):
            layout_meta = {}

        series = opt_parsed.get('series', []) if isinstance(opt_parsed, dict) else []
        series_types = {
            (item.get('type') or '').strip().lower()
            for item in series
            if isinstance(item, dict) and item.get('type')
        }
        component_counts = []
        for key in ('grid', 'xAxis', 'yAxis', 'title', 'legend', 'visualMap', 'geo', 'radar'):
            value = opt_parsed.get(key) if isinstance(opt_parsed, dict) else None
            if isinstance(value, list):
                component_counts.append(len(value))
        panel_count = max(component_counts or [1])
        if len(series_types) > 1:
            panel_count = max(panel_count, len(series_types))
        if len(series) > 4:
            panel_count = max(panel_count, (len(series) + 1) // 2)

        inferred_dashboard = (
            chart.chart_type == 'custom'
            or len(series_types) > 1
            or panel_count > 1
        )
        default_min_height = 720
        if inferred_dashboard:
            default_min_height = max(default_min_height, 420 * max(panel_count, 2))
        if embed:
            default_min_height = max(540, min(default_min_height, 1400))

        layout_min_height = layout_meta.get('minHeight')
        layout_mobile_min_height = layout_meta.get('mobileMinHeight')
        layout_min_width = layout_meta.get('minWidth')

        def _parse_layout_int(value, default):
            if value is None:
                return default
            if isinstance(value, str):
                text = value.strip().lower()
                if text.endswith('px'):
                    text = text[:-2].strip()
                try:
                    return int(float(text))
                except (TypeError, ValueError):
                    return default
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        layout_min_height = _parse_layout_int(layout_min_height, default_min_height)
        layout_mobile_min_height = _parse_layout_int(
            layout_mobile_min_height,
            max(layout_min_height, 960 if inferred_dashboard else 640),
        )
        layout_min_width = _parse_layout_int(
            layout_min_width,
            1280 if inferred_dashboard else 0,
        )

        needed_maps = []
        _seen = set()
        def _reg(n):
            n = (n or 'world').strip().lower()
            if n and n not in _seen:
                _seen.add(n); needed_maps.append(n)
        for s in opt_parsed.get('series', []):
            if isinstance(s, dict) and s.get('type') == 'map':
                _reg(s.get('map', 'world'))
        geo = opt_parsed.get('geo')
        if isinstance(geo, dict): _reg(geo.get('map', 'world'))
        elif isinstance(geo, list):
            for g in geo:
                if isinstance(g, dict): _reg(g.get('map', 'world'))

        _cdn = {
            'world': ['https://cdn.jsdelivr.net/gh/apache/echarts@5.5.1/test/data/map/json/world.json',
                      'https://cdn.jsdelivr.net/npm/echarts/map/json/world.json',
                      'https://raw.githubusercontent.com/apache/echarts/5.5.1/test/data/map/json/world.json'],
            'china': ['https://cdn.jsdelivr.net/gh/apache/echarts@5.5.1/test/data/map/json/china.json',
                      'https://cdn.jsdelivr.net/npm/echarts/map/json/china.json',
                      'https://raw.githubusercontent.com/apache/echarts/5.5.1/test/data/map/json/china.json'],
        }
        map_sources = {nm: _cdn.get(nm, [f'https://cdn.jsdelivr.net/gh/apache/echarts@5.5.1/test/data/map/json/{nm}.json'])
                       for nm in needed_maps}
        cdn_urls = [
            "https://cdnjs.cloudflare.com/ajax/libs/echarts/5.5.1/echarts.min.js",
            "https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js",
            "https://unpkg.com/echarts@5.5.1/dist/echarts.min.js",
        ]
        needed_maps_json = json.dumps(needed_maps)
        map_sources_json = json.dumps(map_sources)
        cdn_json         = json.dumps(cdn_urls)

        return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:100%;min-height:100%;overflow:auto}}
body{{background:#0f172a;color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:flex;flex-direction:column;min-height:100vh;overflow:auto}}
#hdr{{flex-shrink:0;padding:12px 24px;background:linear-gradient(135deg,#1e293b 0%,#0f172a 100%);border-bottom:1px solid #334155;display:flex;align-items:center;gap:12px;flex-wrap:wrap;{hdr_style}}}
#hdr h1{{font-size:17px;font-weight:700;flex:1;letter-spacing:-0.01em}}
.desc{{font-size:12px;color:#94a3b8;max-width:400px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.badge{{font-size:10px;padding:3px 10px;border-radius:9999px;color:#fff;font-weight:600;letter-spacing:0.03em;text-transform:uppercase}}
.live{{background:linear-gradient(135deg,#0ea5e9,#06b6d4)}}.static{{background:#475569}}
.btn{{cursor:pointer;padding:5px 14px;border-radius:6px;border:1px solid #475569;background:transparent;color:#94a3b8;font-size:12px;font-weight:500;transition:all .2s ease}}
.btn:hover{{background:#334155;color:#f1f5f9;border-color:#64748b}}.btn:disabled{{opacity:.5;cursor:default}}
#shell{{flex:1;position:relative;overflow:auto;-webkit-overflow-scrolling:touch}}
#wrap{{position:relative;min-height:{layout_min_height}px;padding-bottom:16px}}
#chart{{width:100%;height:{layout_min_height}px;min-height:{layout_min_height}px}}
#mcp-overlay-root{{position:absolute;inset:0;pointer-events:none;z-index:4}}
#mcp-echart-root{{display:none;position:relative;width:100%;min-height:{layout_min_height}px;z-index:2}}
.mcp-overlay-node{{position:absolute;pointer-events:none;z-index:4}}
#ov{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;background:rgba(15,23,42,.92);gap:14px;z-index:10;transition:opacity .3s ease}}
#ov.hidden{{opacity:0;pointer-events:none}}
.spin{{width:36px;height:36px;border:3px solid #334155;border-top-color:#38bdf8;border-radius:50%;animation:spin .7s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.ebox{{max-width:640px;padding:18px;background:rgba(127,29,29,.15);border:1px solid #7f1d1d;border-radius:10px;color:#fca5a5;font-size:12px;font-family:'SF Mono',Monaco,Consolas,monospace;white-space:pre-wrap;max-height:240px;overflow:auto}}
#foot{{flex-shrink:0;font-size:11px;color:#475569;padding:6px 16px;background:#0a1120;border-top:1px solid #1e293b;transition:color .3s ease}}
.mcp-post-error{{max-width:640px;margin:12px auto;padding:14px;background:rgba(127,29,29,.15);border:1px solid #7f1d1d;border-radius:10px;color:#fca5a5;font-size:12px;font-family:'SF Mono',Monaco,Consolas,monospace;white-space:pre-wrap}}
@media (max-width: 767px) {{
  #hdr{{padding:12px 16px}}
  .desc{{max-width:none;width:100%;white-space:normal}}
}}
</style></head><body>
<div id="hdr"><h1>{name}</h1>{desc_html}<span class="badge {badge_cls}">{badge_text}</span>
<button class="btn" id="btnR" onclick="mcpLoad()">&#x21ba; Refresh</button></div>
<div id="shell"><div id="wrap"><div id="chart" data-mcp-chart="main"></div><div id="mcp-overlay-root"></div><div id="mcp-echart-root" class="mcp-root-slot"></div>
<div id="ov"><div class="spin"></div><div style="color:#94a3b8;font-size:13px">Loading dashboard&hellip;</div></div></div>
</div>
<div id="foot">Loading ECharts library&hellip;</div>
<script>
/* ══════════════════════════════════════════════════════════════════════════════
   MCP EChart Runtime — ES6 Industrial Edition
   ══════════════════════════════════════════════════════════════════════════════ */
'use strict';

// ── Configuration constants ──────────────────────────────────────────────────
const ST = {static_str};
const DU = {json.dumps(data_url)};
const HD = {has_data_js};
const CDNS = {cdn_json};
const MCP_LAYOUT = {{
  minHeight: {layout_min_height},
  mobileMinHeight: {layout_mobile_min_height},
  minWidth: {layout_min_width},
  isDashboard: {'true' if inferred_dashboard else 'false'}
}};
const RAW_OPTION_JS = {raw_option_js};
const NEEDED_MAPS = {needed_maps_json};
const MAP_SOURCES = {map_sources_json};
const MCP_OPTION_KEYS = new Set([
  'title','legend','tooltip','toolbox','grid','xAxis','yAxis',
  'radar','geo','visualMap','dataset','series','graphic'
]);
const POST_JS_NEEDS_CHART = {needs_chartjs};

// ── Mutable state ────────────────────────────────────────────────────────────
let cdnIndex = 0;
let chart = null;
let mcpOption = ST;
let resizeTimer = null;
let mcpJsData = null;
let mcpEventsBound = false;
let mcpObserversBound = false;
let mcpPostInitAttempts = 0;

// ── DOM references ───────────────────────────────────────────────────────────
const ov = document.getElementById('ov');
const ft = document.getElementById('foot');
const wrap = document.getElementById('wrap');
const chartEl = document.getElementById('chart');
const overlayRoot = document.getElementById('mcp-overlay-root');

// ── DOM element resolution (safety net for LLM-generated IDs) ────────────────
const _mcpOrigGetElementById = document.getElementById.bind(document);
const _mcpOrigQuerySelector = document.querySelector.bind(document);
const _mcpFallbackNodes = {{}};

const _KNOWN_CHART_IDS = new Set([
  'mcp_chart','mcp-chart','echart','echart_root',
  'chart-container','chart_container','chart-root','chart_root'
]);

const _mcpResolveKnownElement = (id) => {{
  if (_KNOWN_CHART_IDS.has(id)) return chartEl;
  if (id === 'mcp-echart-root') return _mcpOrigGetElementById('mcp-echart-root');
  return null;
}};

const _mcpEnsureElement = (id) => {{
  if (_mcpFallbackNodes[id]) return _mcpFallbackNodes[id];
  const el = document.createElement('div');
  el.id = id;
  el.setAttribute('data-mcp-generated-id', id);
  const isOverlay = /overlay|kpi|card|metric|summary|badge|label|panel|container|^ch[-_]/i.test(id);
  if (isOverlay && overlayRoot) {{
    el.className = 'mcp-overlay-node';
    overlayRoot.appendChild(el);
  }} else {{
    el.style.display = 'none';
    el.className = 'mcp-fallback-node';
    document.body.appendChild(el);
    console.warn('MCP EChart: created fallback element for missing id:', id);
  }}
  _mcpFallbackNodes[id] = el;
  return el;
}};

document.getElementById = (id) =>
  _mcpOrigGetElementById(id) || _mcpResolveKnownElement(id) || _mcpEnsureElement(id);

window.mcpById = (id) =>
  _mcpOrigGetElementById(id) || _mcpResolveKnownElement(id) || _mcpEnsureElement(id);

document.querySelector = (selector) => {{
  if (typeof selector === 'string' && selector.startsWith('#') &&
      !selector.includes(' ') && !selector.includes('>') && !selector.includes('.'))
    return document.getElementById(selector.slice(1));
  return _mcpOrigQuerySelector(selector);
}};

// ── Utility functions ────────────────────────────────────────────────────────
const mcpPercentValue = (value) => {{
  if (typeof value === 'number') return value;
  if (typeof value !== 'string') return null;
  const text = value.trim();
  if (!text.endsWith('%')) return null;
  const num = parseFloat(text.slice(0, -1));
  return Number.isFinite(num) ? num : null;
}};

const mcpSetColor = (container, key, preferred, palette) => {{
  if (!container || typeof container !== 'object') return;
  const current = container[key];
  if (current === undefined || current === null) {{
    container[key] = preferred;
    return;
  }}
  if (typeof current === 'string' && palette.includes(current.trim().toLowerCase()))
    container[key] = preferred;
}};

const extractJsData = (payload) => {{
  if (!payload || typeof payload !== 'object') return null;
  if (payload.__js_data__ !== undefined) return payload.__js_data__;
  const jsData = {{}};
  let hasCustom = false;
  for (const [key, val] of Object.entries(payload)) {{
    if (key === 'error' || key === 'error_detail' || key === '__meta') continue;
    if (key.startsWith('__')) continue;
    if (MCP_OPTION_KEYS.has(key)) continue;
    jsData[key] = val;
    hasCustom = true;
  }}
  return hasCustom ? jsData : null;
}};

const exposeJsDataGlobals = (payload) => {{
  if (!payload || typeof payload !== 'object') return;
  for (const [key, val] of Object.entries(payload)) {{
    if (/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(key) && window[key] === undefined)
      window[key] = val;
  }}
}};

// ── Theme normalizer (runtime) ───────────────────────────────────────────────
const mcpNormalizeRuntimeTheme = (option) => {{
  if (!option || typeof option !== 'object' || Array.isArray(option)) return option;

  const bg = option.backgroundColor;
  const isDarkBg = !bg || bg === 'transparent' || bg === 'rgba(0,0,0,0)' ||
                   bg === '#0f172a' || bg === '#111827' || bg === '#0b1020';
  if (!isDarkBg) return option;

  const darkPalette = [
    '#000','#000000','#111','#111111','#222','#222222','#333','#333333',
    '#444','#444444','#555','#555555','#666','#666666','#1f2937','#374151'
  ];
  const strongText = '#f8fafc';
  const normalText = '#e2e8f0';
  const mutedText = '#cbd5e1';
  const lineColor = '#334155';

  const normalizeTextStyle = (node, preferred) => {{
    if (!node || typeof node !== 'object') return;
    const style = node.textStyle || {{}};
    node.textStyle = style;
    mcpSetColor(style, 'color', preferred, darkPalette);
  }};

  const normalizeAxis = (axisObj) => {{
    const axes = Array.isArray(axisObj) ? axisObj : [axisObj];
    for (const axis of axes) {{
      if (!axis || typeof axis !== 'object') continue;
      const axisLabel = axis.axisLabel || {{}};
      axis.axisLabel = axisLabel;
      mcpSetColor(axisLabel, 'color', mutedText, darkPalette);
      const nameTextStyle = axis.nameTextStyle || {{}};
      axis.nameTextStyle = nameTextStyle;
      mcpSetColor(nameTextStyle, 'color', normalText, darkPalette);
      if (axis.splitLine && typeof axis.splitLine === 'object') {{
        const lineStyle = axis.splitLine.lineStyle || {{}};
        axis.splitLine.lineStyle = lineStyle;
        mcpSetColor(lineStyle, 'color', lineColor, darkPalette);
      }}
    }}
  }};

  normalizeTextStyle(option.title, strongText);
  if (Array.isArray(option.title)) option.title.forEach(t => normalizeTextStyle(t, strongText));
  normalizeTextStyle(option.legend, normalText);
  if (Array.isArray(option.legend)) option.legend.forEach(l => normalizeTextStyle(l, normalText));
  normalizeAxis(option.xAxis);
  normalizeAxis(option.yAxis);
  normalizeAxis(option.singleAxis);

  if (option.radar && typeof option.radar === 'object') {{
    const radarName = option.radar.name || {{}};
    option.radar.name = radarName;
    mcpSetColor(radarName, 'color', normalText, darkPalette);
  }}

  if (Array.isArray(option.series)) {{
    for (const series of option.series) {{
      if (!series || typeof series !== 'object') continue;
      const label = series.label || {{}};
      series.label = label;
      mcpSetColor(label, 'color', normalText, darkPalette);
      if (series.upperLabel && typeof series.upperLabel === 'object')
        mcpSetColor(series.upperLabel, 'color', normalText, darkPalette);
      if (series.detail && typeof series.detail === 'object')
        mcpSetColor(series.detail, 'color', strongText, darkPalette);
      if (series.axisLabel && typeof series.axisLabel === 'object')
        mcpSetColor(series.axisLabel, 'color', mutedText, darkPalette);
    }}
  }}
  return option;
}};

// ── Axis index remapper + bounds clamper ──────────────────────────────────────
const mcpRemapAxisIndices = (option) => {{
  if (!option || typeof option !== 'object' || Array.isArray(option)) return option;
  if (!Array.isArray(option.series) || !option.series.length) return option;

  // ① Build gridIndex -> array position maps (for non-contiguous gridIndex)
  const buildIndexMap = (axisKey) => {{
    const axes = option[axisKey];
    if (!Array.isArray(axes) || axes.length < 2) return null;
    let needsRemap = false;
    const map = {{}};
    axes.forEach((axis, pos) => {{
      const gi = (axis && typeof axis === 'object' && axis.gridIndex !== undefined)
        ? axis.gridIndex : pos;
      map[gi] = pos;
      if (gi !== pos) needsRemap = true;
    }});
    return needsRemap ? map : null;
  }};

  const xMap = buildIndexMap('xAxis');
  const yMap = buildIndexMap('yAxis');
  const gMap = buildIndexMap('grid');
  const xLen = Array.isArray(option.xAxis) ? option.xAxis.length : 0;
  const yLen = Array.isArray(option.yAxis) ? option.yAxis.length : 0;
  const gLen = Array.isArray(option.grid) ? option.grid.length : 0;

  // ② Apply remapping AND clamp out-of-bounds indices
  option.series.forEach(series => {{
    if (!series || typeof series !== 'object') return;

    // xAxisIndex: remap via gridIndex map, then clamp to valid range
    if (series.xAxisIndex !== undefined && xLen > 0) {{
      let idx = series.xAxisIndex;
      if (xMap && xMap[idx] !== undefined) idx = xMap[idx];
      series.xAxisIndex = Math.max(0, Math.min(idx, xLen - 1));
    }}
    // yAxisIndex: remap + clamp
    if (series.yAxisIndex !== undefined && yLen > 0) {{
      let idx = series.yAxisIndex;
      if (yMap && yMap[idx] !== undefined) idx = yMap[idx];
      series.yAxisIndex = Math.max(0, Math.min(idx, yLen - 1));
    }}
    // gridIndex: remap + clamp
    if (series.gridIndex !== undefined && gLen > 0) {{
      let idx = series.gridIndex;
      if (gMap && gMap[idx] !== undefined) idx = gMap[idx];
      series.gridIndex = Math.max(0, Math.min(idx, gLen - 1));
    }}
  }});

  // ③ Strip gridIndex from axis items (ECharts uses array position, not gridIndex)
  ['xAxis', 'yAxis'].forEach(key => {{
    if (Array.isArray(option[key])) {{
      option[key].forEach(axis => {{
        if (axis && typeof axis === 'object' && axis.gridIndex !== undefined)
          delete axis.gridIndex;
      }});
    }}
  }});

  return option;
}};

// ── Dashboard force-layout (permanent solution) ──────────────────────────────
// Groups series into LOGICAL CHARTS and ALWAYS assigns each its own slot.
// No overlap detection needed — we always redistribute when 2+ logical charts.
const mcpNormalizeRuntimeDashboardOption = (option) => {{
  if (!option || typeof option !== 'object' || Array.isArray(option)) return option;
  const seriesList = Array.isArray(option.series) ? option.series : null;
  if (!seriesList || !seriesList.length) return option;

  const CENTER_TYPES = new Set(['pie', 'gauge', 'radar', 'sunburst', 'funnel']);
  const CARTESIAN_TYPES = new Set(['bar', 'line', 'scatter', 'heatmap', 'candlestick']);

  // ── Step 1: classify each series ──────────────────────────────────────────
  const centerSeries = [];    // each = 1 logical chart
  const cartesianSeries = [];  // grouped by axis below

  seriesList.forEach((s, idx) => {{
    if (!s || typeof s !== 'object') return;
    const t = (s.type || '').toLowerCase().trim();
    if (CENTER_TYPES.has(t))    centerSeries.push({{ idx, s, t }});
    else if (CARTESIAN_TYPES.has(t)) cartesianSeries.push({{ idx, s, t }});
  }});

  // ── Step 2: group cartesian series by their grid slot ─────────────────────
  // Series sharing the same xAxisIndex (or no xAxisIndex) form ONE logical chart
  const cartesianGroups = new Map(); // gridKey -> array of item objects
  cartesianSeries.forEach(item => {{
    const key = item.s.xAxisIndex !== undefined ? `${{item.s.xAxisIndex}}` : '0';
    if (!cartesianGroups.has(key)) cartesianGroups.set(key, []);
    cartesianGroups.get(key).push(item);
  }});
  const cartesianGroupList = Array.from(cartesianGroups.values()); // each group = 1 logical chart

  // ── Step 3: total logical charts ─────────────────────────────────────────
  const totalLogical = cartesianGroupList.length + centerSeries.length;
  if (totalLogical < 2) return option; // single chart, nothing to do

  // ── Step 4: panel slot calculator ─────────────────────────────────────────
  const cols = totalLogical <= 1 ? 1 : (totalLogical <= 4 ? 2 : (totalLogical <= 9 ? 3 : 4));
  const rows = Math.ceil(totalLogical / cols);
  // Generous gaps and padding to prevent cross-cell label bleed
  const GAP_X = 8, GAP_Y = 12, PAD_L = 3, PAD_T = 5, PAD_B = 4;
  const totalW = 100 - PAD_L * 2;
  const totalH = 100 - PAD_T - PAD_B;
  const cellW = (totalW - (cols - 1) * GAP_X) / cols;
  const cellH = (totalH - (rows - 1) * GAP_Y) / rows;
  const TITLE_H = 5; // percentage height reserved for title at top of each cell

  const slot = (pos) => {{
    const r = Math.floor(pos / cols);
    const c = pos % cols;
    const left  = PAD_L + c * (cellW + GAP_X);
    const top   = PAD_T + r * (cellH + GAP_Y);
    const right = PAD_L + (cols - 1 - c) * (cellW + GAP_X);
    const cx    = left + cellW / 2;
    // Center vertically in the content area (below title)
    const contentTop = top + TITLE_H;
    const contentH   = cellH - TITLE_H;
    const cy    = contentTop + contentH / 2;
    return {{ left, top, right, cellW, cellH, cx, cy, contentTop, contentH }};
  }};

  // ── Step 5: assign slots to cartesian groups ──────────────────────────────
  const ensureArray = (key, len) => {{
    if (!Array.isArray(option[key])) {{
      const orig = option[key] && typeof option[key] === 'object' ? option[key] : {{}};
      option[key] = Array.from({{ length: len }}, (_, i) => i === 0 ? orig : {{}});
    }} else while (option[key].length < len) option[key].push({{}});
  }};
  const n = cartesianGroupList.length;
  if (n > 0) {{
    ensureArray('grid',  n);
    ensureArray('xAxis', n);
    ensureArray('yAxis', n);
  }}

  cartesianGroupList.forEach((group, gi) => {{
    const sl = slot(gi);
    // Force assign grid — extra top padding so 'top'-positioned bar labels don't overflow
    const g = option.grid[gi] = (option.grid[gi] || {{}});
    g.left         = `${{sl.left.toFixed(1)}}%`;
    g.right        = `${{sl.right.toFixed(1)}}%`;
    g.top          = `${{(sl.contentTop + 5).toFixed(1)}}%`; // +5 extra for bar labels above bars
    g.height       = `${{(sl.contentH - 9).toFixed(1)}}%`;
    g.containLabel = true;
    delete g.width; delete g.bottom;

    // Re-index axis to this grid slot
    if (option.xAxis[gi]) {{ option.xAxis[gi].gridIndex = gi; }}
    if (option.yAxis[gi]) {{ option.yAxis[gi].gridIndex = gi; }}

    // Series normalization: fix labels & assign grid
    group.forEach(item => {{
      item.s.xAxisIndex = gi;
      item.s.yAxisIndex = gi;
      // Force bar labels inside to prevent overflow above grid top edge
      if (item.t === 'bar') {{
        if (!item.s.label) item.s.label = {{}};
        // Only override 'top' position (which bleeds above grid) — leave 'inside' alone
        if (!item.s.label.position || item.s.label.position === 'top') {{
          item.s.label.position = 'inside';
          item.s.label.fontSize = 10;
          item.s.label.color    = '#fff';
        }}
      }}
    }});
  }});

  // ── Step 6: assign slots to center-based series ───────────────────────────
  // Use 30% of the smaller cell dimension for radius to keep labels inside cell
  centerSeries.forEach((item, ci) => {{
    const pos = cartesianGroupList.length + ci;
    const sl  = slot(pos);
    // Tight radius: max 30% of cell, so labels don't bleed into adjacent cells
    const maxR = Math.min(sl.cellW, sl.contentH) * 0.30;

    // Center is within the content area (below title strip)
    item.s.center = [`${{sl.cx.toFixed(1)}}%`, `${{sl.cy.toFixed(1)}}%`];

    if (item.t === 'pie' || item.t === 'sunburst') {{
      const outer = `${{Math.min(maxR, 18).toFixed(0)}}%`;
      const inner = `${{Math.min(maxR * 0.5, 10).toFixed(0)}}%`;
      item.s.radius = Array.isArray(item.s.radius) ? [inner, outer] : outer;
      // Shrink label font to reduce bleed
      if (!item.s.label) item.s.label = {{}};
      item.s.label.fontSize = 10;
    }} else if (item.t === 'gauge') {{
      item.s.radius = `${{Math.min(maxR, 20).toFixed(0)}}%`;
      if (!item.s.detail) item.s.detail = {{}};
      item.s.detail.fontSize = 12;
    }} else if (item.t === 'radar') {{
      if (!option.radar) option.radar = {{}};
      const radar = Array.isArray(option.radar) ? option.radar[0] : option.radar;
      if (radar) {{
        radar.center = item.s.center;
        radar.radius = `${{Math.min(maxR * 0.8, 15).toFixed(0)}}%`;
      }}
    }} else if (item.t === 'funnel') {{
      // Strip ALL conflicting positioning so our values take effect
      delete item.s.center; delete item.s.right; delete item.s.bottom;
      item.s.left   = `${{(sl.left + 3).toFixed(1)}}%`;
      item.s.top    = `${{sl.contentTop.toFixed(1)}}%`;
      item.s.width  = `${{(sl.cellW - 6).toFixed(1)}}%`;
      item.s.height = `${{(sl.contentH - 4).toFixed(1)}}%`;
      if (!item.s.label) item.s.label = {{}};
      item.s.label.fontSize = 11;
    }}
  }});

  // ── Step 7: fix title positions — place at TOP of each cell ──────────────
  if (Array.isArray(option.title)) {{
    option.title.forEach((title, idx) => {{
      if (!title || typeof title !== 'object' || idx >= totalLogical) return;
      const sl = slot(idx);
      title.left = `${{sl.left.toFixed(1)}}%`;
      title.top  = `${{sl.top.toFixed(1)}}%`;
      if (!title.textStyle) title.textStyle = {{}};
      if (!title.textStyle.fontSize) title.textStyle.fontSize = 13;
      // Force visible color on dark theme
      if (!title.textStyle.color) title.textStyle.color = '#e0e0e0';
      if (title.subtextStyle) {{
        if (!title.subtextStyle.color) title.subtextStyle.color = '#aaaaaa';
      }}
    }});
  }}

  return option;
}};

// ── Map runtime normalizer ───────────────────────────────────────────────────
const mcpNormalizeMapRuntimeOption = (option) => {{
  if (!option || typeof option !== 'object' || Array.isArray(option) ||
      !window.echarts || typeof echarts.getMap !== 'function') return option;

  const hasMap = (name) => !!(name && echarts.getMap(name));

  const sanitizeGeo = (entry) => {{
    if (!entry || typeof entry !== 'object') return null;
    if (!entry.map || !hasMap(entry.map)) return null;
    if (entry.regions && !Array.isArray(entry.regions)) delete entry.regions;
    return entry;
  }};

  if (Array.isArray(option.geo)) {{
    option.geo = option.geo.map(sanitizeGeo).filter(Boolean);
    if (!option.geo.length) delete option.geo;
  }} else if (option.geo) {{
    option.geo = sanitizeGeo(option.geo);
    if (!option.geo) delete option.geo;
  }}

  if (Array.isArray(option.series)) {{
    option.series = option.series.filter(series => {{
      if (!series || typeof series !== 'object') return true;
      if ((series.type || '').toLowerCase() !== 'map') return true;
      if (series.map && hasMap(series.map)) {{
        if (series.regions && !Array.isArray(series.regions)) delete series.regions;
        return true;
      }}
      return !!(series.geoIndex !== undefined && option.geo);
    }});
  }}
  return option;
}};

// Fill sparse arrays and ensure radar config to prevent ECharts internal crashes
const mcpSanitizeOption = (option) => {{
  if (!option || typeof option !== 'object') return option;
  // Fill sparse entries in all top-level arrays
  const arrKeys = ['series', 'xAxis', 'yAxis', 'grid', 'title', 'legend', 'dataZoom', 'visualMap'];
  arrKeys.forEach(k => {{
    if (Array.isArray(option[k])) {{
      for (let i = 0; i < option[k].length; i++) {{
        if (option[k][i] === undefined || option[k][i] === null) option[k][i] = {{}};
      }}
    }}
  }});
  // Ensure radar config exists if any radar series is present
  const seriesList = Array.isArray(option.series) ? option.series : (option.series ? [option.series] : []);
  const hasRadar = seriesList.some(s => s && s.type === 'radar');
  if (hasRadar) {{
    if (!option.radar) option.radar = {{}};
    const radarCfg = Array.isArray(option.radar) ? option.radar[0] : option.radar;
    if (radarCfg && !Array.isArray(radarCfg.indicator)) {{
      // Build minimal indicator from series data keys
      const radarSeries = seriesList.find(s => s && s.type === 'radar');
      const dataItems = (radarSeries && Array.isArray(radarSeries.data)) ? radarSeries.data : [];
      if (dataItems.length > 0 && Array.isArray(dataItems[0] && dataItems[0].value)) {{
        radarCfg.indicator = dataItems[0].value.map((_, i) => ({{ name: 'D' + i }}));
      }} else {{
        radarCfg.indicator = [{{ name: 'N/A' }}];
      }}
    }}
  }}
  return option;
}};

// Prepare runtime option pipeline with full sanitization
const mcpPrepareRuntimeOption = (option) => {{
  try {{
    return mcpSanitizeOption(mcpNormalizeMapRuntimeOption(mcpNormalizeRuntimeDashboardOption(mcpNormalizeRuntimeTheme(mcpRemapAxisIndices(option)))));
  }} catch (e) {{
    console.warn('mcpPrepareRuntimeOption error, using raw option:', e);
    return mcpSanitizeOption(option);
  }}
}};


const mcpResolveBaseOption = () => {{
  if (RAW_OPTION_JS && typeof RAW_OPTION_JS === 'string') {{
    try {{
      const rawOption = (new Function('"use strict";return (' + RAW_OPTION_JS + ');'))();
      if (rawOption && typeof rawOption === 'object' && !Array.isArray(rawOption))
        return mcpPrepareRuntimeOption(rawOption);
    }} catch (e) {{
      console.warn('raw_echart_option:', e);
    }}
  }}
  return mcpPrepareRuntimeOption(ST);
}};

// ── Layout sizing ────────────────────────────────────────────────────────────
const computedMinHeight = () => {{
  const mobile = window.innerWidth < 768;
  return mobile ? (MCP_LAYOUT.mobileMinHeight || MCP_LAYOUT.minHeight) : MCP_LAYOUT.minHeight;
}};

const computedMinWidth = () =>
  MCP_LAYOUT.isDashboard && window.innerWidth < 992 ? (MCP_LAYOUT.minWidth || 0) : 0;

const applyLayoutSizing = () => {{
  if (!wrap || !chartEl) return;
  const minHeight = computedMinHeight();
  const minWidth = computedMinWidth();
  wrap.style.minHeight = `${{minHeight}}px`;
  chartEl.style.height = `${{minHeight}}px`;
  chartEl.style.minHeight = `${{minHeight}}px`;
  chartEl.style.minWidth = minWidth ? `${{minWidth}}px` : '100%';
  if (chart) chart.resize();
}};

// ── Chart resize scheduling ──────────────────────────────────────────────────
const mcpRefreshChartPaint = () => {{
  if (!chart) return;
  try {{
    chart.resize();
    if (chart.getZr && chart.getZr()) chart.getZr().refreshImmediately();
  }} catch (e) {{ /* safe to ignore */ }}
}};

const scheduleChartResize = () => {{
  if (!chart) return;
  requestAnimationFrame(() => {{
    mcpRefreshChartPaint();
    setTimeout(mcpRefreshChartPaint, 60);
    setTimeout(mcpRefreshChartPaint, 220);
    setTimeout(mcpRefreshChartPaint, 480);
  }});
}};

const mcpScheduleInstanceResize = (instance) => {{
  if (!instance) return;
  const run = () => {{
    try {{
      instance.resize();
      if (instance.getZr && instance.getZr()) instance.getZr().refreshImmediately();
    }} catch (e) {{ /* safe */ }}
  }};
  requestAnimationFrame(() => {{
    run(); setTimeout(run, 60); setTimeout(run, 220); setTimeout(run, 480);
  }});
}};

// ── Chart container preparation ──────────────────────────────────────────────
const mcpPrepareChartContainer = (dom) => {{
  if (!dom || !dom.style) return dom;
  dom.style.width = dom.style.width || '100%';
  dom.style.maxWidth = '100%';
  dom.style.minWidth = '0';
  dom.style.overflow = 'hidden';
  if (!dom.style.height) dom.style.height = '100%';
  const parent = dom.parentElement;
  if (parent && parent.style) {{
    if (!parent.style.minWidth) parent.style.minWidth = '0';
    if (!parent.style.maxWidth) parent.style.maxWidth = '100%';
    if (!parent.style.overflow) parent.style.overflow = 'hidden';
  }}
  const cardParent = dom.closest('[style*="border-radius"], [data-mcp-generated-id]');
  if (cardParent && cardParent.style) {{
    if (!cardParent.style.minWidth) cardParent.style.minWidth = '0';
    if (!cardParent.style.maxWidth) cardParent.style.maxWidth = '100%';
    if (!cardParent.style.overflow) cardParent.style.overflow = 'hidden';
    cardParent.style.contain = cardParent.style.contain || 'layout paint';
  }}
  return dom;
}};

// ── Patch echarts.init for safe sub-chart creation ───────────────────────────
const mcpPatchEchartsInit = () => {{
  if (!window.echarts || echarts.__mcp_wrapped_init__) return;
  const _mcpOrigInit = echarts.init.bind(echarts);
  echarts.init = (dom, theme, opts) => {{
    dom = mcpPrepareChartContainer(dom);
    const instance = _mcpOrigInit(dom, theme, opts);
    if (instance && !instance.__mcp_wrapped__) {{
      instance.__mcp_wrapped__ = true;
      const _origSetOption = instance.setOption.bind(instance);
      instance.setOption = (option, options) => {{
        const res = _origSetOption(mcpPrepareRuntimeOption(option), options);
        mcpScheduleInstanceResize(instance);
        return res;
      }};
    }}
    return instance;
  }};
  echarts.__mcp_wrapped_init__ = true;
}};

// ── Post init JS execution (with error boundary) ────────────────────────────
const runPostInitJs = () => {{
  const rootDom = _mcpOrigGetElementById('mcp-echart-root');

  // Wait for Chart.js if post_init_js requires it
  if (POST_JS_NEEDS_CHART && typeof window.Chart === 'undefined') {{
    if (mcpPostInitAttempts < 50) {{
      mcpPostInitAttempts++;
      setTimeout(runPostInitJs, 100);
      return;
    }}
    console.warn('MCP EChart: Chart.js not loaded after 5s timeout');
  }}

  if (POST_JS_NEEDS_CHART && chartEl) {{
    try {{ if (chart) chart.dispose(); }} catch (e) {{ /* safe */ }}
    chartEl.style.display = 'block';
    chartEl.style.height = 'auto';
    chartEl.style.minHeight = `${{computedMinHeight()}}px`;
    chartEl.style.overflow = 'visible';
    chartEl.innerHTML = '';
    if (rootDom) {{ rootDom.style.display = 'none'; rootDom.innerHTML = ''; }}
    if (overlayRoot) overlayRoot.style.display = 'none';
  }} else {{
    if (chartEl) {{
      chartEl.style.display = 'block';
      chartEl.style.height = `${{computedMinHeight()}}px`;
      chartEl.style.minHeight = `${{computedMinHeight()}}px`;
      chartEl.style.overflow = 'hidden';
    }}
    if (overlayRoot) overlayRoot.style.display = 'block';
  }}

  const dom = (POST_JS_NEEDS_CHART && chartEl)
    ? chartEl
    : ((chart && chart.getDom) ? chart.getDom() : chartEl);
  window.dom = dom;
  window.mcpData = mcpJsData;
  if (chart) {{
    chart.__mcp_js_data__ = mcpJsData;
    chart.__mcp_data__ = mcpJsData;
  }}

  try {{
    {post_js}
  }} catch (e) {{
    console.error('post_init_js error:', e);
    // Show error visually so user can debug
    const errDiv = document.createElement('div');
    errDiv.className = 'mcp-post-error';
    errDiv.textContent = `\u26a0 post_init_js error: ${{e.message}}`;
    if (chartEl && chartEl.parentElement)
      chartEl.parentElement.appendChild(errDiv);
  }}
}};

const queuePostInitJs = () => {{
  mcpPostInitAttempts = 0;
  runPostInitJs();
}};

// ── Main chart instance management ───────────────────────────────────────────
const mcpEnsureMainChart = () => {{
  if (!window.echarts) return false;
  const chartDom = document.getElementById('chart');
  if (!chartDom) return false;
  if (!chart) return true;
  const needsReset = !!chart.__mcp_soft_disposed__ || (chart.isDisposed && chart.isDisposed());
  if (!needsReset) return true;
  try {{
    const existing = echarts.getInstanceByDom(chartDom);
    if (existing) existing.dispose();
  }} catch (e) {{ /* safe */ }}
  chartDom.innerHTML = '';
  chart = null;
  initChart(true);
  return !!chart;
}};

// ── CDN loading ──────────────────────────────────────────────────────────────
const loadEcharts = () => {{
  if (cdnIndex >= CDNS.length) {{
    ov.innerHTML = '<div class="ebox">&#9888; Failed to load ECharts from all CDNs.<br>Check your network connection.</div>';
    ft.textContent = 'ECharts load failed';
    ft.style.color = '#f87171';
    return;
  }}
  const s = document.createElement('script');
  s.src = CDNS[cdnIndex];
  s.async = false;
  s.onload = () => loadAllMaps(0);
  s.onerror = () => {{
    cdnIndex++;
    ft.textContent = `CDN ${{cdnIndex}} failed, trying next\u2026`;
    loadEcharts();
  }};
  document.head.appendChild(s);
}};

const loadAllMaps = (idx) => {{
  if (idx >= NEEDED_MAPS.length) {{ initChart(); return; }}
  const name = NEEDED_MAPS[idx];
  const sources = MAP_SOURCES[name] || [];
  ft.textContent = `Loading ${{name}} map\u2026`;
  fetchMap(name, sources, 0, () => loadAllMaps(idx + 1));
}};

const fetchMap = (name, sources, si, done) => {{
  if (si >= sources.length) {{
    ov.innerHTML = `<div class="ebox">&#9888; Map \u2018${{name}}\u2019 failed to load from all CDNs.</div>`;
    ft.textContent = 'Map load failed';
    ft.style.color = '#f87171';
    done();
    return;
  }}
  fetch(sources[si])
    .then(r => {{ if (!r.ok) throw new Error(`HTTP ${{r.status}}`); return r.json(); }})
    .then(geo => {{ echarts.registerMap(name, geo); done(); }})
    .catch(() => fetchMap(name, sources, si + 1, done));
}};

// ── Chart initialization ─────────────────────────────────────────────────────
const initChart = (skipLoad) => {{
  mcpPatchEchartsInit();
  applyLayoutSizing();
  const chartDom = mcpPrepareChartContainer(document.getElementById('chart'));
  chart = echarts.init(chartDom, null, {{ renderer: 'canvas' }});
  chart.__mcp_soft_disposed__ = false;
  chart.__mcp_dom__ = chartDom;

  const _mcpOriginalGetDom = chart.getDom ? chart.getDom.bind(chart) : () => chartDom;
  const _mcpOriginalDispose = chart.dispose ? chart.dispose.bind(chart) : () => {{}};

  chart.getDom = () => {{
    try {{ return _mcpOriginalGetDom() || chart.__mcp_dom__ || chartDom; }}
    catch (e) {{ return chart.__mcp_dom__ || chartDom; }}
  }};

  chart.dispose = () => {{
    chart.__mcp_soft_disposed__ = true;
    chart.__mcp_dom__ = chartDom;
    try {{ chart.clear(); }} catch (e) {{ /* safe */ }}
    return chart.__mcp_dom__;
  }};

  const _mcpOriginalSetOption = chart.setOption.bind(chart);
  chart.setOption = (option, opts) => {{
    const res = _mcpOriginalSetOption(mcpPrepareRuntimeOption(option), opts);
    scheduleChartResize();
    return res;
  }};

  // ── Event listeners (bind once) ──
  if (!mcpEventsBound) {{
    window.addEventListener('resize', () => {{
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(applyLayoutSizing, 60);
    }});
    window.addEventListener('pageshow', () => scheduleChartResize());
    window.addEventListener('load', () => scheduleChartResize());
    window.addEventListener('scroll', () => scheduleChartResize(), {{ passive: true }});
    document.addEventListener('visibilitychange', () => {{
      if (!document.hidden) scheduleChartResize();
    }});
    mcpEventsBound = true;
  }}

  if (window.ResizeObserver && !mcpObserversBound) {{
    new ResizeObserver(() => {{ applyLayoutSizing(); scheduleChartResize(); }})
      .observe(document.getElementById('shell'));
    new ResizeObserver(() => {{ applyLayoutSizing(); scheduleChartResize(); }})
      .observe(chartEl);
    mcpObserversBound = true;
  }}

  try {{ {pre_js} }} catch (e) {{ console.warn('pre_init_js:', e); }}
  chart.setOption(mcpResolveBaseOption(), {{ notMerge: false }});
  scheduleChartResize();
  ft.textContent = 'ECharts ready';
  if (!skipLoad) mcpLoad();
}};

// Unflatten path-format keys from data_code result
// e.g. 'xAxis[0].data' key becomes xAxis array with data inside
const mcpUnflattenOption = (flat) => {{
  if (!flat || typeof flat !== 'object' || Array.isArray(flat)) return flat;
  const out = {{}};
  for (const [rawKey, value] of Object.entries(flat)) {{
    if (rawKey.startsWith('__')) {{ out[rawKey] = value; continue; }}
    // Check if key is a path (contains . or [)
    const hasBracket = rawKey.indexOf('[') !== -1;
    const hasDot     = rawKey.indexOf('.') !== -1;
    if (!hasBracket && !hasDot) {{ out[rawKey] = value; continue; }}
    // Parse e.g. 'xAxis[0].data' -> ['xAxis', '0', 'data']
    // Parse 'xAxis[0].data' into segments without regex (avoids f-string escaping)
    const segs = [];
    let buf = '';
    for (let ci = 0; ci < rawKey.length; ci++) {{
      const ch = rawKey[ci];
      if (ch === '.' || ch === '[') {{
        if (buf) segs.push(buf);
        buf = '';
      }} else if (ch === ']') {{
        if (buf) segs.push(buf);
        buf = '';
      }} else {{ buf += ch; }}
    }}
    if (buf) segs.push(buf);
    if (!segs.length) {{ out[rawKey] = value; continue; }}
    const isNum = (s) => s.length > 0 && s.split('').every(c => c >= '0' && c <= '9');
    let cur = out;
    for (let i = 0; i < segs.length - 1; i++) {{
      const seg  = segs[i];
      const next = segs[i + 1];
      if (cur[seg] === undefined || cur[seg] === null)
        cur[seg] = isNum(next) ? [] : {{}};
      cur = cur[seg];
    }}
    const last = segs[segs.length - 1];
    if (isNum(last)) cur[parseInt(last, 10)] = value;
    else cur[last] = value;
  }}
  return out;
}};

// ── Deep merge ───────────────────────────────────────────────────────────────
const _dm = (d, s) => {{
  if (s === null || s === undefined) return d;
  if (typeof s !== 'object') return s;
  if (Array.isArray(s)) {{
    if (!Array.isArray(d)) return s;
    const len = Math.max(d.length, s.length);
    const arr = [];
    for (let i = 0; i < len; i++) {{
      if (i >= s.length) arr.push(d[i]);
      else if (i >= d.length) arr.push(s[i]);
      else if (s[i] && typeof s[i] === 'object' && !Array.isArray(s[i]) &&
               d[i] && typeof d[i] === 'object' && !Array.isArray(d[i]))
        arr.push(_dm(d[i], s[i]));
      else arr.push(s[i]);
    }}
    return arr;
  }}
  const o = Object.assign({{}}, d);
  for (const k of Object.keys(s)) {{
    o[k] = (d && Object.prototype.hasOwnProperty.call(d, k)) ? _dm(d[k], s[k]) : s[k];
  }}
  return o;
}};

// ── Data loading ─────────────────────────────────────────────────────────────
const mcpLoad = async () => {{
  if (!mcpEnsureMainChart()) return;
  if (!chart) return;
  if (!HD) {{
    ov.classList.add('hidden');
    ft.textContent = 'Static chart \u2014 no data handler configured.';
    queuePostInitJs();
    return;
  }}

  ov.innerHTML = '<div class="spin"></div><div style="color:#94a3b8;font-size:13px">Fetching live data\u2026</div>';
  ov.classList.remove('hidden');
  const btn = document.getElementById('btnR');
  if (btn) btn.disabled = true;
  const t0 = Date.now();

  try {{
    const r = await fetch(DU);
    if (!r.ok) throw new Error(`HTTP ${{r.status}} from data endpoint`);
    const d = await r.json();
    if (d.error) throw new Error(d.error + (d.error_detail ? '\\n\\n' + d.error_detail : ''));

    const meta = d.__meta || {{}};
    mcpJsData = extractJsData(d);
    window.mcpJsData = mcpJsData;
    if (chart) chart.__mcp_js_data__ = mcpJsData;
    exposeJsDataGlobals(mcpJsData);

    // Remove internal keys before merge
    delete d.__meta;
    delete d.__js_data__;
    for (const k of Object.keys(d)) {{
      if (k.startsWith('__')) delete d[k];
    }}

    // Unflatten path keys then deep-merge, then re-apply normalizer
    const unflat = mcpUnflattenOption(d);
    mcpOption = mcpPrepareRuntimeOption(_dm(mcpResolveBaseOption(), unflat));
    chart.setOption(mcpOption, {{ notMerge: true }});
    scheduleChartResize();

    ov.classList.add('hidden');
    ft.textContent = `Updated ${{new Date().toLocaleTimeString()}} \u00b7 ${{meta.duration_ms || (Date.now() - t0)}}ms`;
    ft.style.color = '#475569';
    queuePostInitJs();
  }} catch (e) {{
    ov.innerHTML = `<div class="ebox">\u26a0 ${{String(e.message).replace(/</g, '&lt;')}}</div>`;
    ft.style.color = '#f87171';
    ft.textContent = 'Data error \u2014 fix data_code and refresh';
  }} finally {{
    if (btn) btn.disabled = false;
  }}
}};

// ── Boot ─────────────────────────────────────────────────────────────────────
loadEcharts();
</script></body></html>'''

    @http.route('/mcp/echart/<string:slug>', type='http', auth='none',
                methods=['GET'], csrf=False, save_session=False)
    def render_echart(self, slug, **kw):
        chart = request.env['mcp.echart'].sudo().search(
            [('slug', '=', slug), ('active', '=', True)], limit=1)
        env, user, access_mode, err = self._resolve_public_record_access(
            chart, html=True, route_name='render_echart')
        if err:
            return err
        html = self._build_echart_html(
            chart,
            embed=kw.get('embed') == '1',
            data_url=f"/mcp/echart/{slug}/data",
        )
        return Response(html, status=200, mimetype='text/html')

    @http.route('/mcp/echart/public/<int:rec_id>/<string:token>', type='http',
                auth='none', methods=['GET'], csrf=False, save_session=False)
    def render_echart_public(self, rec_id, token, **kw):
        chart = request.env['mcp.echart'].sudo().browse(rec_id)
        env, user, access_mode, err = self._resolve_public_record_access(
            chart, share_token=token, html=True, route_name='render_echart_public')
        if err:
            return err
        html = self._build_echart_html(
            chart,
            embed=kw.get('embed') == '1',
            data_url=f"/mcp/echart/public/{rec_id}/{token}/data",
        )
        return Response(html, status=200, mimetype='text/html')

    @http.route('/mcp/echart/<string:slug>/data', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, save_session=False)
    def echart_data(self, slug, **kw):
        if request.httprequest.method == 'OPTIONS':
            return Response('', status=200, headers={'Access-Control-Allow-Origin': '*'})
        chart = request.env['mcp.echart'].sudo().search(
            [('slug', '=', slug), ('active', '=', True)], limit=1)
        env, user, access_mode, err = self._resolve_public_record_access(
            chart, route_name='echart_data')
        if err:
            return err
        if not chart.data_code or not chart.data_code.strip():
            return _json_response({"__meta": {"has_data_code": False}})

        globs = _build_safe_globals(env)
        locs  = {'result': {}}
        start = time.monotonic()
        try:
            mcp_exec(_prepare_echart_data_code(chart.data_code), globs, locs)
            dur    = round((time.monotonic() - start) * 1000)
            result = _normalize_echart_result(locs.get('result') or {})
            if not isinstance(result, dict):
                return _json_response({"error": f"data_code set result to {type(result).__name__}, expected dict.",
                                       "__meta": {"duration_ms": dur, "ok": False}}, 500)
            if '__error' in result:
                return _json_response({"error": result['__error'], "__meta": {"duration_ms": dur, "ok": False}}, 500)
            try:
                json.dumps(result, default=str)
            except Exception as ser_err:
                _log(env, tool='echart_data', operation='echart',
                     log_level='error', state='error', error=ser_err,
                     payload={'slug': slug, 'issue': 'non-serialisable result'})
                return _json_response({"error": f"result contains non-serialisable data: {ser_err}",
                                       "__meta": {"duration_ms": dur, "ok": False}}, 500)
            result['__meta'] = {"duration_ms": dur, "ok": True}
            return _json_response(result)
        except SyntaxError as e:
            dur = round((time.monotonic() - start) * 1000)
            return _json_response({"error": f"Syntax error in data_code at line {e.lineno}: {e.msg}",
                                   "error_detail": f"Line {e.lineno}: {e.text or ''}\\nSyntaxError: {e.msg}",
                                   "__meta": {"duration_ms": dur, "ok": False}}, 500)
        except Exception as e:
            dur = round((time.monotonic() - start) * 1000)
            tb  = traceback.format_exc()
            _logger.error("echart data_code [%s]: %s", slug, tb)
            _log(env, tool='echart_data', operation='echart',
                 log_level='error', state='error', error=e,
                 tb=tb, duration_ms=dur,
                 payload={'slug': slug})
            err_msg = str(e)
            hint    = ""
            if "read_group" in tb and "_read_group" not in tb:
                hint = "\\n💡 HINT: read_group() removed in Odoo 19 — use _read_group()"
            elif "strftime" in tb and "NoneType" in tb:
                hint = "\\n💡 HINT: Date is None — use: val.strftime('%b %Y') if val else 'Unknown'"
            elif "has no attribute" in tb and ("name" in tb or "display_name" in tb):
                hint = "\\n💡 HINT: Many2one is False — use: val.name if val else 'Unknown'"
            elif "Invalid field" in tb or "Unknown field" in tb or "does not exist" in tb:
                hint = "\\n💡 HINT: Field mismatch — call odoo_get_fields(model='...') first and use only live Odoo fields."
            elif "is not installed or not available in this Odoo database" in tb or "KeyError:" in tb:
                hint = "\\n💡 HINT: Model missing — call odoo_list_models first, and guard optional models with env.has_model('model.name')."
            return _json_response({"error": err_msg + hint, "error_detail": tb,
                                   "__meta": {"duration_ms": dur, "ok": False}}, 500)

    @http.route('/mcp/echart/public/<int:rec_id>/<string:token>/data', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, save_session=False)
    def echart_data_public(self, rec_id, token, **kw):
        if request.httprequest.method == 'OPTIONS':
            return Response('', status=200, headers={'Access-Control-Allow-Origin': '*'})
        chart = request.env['mcp.echart'].sudo().browse(rec_id)
        env, user, access_mode, err = self._resolve_public_record_access(
            chart, share_token=token, route_name='echart_data_public')
        if err:
            return err
        if not chart.data_code or not chart.data_code.strip():
            return _json_response({"__meta": {"has_data_code": False}})

        globs = _build_safe_globals(env)
        locs = {'result': {}}
        start = time.monotonic()
        try:
            mcp_exec(_prepare_echart_data_code(chart.data_code), globs, locs)
            dur = round((time.monotonic() - start) * 1000)
            result = _normalize_echart_result(locs.get('result') or {})
            if not isinstance(result, dict):
                return _json_response({"error": f"data_code set result to {type(result).__name__}, expected dict.",
                                       "__meta": {"duration_ms": dur, "ok": False}}, 500)
            if '__error' in result:
                return _json_response({"error": result['__error'], "__meta": {"duration_ms": dur, "ok": False}}, 500)
            try:
                json.dumps(result, default=str)
            except Exception as ser_err:
                _log(env, tool='echart_data', operation='echart',
                     user=user, log_level='error', state='error', error=ser_err,
                     payload={'rec_id': rec_id, 'issue': 'non-serialisable result'})
                return _json_response({"error": f"result contains non-serialisable data: {ser_err}",
                                       "__meta": {"duration_ms": dur, "ok": False}}, 500)
            result['__meta'] = {"duration_ms": dur, "ok": True}
            return _json_response(result)
        except SyntaxError as e:
            dur = round((time.monotonic() - start) * 1000)
            return _json_response({"error": f"Syntax error in data_code at line {e.lineno}: {e.msg}",
                                   "error_detail": f"Line {e.lineno}: {e.text or ''}\\nSyntaxError: {e.msg}",
                                   "__meta": {"duration_ms": dur, "ok": False}}, 500)
        except Exception as e:
            dur = round((time.monotonic() - start) * 1000)
            tb = traceback.format_exc()
            _logger.error("echart public data_code [%s]: %s", rec_id, tb)
            _log(env, tool='echart_data', operation='echart',
                 user=user, log_level='error', state='error', error=e,
                 tb=tb, duration_ms=dur,
                 payload={'rec_id': rec_id})
            hint = ""
            if "read_group" in tb and "_read_group" not in tb:
                hint = "\\n💡 HINT: read_group() removed in Odoo 19 — use _read_group()"
            elif "Invalid field" in tb or "Unknown field" in tb or "does not exist" in tb:
                hint = "\\n💡 HINT: Field mismatch — call odoo_get_fields(model='...') first and use only live Odoo fields."
            elif "is not installed or not available in this Odoo database" in tb or "KeyError:" in tb:
                hint = "\\n💡 HINT: Model missing — call odoo_list_models first, and guard optional models with env.has_model('model.name')."
            return _json_response({"error": str(e) + hint, "error_detail": tb,
                                   "__meta": {"duration_ms": dur, "ok": False}}, 500)

    # ── WebApp HTML builder & routes ──────────────────────────────────────

    def _build_webapp_html(self, app, data_url=''):
        import re as _r
        import json as _json

        name = (app.name or '').replace('<', '&lt;').replace('>', '&gt;')
        desc = (app.description or '').replace('<', '&lt;').replace('>', '&gt;')
        slug = app.slug
        data_url = data_url or f"/mcp/app/{slug}/data"
        has_data = bool(app.data_code and app.data_code.strip())
        has_data_js = 'true' if has_data else 'false'
        name_js = _json.dumps(name)
        desc_meta = f'<meta name="description" content="{desc}">' if desc else ''

        # ── Portal user detection — passes session user into window.odoo.portal ──
        try:
            _sess_uid = request.session.uid
            if _sess_uid:
                _u = request.env['res.users'].sudo().browse(_sess_uid)
                _portal_info = {
                    'uid':        _sess_uid,
                    'name':       _u.name or '',
                    'partner_id': _u.partner_id.id if _u.partner_id else None,
                    'is_portal':  _u.has_group('base.group_portal'),
                    'is_admin':   _u.has_group('base.group_system'),
                }
            else:
                _portal_info = {'uid': None, 'name': '', 'partner_id': None, 'is_portal': False, 'is_admin': False}
        except Exception:
            _portal_info = {'uid': None, 'name': '', 'partner_id': None, 'is_portal': False, 'is_admin': False}
        portal_js = _json.dumps(_portal_info)

        jsx_src = (app.jsx_code or '').strip()

        def _strip_esm(code):
            code = _r.sub(r'^[ \t]*import\s[^\'\"\n]*from\s+[\'"][^\'"]+[\'"];?[ \t]*$', '', code, flags=_r.MULTILINE)
            code = _r.sub(r'^[ \t]*import\s+[\'"][^\'"]+[\'"];?[ \t]*$', '', code, flags=_r.MULTILINE)
            exported_name = None
            m = _r.search(r'export\s+default\s+function\s+([A-Z]\w*)', code)
            if m:
                exported_name = m.group(1)
            else:
                m = _r.search(r'export\s+default\s+([A-Z]\w*)\s*[;(]?', code)
                if m:
                    exported_name = m.group(1)
            code = _r.sub(r'^[ \t]*export\s+default\s+function\s+([A-Z]\w*)\s*\(', 'function App(', code,
                          flags=_r.MULTILINE)
            code = _r.sub(r'^[ \t]*export\s+default\s+\w[\w.]*\s*;?[ \t]*$', '', code, flags=_r.MULTILINE)
            code = _r.sub(r'^[ \t]*export\s+(?=const|let|var|function|class|async)', '', code, flags=_r.MULTILINE)
            if exported_name and exported_name != 'App':
                code = _r.sub(r'\bfunction\s+' + _r.escape(exported_name) + r'\s*\(', 'function App(', code)
                code = _r.sub(r'\bconst\s+' + _r.escape(exported_name) + r'\s*=', 'const App =', code)
            has_app = bool(_r.search(r'\bfunction\s+App\s*\(', code) or _r.search(r'\bconst\s+App\s*=', code))
            if not has_app:
                all_funcs = list(_r.finditer(r'\bfunction\s+([A-Z]\w*)\s*\(', code))
                if all_funcs:
                    last_name = all_funcs[-1].group(1)
                    code = _r.sub(r'\bfunction\s+' + _r.escape(last_name) + r'\s*\(', 'function App(', code)
                else:
                    all_consts = list(_r.finditer(r'\bconst\s+([A-Z]\w*)\s*=\s*(?:function|\(|async)', code))
                    if all_consts:
                        last_name = all_consts[-1].group(1)
                        code = _r.sub(r'\bconst\s+' + _r.escape(last_name) + r'\s*=', 'const App =', code)
            return code.strip()

        if jsx_src:
            jsx_src = _strip_esm(jsx_src)

        # Detect optional libs needed
        needs_echarts = 'echarts' in jsx_src
        needs_plotly = 'Plotly' in jsx_src
        needs_dayjs = 'dayjs' in jsx_src
        needs_lodash = '_.' in jsx_src
        needs_papaparse = 'Papa' in jsx_src

        lib_script_tags = ''
        if needs_echarts:
            lib_script_tags += '<script src="https://cdnjs.cloudflare.com/ajax/libs/echarts/5.5.1/echarts.min.js"></script>\n'
        if needs_plotly:
            lib_script_tags += '<script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.27.0/plotly.min.js"></script>\n'
        if needs_dayjs:
            lib_script_tags += '<script src="https://cdnjs.cloudflare.com/ajax/libs/dayjs/1.11.10/dayjs.min.js"></script>\n'
        if needs_lodash:
            lib_script_tags += '<script src="https://cdnjs.cloudflare.com/ajax/libs/lodash.js/4.17.21/lodash.min.js"></script>\n'
        if needs_papaparse:
            lib_script_tags += '<script src="https://cdnjs.cloudflare.com/ajax/libs/PapaParse/5.4.1/papaparse.min.js"></script>\n'

        default_app_js = """
    function App() {
      const [data, setData] = React.useState(null);
      const [err,  setErr]  = React.useState(null);
      React.useEffect(() => {
        window.odoo.fetch()
          .then(d  => setData(d))
          .catch(e => setErr(e.message));
      }, []);
      if (err)  return React.createElement('div', {className:'mcp-err'}, err);
      if (!data) return React.createElement('div', {className:'mcp-loading'},
        React.createElement('div', {className:'mcp-spin'}), 'Loading...');
      return React.createElement('div', {className:'mcp-json'},
        React.createElement('pre', null, JSON.stringify(data, null, 2)));
    }
    """

        # Build the final app JS — wraps user code with React hooks injected
        if jsx_src:
            app_code = jsx_src
        else:
            app_code = default_app_js

        app_code_json = _json.dumps(app_code)

        html = f"""<!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    {desc_meta}
    <title>{name}</title>

    <!-- Tailwind CSS Play CDN — full Tailwind, all classes work -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
    tailwind.config = {{
      theme: {{
        extend: {{
          colors: {{
            brand: {{ 50:'#eff6ff',100:'#dbeafe',500:'#3b82f6',600:'#2563eb',700:'#1d4ed8',900:'#1e3a8a' }},
          }}
        }}
      }}
    }}
    </script>

    <!-- React + ReactDOM UMD -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.development.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.development.js"></script>

    <!-- Babel standalone for JSX transform -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/7.26.5/babel.min.js"></script>

    <!-- Chart.js 4 — always available as global Chart (no import needed) -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>

    <!-- Optional libs (only loaded if detected in jsx_code) -->
    {lib_script_tags}

    <style>
      *, *::before, *::after {{ box-sizing: border-box; }}
      html, body {{ margin: 0; padding: 0; min-height: 100%; }}
      body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
      #mcp-root {{ min-height: 100vh; }}
      .mcp-loading {{ display:flex;align-items:center;justify-content:center;gap:12px;min-height:50vh;color:#64748b;font-size:15px; }}
      .mcp-spin {{ width:28px;height:28px;border:3px solid #e2e8f0;border-top-color:#3b82f6;border-radius:50%;animation:mcp-spin .7s linear infinite; }}
      @keyframes mcp-spin {{ to {{ transform: rotate(360deg); }} }}
      .mcp-err {{ margin:24px;padding:20px;background:#fef2f2;color:#b91c1c;border:1px solid #fca5a5;border-left:4px solid #ef4444;border-radius:8px;font-size:14px; }}
      .mcp-json {{ padding:24px;max-width:960px;margin:0 auto; }}
      .mcp-json pre {{ background:#1e293b;color:#e2e8f0;padding:20px;border-radius:8px;font-size:12.5px;overflow:auto;max-height:80vh; }}
      #mcp-err-overlay {{ display:none;position:fixed;inset:0;z-index:9999;background:rgba(10,17,32,.97);color:#f1f5f9;overflow:auto;padding:40px 32px;font-family:monospace;font-size:13px; }}
      #mcp-err-overlay h2 {{ color:#f87171;font-size:18px;margin:0 0 16px; }}
      #mcp-err-overlay pre {{ background:rgba(239,68,68,.07);border:1px solid rgba(239,68,68,.25);padding:16px;border-radius:8px;white-space:pre-wrap;color:#fca5a5;max-height:50vh;overflow:auto; }}
      #mcp-err-overlay button {{ margin-top:16px;padding:8px 20px;background:#1e293b;color:#94a3b8;border:1px solid #334155;border-radius:6px;cursor:pointer;font-size:13px; }}
    </style>
    </head>
    <body>

    <div id="mcp-root">
      <div class="mcp-loading"><div class="mcp-spin"></div>Starting app&hellip;</div>
    </div>

    <div id="mcp-err-overlay">
      <h2>&#9888; App Error</h2>
      <pre id="mcp-err-msg">Unknown error</pre>
      <button onclick="document.getElementById('mcp-err-overlay').style.display='none';document.getElementById('mcp-root').style.display='';">Dismiss</button>
    </div>

    <script>
    // ── Odoo data bridge
    window.odoo = {{
      appName: {name_js},
      dataUrl: {json.dumps(data_url)},
      hasData: {has_data_js},
      portal: {portal_js},
      fetch: async function(params) {{
        if (!window.odoo.hasData) return {{}};
        var r = await fetch(window.odoo.dataUrl, {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify(params || {{}})
        }});
        if (!r.ok) throw new Error("HTTP " + r.status);
        var d = await r.json();
        if (d && d.error) throw new Error(d.error + (d.error_detail ? "\\n\\n" + d.error_detail : ""));
        if (d) delete d.__meta;
        return d || {{}};
      }}
    }};

    // ── Error overlay
    window.__mcpError = function(title, detail) {{
      var el  = document.getElementById("mcp-err-overlay");
      var msg = document.getElementById("mcp-err-msg");
      var rt  = document.getElementById("mcp-root");
      if (el)  el.style.display = "block";
      if (msg) msg.textContent  = title + (detail ? "\\n\\n" + detail : "");
      if (rt)  rt.style.display = "none";
    }};
    window.addEventListener("error", function(ev) {{
      if (ev.error) window.__mcpError(ev.error.message || String(ev.error), ev.error.stack || "");
      else if (ev.message) window.__mcpError(ev.message, "");
    }});
    window.addEventListener("unhandledrejection", function(ev) {{
      var r = ev.reason;
      window.__mcpError("Promise error: " + (r && r.message ? r.message : String(r || "")), r && r.stack ? r.stack : "");
    }});

    // ── React hooks shorthand injected into global scope so user code can call useState() directly
    var useState      = React.useState;
    var useEffect     = React.useEffect;
    var useRef        = React.useRef;
    var useCallback   = React.useCallback;
    var useMemo       = React.useMemo;
    var useContext    = React.useContext;
    var useReducer    = React.useReducer;
    var createContext = React.createContext;
    var Fragment      = React.Fragment;
    var forwardRef    = React.forwardRef;
    var memo          = React.memo;
    </script>

    <script>
    // ── JSX Transform + Mount
    // All libs, React, Babel are loaded synchronously above — no timing issues
    try {{
      var __src = {app_code_json};
      var __out = Babel.transform(__src, {{
        presets: ["react"],
        plugins: []
      }}).code;

      // Wrap in IIFE so const/let stay scoped but App is accessible
      var __wrapped = "(function(){{\\n" + __out + "\\n" +
        "if(typeof App==='undefined'){{" +
        "  window.__mcpError('App is not defined'," +
        "  'Your jsx_code must define: function App(){{ return <div>Hello</div>; }}');" +
        "  return;" +
        "}}" +
        "class _EB extends React.Component{{" +
        "  constructor(p){{super(p);this.state={{err:null}};}}" +
        "  static getDerivedStateFromError(e){{return{{err:e}};}}" +
        "  componentDidCatch(e,i){{window.__mcpError('Runtime error: '+e.message,(i&&i.componentStack)||e.stack||'');}}" +
        "  render(){{" +
        "    if(this.state.err) return React.createElement('div',{{className:'mcp-err'}},this.state.err.message);" +
        "    return this.props.children;" +
        "  }}" +
        "}}" +
        "try{{" +
        "  ReactDOM.createRoot(document.getElementById('mcp-root')).render(" +
        "    React.createElement(_EB,null,React.createElement(App,null))" +
        "  );" +
        "}}catch(e){{window.__mcpError('Mount failed: '+e.message,e.stack||'');}}" +
        "}})();";

      (new Function(__wrapped))();
    }} catch(e) {{
      window.__mcpError("Babel compile error: " + e.message, e.stack || "");
    }}
    </script>

    </body>
    </html>"""

        return html

    @http.route('/mcp/portal/home', type='http', auth='none',
                methods=['GET'], csrf=False, save_session=True, website=True)
    def portal_home_redirect(self, **kw):
        uid = request.session.uid
        if not uid:
            return request.redirect('/web/login?redirect=/mcp/portal/home')
        try:
            user = request.env['res.users'].sudo().browse(uid)
            if user.has_group('base.group_portal'):
                return request.redirect(f"/mcp/app/{self._get_portal_home_slug()}")
        except Exception:
            pass
        return request.redirect('/my/home')

    @http.route('/my/home', type='http', auth='public',
                methods=['GET'], csrf=False, save_session=True, website=True)
    def mcp_my_home_override(self, **kw):
        try:
            uid = request.session.uid
            if uid:
                user = request.env['res.users'].sudo().browse(uid)
                if user.has_group('base.group_portal'):
                    return request.redirect(f"/mcp/app/{self._get_portal_home_slug()}")
        except Exception:
            pass
        return request.redirect('/my')

    @http.route('/mcp/app/<string:slug>', type='http', auth='none',
                methods=['GET'], csrf=False, save_session=False)
    def render_webapp(self, slug, **kw):
        app = request.env['mcp.webapp'].sudo().search(
            [('slug', '=', slug), ('active', '=', True)], limit=1)
        env, user, access_mode, err = self._resolve_public_record_access(
            app, html=True, route_name='render_webapp')
        if err:
            return err
        html = self._build_webapp_html(app, data_url=f"/mcp/app/{slug}/data")
        return Response(html, status=200, mimetype='text/html',
                        headers={'Cache-Control': 'no-store, no-cache, must-revalidate'})

    @http.route('/mcp/app/public/<int:rec_id>/<string:token>', type='http', auth='none',
                methods=['GET'], csrf=False, save_session=False)
    def render_webapp_public(self, rec_id, token, **kw):
        app = request.env['mcp.webapp'].sudo().browse(rec_id)
        env, user, access_mode, err = self._resolve_public_record_access(
            app, share_token=token, html=True, route_name='render_webapp_public')
        if err:
            return err
        html = self._build_webapp_html(app, data_url=f"/mcp/app/public/{rec_id}/{token}/data")
        return Response(html, status=200, mimetype='text/html',
                        headers={'Cache-Control': 'no-store, no-cache, must-revalidate'})

    @http.route('/mcp/app/<string:slug>/data', type='http', auth='none',
                methods=['GET', 'POST', 'OPTIONS'], csrf=False, save_session=False)
    def webapp_data(self, slug, **kw):
        if request.httprequest.method == 'OPTIONS':
            return Response('', status=200, headers={
                'Access-Control-Allow-Origin':  '*',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            })
        app = request.env['mcp.webapp'].sudo().search(
            [('slug', '=', slug), ('active', '=', True)], limit=1)
        env, user, access_mode, err = self._resolve_public_record_access(
            app, route_name='webapp_data')
        if err:
            return err
        if not app.data_code or not app.data_code.strip():
            return _json_response({})

        req_params = {}
        try:
            raw = request.httprequest.data
            if raw:
                req_params = json.loads(raw.decode('utf-8'))
        except Exception:
            pass

        # ── Portal user resolution ─────────────────────────────────────────
        _sess_uid = request.session.uid
        _portal_uid, _portal_partner_id, _portal_name = None, None, ''
        if _sess_uid:
            try:
                _u = request.env['res.users'].sudo().browse(_sess_uid)
                _portal_uid        = _sess_uid
                _portal_partner_id = _u.partner_id.id if _u.partner_id else None
                _portal_name       = _u.name or ''
            except Exception:
                pass

        globs           = _build_safe_globals(env)
        globs['params']            = req_params
        globs['portal_uid']        = _portal_uid
        globs['portal_partner_id'] = _portal_partner_id
        globs['portal_name']       = _portal_name
        locs            = {'result': {}}
        start           = time.monotonic()
        try:
            mcp_exec(app.data_code, globs, locs)
            dur    = round((time.monotonic() - start) * 1000)
            result = locs.get('result') or {}
            if not isinstance(result, dict):
                result = {'data': result}
            result['__meta'] = {'duration_ms': dur, 'ok': True}
            return _json_response(result)
        except Exception as exc:
            dur = round((time.monotonic() - start) * 1000)
            tb_str = traceback.format_exc()
            _logger.error("webapp data_code [%s]: %s", slug, tb_str)
            _log(env, tool='webapp_data', operation='webapp',
                 user=user,
                 log_level='error', state='error', error=exc,
                 tb=tb_str, duration_ms=dur,
                 payload={'slug': slug})
            return _json_response({
                'error':        str(exc),
                'error_detail': tb_str,
                '__meta':       {'duration_ms': dur, 'ok': False},
            }, 500)

    @http.route('/mcp/app/public/<int:rec_id>/<string:token>/data', type='http', auth='none',
                methods=['GET', 'POST', 'OPTIONS'], csrf=False, save_session=False)
    def webapp_data_public(self, rec_id, token, **kw):
        if request.httprequest.method == 'OPTIONS':
            return Response('', status=200, headers={
                'Access-Control-Allow-Origin':  '*',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            })
        app = request.env['mcp.webapp'].sudo().browse(rec_id)
        env, user, access_mode, err = self._resolve_public_record_access(
            app, share_token=token, route_name='webapp_data_public')
        if err:
            return err
        if not app.data_code or not app.data_code.strip():
            return _json_response({})

        req_params = {}
        try:
            raw = request.httprequest.data
            if raw:
                req_params = json.loads(raw.decode('utf-8'))
        except Exception:
            pass

        globs = _build_safe_globals(env)
        globs['params'] = req_params
        globs['portal_uid'] = None
        globs['portal_partner_id'] = None
        globs['portal_name'] = ''
        locs = {'result': {}}
        start = time.monotonic()
        try:
            mcp_exec(app.data_code, globs, locs)
            dur = round((time.monotonic() - start) * 1000)
            result = locs.get('result') or {}
            if not isinstance(result, dict):
                result = {'data': result}
            result['__meta'] = {'duration_ms': dur, 'ok': True}
            return _json_response(result)
        except Exception as exc:
            dur = round((time.monotonic() - start) * 1000)
            tb_str = traceback.format_exc()
            _logger.error("webapp public data_code [%s]: %s", rec_id, tb_str)
            _log(env, tool='webapp_data', operation='webapp',
                 user=user, log_level='error', state='error', error=exc,
                 tb=tb_str, duration_ms=dur,
                 payload={'rec_id': rec_id})
            return _json_response({
                'error':        str(exc),
                'error_detail': tb_str,
                '__meta':       {'duration_ms': dur, 'ok': False},
            }, 500)
