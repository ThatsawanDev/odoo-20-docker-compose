# -*- coding: utf-8 -*-
"""
OAuth 2.0 Dynamic Client Registration (RFC 7591).
Stores registered clients - ChatGPT and other MCP clients self-register to get client_id.
"""
import secrets
from odoo import api, fields, models


class McpOauthClient(models.Model):
    _name = 'mcp.oauth.client'
    _description = 'OAuth Client (Dynamic Registration)'

    client_id = fields.Char(required=True, index=True, readonly=True)
    client_secret = fields.Char(readonly=True)  # Empty for public clients
    client_name = fields.Char(string='Client Name')
    redirect_uris = fields.Text(string='Redirect URIs', help='One URI per line')
    grant_types = fields.Char(default='authorization_code refresh_token')
    response_types = fields.Char(default='code')
    scope = fields.Char(default='read write execute offline_access')
    token_endpoint_auth_method = fields.Char(default='none')  # none = public client
    active = fields.Boolean(default=True)

    @api.model
    def register_client(self, client_name, redirect_uris, scope=None, grant_types=None):
        """Create a new client and return client_id (RFC 7591)."""
        client_id = f"odoo-mcp-{secrets.token_urlsafe(16)}"
        if isinstance(redirect_uris, (list, tuple)):
            uris = [str(u).strip() for u in redirect_uris if u]
        else:
            uris = [r.strip() for r in str(redirect_uris or '').replace(',', '\n').split('\n') if r.strip()]
        vals = {
            'client_id': client_id,
            'client_name': client_name or 'MCP Client',
            'redirect_uris': '\n'.join(uris),
            'scope': scope or 'read write execute offline_access',
            'grant_types': grant_types or 'authorization_code refresh_token',
        }
        rec = self.sudo().create(vals)
        return {
            'client_id': rec.client_id,
            'client_secret': rec.client_secret or '',
            'client_id_issued_at': int(fields.Datetime.now().timestamp()),
            'redirect_uris': [u.strip() for u in rec.redirect_uris.split('\n') if u.strip()],
            'grant_types': rec.grant_types.split(),
            'scope': rec.scope,
            'token_endpoint_auth_method': rec.token_endpoint_auth_method,
        }

    @api.model
    def validate_client(self, client_id, redirect_uri=None):
        """Check client exists and redirect_uri is allowed."""
        rec = self.sudo().search([('client_id', '=', client_id), ('active', '=', True)], limit=1)
        if not rec:
            return False
        if not redirect_uri:
            return True
        allowed = [u.strip() for u in (rec.redirect_uris or '').split('\n') if u.strip()]
        if not allowed:
            return True  # Empty = allow any (e.g. odoo-mcp-public)
        if redirect_uri in allowed:
            return True
        for pat in allowed:
            if pat.endswith('*') and redirect_uri.startswith(pat.rstrip('*')):
                return True
        return False
