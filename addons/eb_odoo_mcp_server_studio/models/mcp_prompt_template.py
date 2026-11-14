# -*- coding: utf-8 -*-
"""
Prompt templates with {{variable}} placeholders — stored in DB, exposed to MCP clients.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError



class McpPromptTemplate(models.Model):
    _name = 'mcp.prompt.template'
    _description = 'MCP Prompt Template'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True, index=True,
                       help='Unique identifier for MCP client (e.g. create_echart).')
    description = fields.Char(string='Description', required=True,
                              help='Short description shown in AI client.')
    prompt_text = fields.Text(string='Prompt Text', required=True,
                              help='Use {{variable}} for arguments. Example: Create {{description}} for {{model}}.')
    sequence = fields.Integer(string='Sequence', default=10)
    visibility = fields.Selection([
        ('private', 'Private'),
        ('shared', 'Shared'),
        ('public', 'Public'),
    ], string='Visibility', default='public',
       help='Private: only you. Shared: selected users. Public: all MCP users.')
    user_ids = fields.Many2many(
        'res.users',
        'mcp_prompt_template_user_rel',
        'template_id',
        'user_id',
        string='Shared With',
        help='Users who can see this template when visibility is Shared.'
    )
    active = fields.Boolean(default=True)
    argument_ids = fields.One2many(
        'mcp.prompt.template.argument',
        'template_id',
        string='Arguments',
        help='Define required/optional arguments with descriptions.'
    )

    @api.constrains('name')
    def _check_unique_name(self):
        for record in self:
            if record.name:
                existing = self.search([
                    ('name', '=', record.name),
                    ('id', '!=', record.id)
                ], limit=1)

                if existing:
                    raise ValidationError("Template name must be unique.")

    @api.model
    def get_prompts_for_user(self, user_id):
        """Return list of prompts visible to the given user.
        Always called with sudo() from the controller since the MCP
        endpoint runs as auth='none' (public user). Visibility
        is enforced here via domain, not via ORM ACLs.
        """
        domain = [
            ('active', '=', True),
            '|', '|',
            ('visibility', '=', 'public'),
            '&', ('visibility', '=', 'shared'), ('user_ids', 'in', [user_id]),
            '&', ('visibility', '=', 'private'), ('create_uid', '=', user_id),
        ]
        templates = self.sudo().search(domain, order='sequence, name')
        result = []
        for t in templates:
            args = []
            for a in t.argument_ids:
                arg_entry = {
                    'name': a.name,
                    'description': a.description or '',
                    'required': a.required,
                }
                if a.default_value:
                    arg_entry['default'] = a.default_value
                args.append(arg_entry)

            # MCP spec requires at least one argument for the prompt to show argument inputs
            if not args:
                args = [{'name': 'description', 'description': 'What do you want to do?', 'required': False}]

            result.append({
                'name': t.name,
                'description': t.description,
                'arguments': args,
            })
        return result

    def render_for(self, arguments):
        """Replace {{var}} placeholders with values from arguments dict."""
        text = self.prompt_text or ''
        for k, v in (arguments or {}).items():
            text = text.replace('{{' + str(k) + '}}', str(v))
        return text
