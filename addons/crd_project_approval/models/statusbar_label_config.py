# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StatusbarLabelConfig(models.Model):
    _name = 'statusbar.label.config'
    _description = 'Statusbar Label Configuration'
    _order = 'model_id, target_state_id'

    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        domain=[('transient', '=', False)],
    )
    target_state_id = fields.Many2one(
        'statusbar.state.option',
        string='Target State',
        required=True,
        help='State to relabel when the trigger condition is met',
    )
    trigger_state_ids = fields.Many2many(
        'statusbar.state.option',
        'statusbar_label_config_trigger_rel',
        'config_id',
        'state_id',
        string='Trigger States',
        help='When current state is one of these, the target state label changes',
    )
    alternative_label = fields.Char(
        string='Alternative Label',
        required=True,
        help='Text to display instead of the original label when the rule triggers',
    )

    # Computed backward-compat fields — read by the JS widget
    model_name = fields.Char(compute='_compute_compat_fields', store=True)
    target_state = fields.Char(compute='_compute_compat_fields', store=True)
    trigger_states = fields.Char(compute='_compute_compat_fields', store=True)

    @api.depends('model_id', 'target_state_id', 'trigger_state_ids')
    def _compute_compat_fields(self):
        for rec in self:
            rec.model_name = rec.model_id.model or ''
            rec.target_state = rec.target_state_id.code or ''
            rec.trigger_states = ','.join(rec.trigger_state_ids.mapped('code'))
