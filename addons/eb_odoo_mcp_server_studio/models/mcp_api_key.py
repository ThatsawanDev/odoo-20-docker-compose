# -*- coding: utf-8 -*-
"""
API keys for webapp endpoint handlers — store third-party keys (Anthropic, OpenAI, etc.)
Restricted to MCP admins; webapp code accesses via env['mcp.api.key'].
"""
from odoo import fields, models


class McpApiKey(models.Model):
    _name = 'mcp.api.key'
    _description = 'MCP API Key (for Webapp Endpoints)'

    name = fields.Char(string='Label', required=True, help='e.g. Anthropic API Key')
    key_value = fields.Char(string='Key', required=True)
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')