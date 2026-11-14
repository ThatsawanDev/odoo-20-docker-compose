# -*- coding: utf-8 -*-
"""
MCP Studio Configuration — singleton settings for server, tokens, logging, security, and tool allowlists.
"""
from odoo import api, fields, models


class McpConfig(models.Model):
    _name = 'mcp.config'
    _description = 'MCP Server Configuration'

    name = fields.Char(required=True, default='MCP Config')

    # ── Server ───────────────────────────────────────────────────────────
    server_enabled = fields.Boolean(string='MCP Server Enabled', default=True)
    access_token_timeout_hours = fields.Integer(
        string='Access Token Timeout (hours)',
        default=24,
        help='Access token validity in hours.'
    )
    refresh_token_timeout_days = fields.Integer(
        string='Refresh Token Timeout (days)',
        default=30,
        help='Refresh token validity in days (OAuth).'
    )
    log_retention_days = fields.Integer(
        string='Log Retention (days)',
        default=90,
        help='Keep execution logs for this many days. Set 0 to disable auto-cleanup.'
    )
    log_full_payload = fields.Boolean(
        string='Log Full Payload',
        default=False,
        help='Store full request/response in logs (may contain sensitive data).'
    )
    # Expose EChart data in tool response (for AI iteration) — disabled = data stays on server
    expose_echart_data_in_response = fields.Boolean(
        string='Expose EChart Data in Tool Response',
        default=False,
        help='If disabled, AI agents only generate dashboard code; data never leaves your server.'
    )

    # ── Tool limits ───────────────────────────────────────────────────────
    code_execute_limit = fields.Integer(
        string='Code Execute Limit (lines)',
        default=10000,
        help='Max lines allowed in execute_orm code.'
    )
    code_search_limit = fields.Integer(
        string='Code Search Limit (results)',
        default=5000,
        help='Max results returned by code_search.'
    )

    # ── Security: IP Restrictions ────────────────────────────────────────
    ip_whitelist = fields.Text(
        string='IP Whitelist',
        help='Comma-separated IP addresses or CIDR ranges that are ALLOWED to access MCP. '
             'Leave empty to allow all IPs. Example: 192.168.1.0/24, 10.0.0.5'
    )
    ip_blacklist = fields.Text(
        string='IP Blacklist',
        help='Comma-separated IP addresses or CIDR ranges that are BLOCKED from MCP. '
             'Blacklist is checked before whitelist. Example: 1.2.3.4, 5.6.7.0/24'
    )

    # ── Security: Rate Limiting ──────────────────────────────────────────
    rate_limit_enabled = fields.Boolean(
        string='Rate Limiting',
        default=False,
        help='Limit the number of MCP tool calls per minute per user.'
    )
    rate_limit_per_minute = fields.Integer(
        string='Requests/Minute',
        default=60,
        help='Maximum tool calls per user per minute. Set 0 for unlimited.'
    )

    # ── Security: Sensitive Data ─────────────────────────────────────────
    mask_sensitive_in_logs = fields.Boolean(
        string='Mask Sensitive Fields in Logs',
        default=False,
        help='Mask values of restricted fields in audit logs. '
             'Fields marked in Model Restriction Groups will show as [RESTRICTED] in logs.'
    )

    # ── Computed: Live endpoint URL ──────────────────────────────────────
    connector_url = fields.Char(
        string='MCP Server Endpoint',
        compute='_compute_connector_url',
        help='Full MCP protocol endpoint URL. Share this with your AI clients.'
    )

    # ── Computed: Related records ────────────────────────────────────────
    oauth_client_ids = fields.One2many(
        'mcp.oauth.client', string='OAuth Clients',
        compute='_compute_oauth_clients',
    )
    oauth_client_count = fields.Integer(
        compute='_compute_oauth_clients', string='OAuth Clients Count',
    )
    api_token_ids = fields.One2many(
        'mcp.api.token', string='API Tokens',
        compute='_compute_api_tokens',
    )
    api_token_count = fields.Integer(
        compute='_compute_api_tokens', string='API Tokens Count',
    )

    # ── Computed: Security stat counts ───────────────────────────────────
    tool_allowlist_count = fields.Integer(
        compute='_compute_security_counts', string='Tool Allowlists',
    )
    model_restriction_count = fields.Integer(
        compute='_compute_security_counts', string='Model Restrictions',
    )
    field_restriction_count = fields.Integer(
        compute='_compute_security_counts', string='Field Restrictions',
    )
    prompt_template_count = fields.Integer(
        compute='_compute_security_counts', string='Prompt Templates',
    )

    @api.depends()
    def _compute_connector_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_str('web.base.url', '')
        url = (base_url.rstrip('/') + '/mcp/v1/') if base_url else '/mcp/v1/'
        for rec in self:
            rec.connector_url = url

    @api.depends()
    def _compute_oauth_clients(self):
        clients = self.env['mcp.oauth.client'].search([])
        for rec in self:
            rec.oauth_client_ids = clients
            rec.oauth_client_count = len(clients)

    @api.depends()
    def _compute_api_tokens(self):
        tokens = self.env['mcp.api.token'].search([('active', '=', True)])
        for rec in self:
            rec.api_token_ids = tokens
            rec.api_token_count = len(tokens)

    @api.depends()
    def _compute_security_counts(self):
        for rec in self:
            rec.tool_allowlist_count = self.env['mcp.tool.allowlist'].sudo().search_count([])
            rec.model_restriction_count = self.env['mcp.model.group'].sudo().search_count(
                [('active', '=', True)])
            rec.field_restriction_count = self.env['mcp.model.field.restriction'].sudo().search_count([])
            rec.prompt_template_count = self.env['mcp.prompt.template'].sudo().search_count(
                [('active', '=', True)])

    @api.model
    def get_config(self):
        """Return singleton config record (create default if missing)."""
        config = self.sudo().search([], limit=1)
        if not config:
            config = self.sudo().create({
                'server_enabled': True,
                'access_token_timeout_hours': 24,
                'refresh_token_timeout_days': 30,
                'log_retention_days': 90,
            })
        return config

    def action_open_config(self):
        """Open the config form (for menu)."""
        config = self.get_config()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mcp.config',
            'res_id': config.id,
            'view_mode': 'form',
            'target': 'current',
        }
