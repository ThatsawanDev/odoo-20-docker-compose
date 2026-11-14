# in mcp_token.py
from datetime import timedelta

from odoo import api, fields, models

class McpApiToken(models.Model):
    _name = 'mcp.api.token'
    _description = 'MCP API Token'

    name        = fields.Char(required=True)
    token       = fields.Char(index=True, readonly=True)
    refresh_token = fields.Char(index=True, readonly=True)
    user_id     = fields.Many2one('res.users', required=True, ondelete='cascade')
    expires_at  = fields.Datetime(
        string='Expires At',
        help='Access token expiry. Requests using this bearer token are rejected after this time.',
    )
    refresh_expires_at = fields.Datetime(
        string='Refresh Expires At',
        help='Refresh token expiry. After this time, the refresh token can no longer mint new access tokens.',
    )
    scope = fields.Char(
        string='Granted Scope',
        help='OAuth scopes granted to this token. Legacy/manual tokens may be blank.',
    )
    audience = fields.Char(
        string='Audience',
        help='OAuth resource indicator bound to this token.',
    )
    client_id = fields.Char(
        string='OAuth Client ID',
        help='Registered OAuth client that this token was issued for.',
    )
    active      = fields.Boolean(default=True)

    mcp_client = fields.Selection(
        selection=[
            ('chatgpt_web', 'Chat GPT Web'),
            ('claude_web', 'Claude Web'),
            ('gemini_cli', 'Gemini CLI'),
            ('claude_code_cli', 'Claude Code CLI'),
            ('claude_desktop', 'Claude Desktop'),
        ],
        string="MCP Client",
        default='chatgpt_web'
    )
    connector_url = fields.Char(
        string="Connection URL", compute="_compute_connector_url", help="Use this URL in claude_desktop_config.json",
    )

    @api.depends("token", "mcp_client")
    def _compute_connector_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_str("web.base.url", "")
        url_map = {
            'claude_desktop':   '/claude_desktop/auth',
            'claude_web':       '/mcp/v1',
            'claude_code_cli':  '/mcp/v1',
            'gemini_cli':       '/gemini_cli/auth',
            'chatgpt_web':      '/mcp/v1',
        }
        for rec in self:
            path = url_map.get(rec.mcp_client, '/mcp/v1')
            rec.connector_url = f"{base_url}{path}" if base_url else ""

    @api.model_create_multi
    def create(self, vals_list):
        import secrets

        config = self.env['mcp.config'].sudo().get_config()
        access_hours = max(int(config.access_token_timeout_hours or 24), 1)
        refresh_days = max(int(config.refresh_token_timeout_days or 30), 1)
        now = fields.Datetime.now()

        for vals in vals_list:
            if not vals.get('token'):
                vals['token'] = secrets.token_urlsafe(32)

            if not vals.get('refresh_token'):
                vals['refresh_token'] = secrets.token_urlsafe(48)

            if not vals.get('expires_at'):
                vals['expires_at'] = now + timedelta(hours=access_hours)

            if not vals.get('refresh_expires_at'):
                vals['refresh_expires_at'] = now + timedelta(days=refresh_days)

        return super().create(vals_list)

    @api.model
    def _user_has_mcp_access(self, user):
        if not user:
            return False
        try:
            if user.has_group('eb_odoo_mcp_server_studio.group_mcp_user'):
                return True
            if user.has_group('eb_odoo_mcp_server_studio.group_mcp_admin'):
                return True
            if user.has_group('base.group_system'):
                return True
        except Exception:
            return False
        return False

    def _invalidate(self):
        self.sudo().write({'active': False})
        return self.browse()

    @api.model
    def resolve_access_token(self, raw_token, expected_audience=''):
        rec = self.sudo().search([
            ('token', '=', raw_token),
            ('active', '=', True),
        ], limit=1)
        if not rec:
            return self.browse()
        now = fields.Datetime.now()
        if rec.expires_at and now > rec.expires_at:
            return rec._invalidate()
        if rec.audience and expected_audience and rec.audience.rstrip('/') != expected_audience.rstrip('/'):
            return rec._invalidate()
        if not self._user_has_mcp_access(rec.user_id):
            return rec._invalidate()
        return rec

    def authenticate(self, raw_token):
        rec = self.resolve_access_token(raw_token)
        if not rec:
            return None
        return rec.user_id

    @api.model
    def resolve_refresh_token(self, raw_refresh_token):
        rec = self.sudo().search([
            ('refresh_token', '=', raw_refresh_token),
            ('active', '=', True),
        ], limit=1)
        if not rec:
            return self.browse()
        now = fields.Datetime.now()
        if rec.refresh_expires_at and now > rec.refresh_expires_at:
            return rec._invalidate()
        if not self._user_has_mcp_access(rec.user_id):
            return rec._invalidate()
        return rec

    def authenticate_refresh(self, raw_refresh_token):
        return self.resolve_refresh_token(raw_refresh_token)
