# -*- coding: utf-8 -*-
from odoo import models, fields


class StatusbarStateOption(models.Model):
    _name = 'statusbar.state.option'
    _description = 'Statusbar State Option'
    _rec_name = 'label'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    code = fields.Char(string='State Key', required=True)
    label = fields.Char(string='Label', required=True)
