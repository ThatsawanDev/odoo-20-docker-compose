# -*- coding: utf-8 -*-
"""
Per-tool allowlists — Write and Execute tools require explicit user membership.
Read tools are auto-enabled for all MCP users.
"""
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class McpToolAllowlist(models.Model):
    _name = 'mcp.tool.allowlist'
    _description = 'MCP Tool Allowlist'
    _rec_name = 'tool_name'

    tool_name = fields.Char(string='Tool Name', required=True, index=True)
    tool_category = fields.Selection([
        ('read', 'Read'),
        ('write', 'Write'),
        ('code', 'Code'),
        ('execute', 'Execute'),
    ], string='Category', required=True)
    user_ids = fields.Many2many(
        'res.users',
        'mcp_tool_allowlist_user_rel',
        'allowlist_id',
        'user_id',
        string='Allowed Users',
        help='Users who can execute this tool. MCP Admin bypasses allowlist.'
    )

    @api.constrains('tool_name')
    def _check_unique_tool_name(self):
        for record in self:
            if record.tool_name:
                existing = self.search([
                    ('tool_name', '=', record.tool_name),
                    ('id', '!=', record.id)
                ], limit=1)

                if existing:
                    raise ValidationError("Tool already has an allowlist entry.")
