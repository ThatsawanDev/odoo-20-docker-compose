# -*- coding: utf-8 -*-
"""OAuth 2.1 authorization codes for PKCE flow."""
import secrets
from odoo import api, fields, models


class McpOauthCode(models.Model):
    _name = 'mcp.oauth.code'
    _description = 'OAuth Authorization Code'

    code = fields.Char(required=True, index=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    client_id = fields.Char()
    redirect_uri = fields.Char()
    scope = fields.Char()
    resource = fields.Char()
    state = fields.Char()
    code_challenge = fields.Char()
    code_challenge_method = fields.Char(default='S256')
    expiry = fields.Datetime(required=True)
    consumed = fields.Boolean(default=False)

    @api.model
    def create_code(self, user_id, client_id, redirect_uri, scope, state,
                    code_challenge, code_challenge_method='S256', resource=''):
        from datetime import timedelta
        expiry = fields.Datetime.now() + timedelta(minutes=10)
        code = secrets.token_urlsafe(32)
        self.sudo().create({
            'code': code,
            'user_id': user_id,
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': scope or 'read write execute offline_access',
            'resource': resource or '',
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': code_challenge_method or 'S256',
            'expiry': expiry,
        })
        return code
