# -*- coding: utf-8 -*-
from odoo import fields, models


class McpPromptTemplateArgument(models.Model):
    _name = 'mcp.prompt.template.argument'
    _description = 'Prompt Template Argument'
    _order = 'sequence, id'

    template_id = fields.Many2one('mcp.prompt.template', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Variable Name', required=True,
                       help='Matches {{name}} in the prompt text.')
    description = fields.Char(string='Label / Description',
                              help='Description shown to the user in the AI client argument input.')
    required = fields.Boolean(string='Required', default=True,
                              help='If checked, the AI client marks this field as mandatory.')
    default_value = fields.Char(string='Default Value',
                                help='Pre-filled value shown in the AI client. Leave empty for no default.')
