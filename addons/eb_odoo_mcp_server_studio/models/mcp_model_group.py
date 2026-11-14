# -*- coding: utf-8 -*-
"""
Model restriction groups — block AI access to specific models/fields per CRUD operation.
Applies to: list_models, get_model_schema, search_read, read_record, read_group,
            create_record, update_record, delete_record, execute_method.
Does NOT restrict: execute_orm, create_echart, manage_webapp, manage_module.
"""
from odoo import api, fields, models


class McpModelGroup(models.Model):
    _name = 'mcp.model.group'
    _description = 'MCP Model Restriction Group'

    name = fields.Char(string='Name', required=True)
    user_ids = fields.Many2many(
        'res.users',
        'mcp_model_group_user_rel',
        'group_id',
        'user_id',
        string='Apply to Users',
        help='Leave empty to apply to all MCP users.'
    )
    line_ids = fields.One2many(
        'mcp.model.group.line',
        'group_id',
        string='Restricted Models',
    )
    active = fields.Boolean(default=True)
    description = fields.Text(
        string='Description',
        help='Describe what this restriction group is for.',
    )

    # ── Computed counts for display ──────────────────────────────────────
    model_count = fields.Integer(
        compute='_compute_counts', string='Models',
    )
    field_count = fields.Integer(
        compute='_compute_counts', string='Fields',
    )

    @api.depends('line_ids', 'line_ids.field_ids')
    def _compute_counts(self):
        for rec in self:
            rec.model_count = len(rec.line_ids)
            rec.field_count = sum(len(l.field_ids) for l in rec.line_ids)

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

class McpModelGroupLine(models.Model):
    _name = 'mcp.model.group.line'
    _description = 'Model Restriction Line'

    group_id = fields.Many2one('mcp.model.group', required=True, ondelete='cascade', index=True)
    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    model_name = fields.Char(
        related='model_id.model', string='Technical Name', store=True, readonly=True,
    )
    block_read = fields.Boolean(string='Block Read', default=False)
    block_create = fields.Boolean(string='Block Create', default=False)
    block_write = fields.Boolean(string='Block Update', default=False)
    block_unlink = fields.Boolean(string='Block Delete', default=False)
    block_execute = fields.Boolean(string='Block Execute Method', default=False)
    field_ids = fields.One2many(
        'mcp.model.field.restriction',
        'line_id',
        string='Field Restrictions',
    )

class McpModelFieldRestriction(models.Model):
    _name = 'mcp.model.field.restriction'
    _description = 'Field Restriction (hide from AI)'
    _rec_name = 'field_id'

    line_id = fields.Many2one(
        'mcp.model.group.line',
        required=True,
        ondelete='cascade',
        readonly=True,
        index=True,
    )

    # Stored so field_id domain works correctly in the view
    model_id = fields.Many2one(
        'ir.model',
        related='line_id.model_id',
        store=True,
        readonly=True,
        index=True,
        string='Model',
    )

    # ── Field selection: proper Many2one instead of raw Char ─────────────
    field_id = fields.Many2one(
        'ir.model.fields',
        string='Field',
        required=True,
        ondelete='cascade',
        domain="[('model_id', '=', model_id)]",
        help='Select the field to restrict from AI access.',
    )

    # Computed from field_id for backward compat & quick lookups
    field_name = fields.Char(
        related='field_id.name', string='Field Name', store=True, readonly=True,
    )
    field_description = fields.Char(
        related='field_id.field_description', string='Label', readonly=True,
    )
    field_type = fields.Selection(
        related='field_id.ttype', string='Type', readonly=True,
    )

    # ── CRUD block toggles ───────────────────────────────────────────────
    block_read = fields.Boolean(string='Block Read', default=True,
                                help='Hide this field from search_read, get_record, get_fields responses.')
    block_create = fields.Boolean(string='Block Create', default=True,
                                  help='Prevent AI from setting this field in create operations.')
    block_write = fields.Boolean(string='Block Write', default=True,
                                 help='Prevent AI from updating this field.')

    _unique_field_per_line = models.Constraint(
        'UNIQUE(line_id, field_id)',
        'Each field can only be restricted once per model line.'
    )