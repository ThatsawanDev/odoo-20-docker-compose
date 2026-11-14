# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectSize(models.Model):
    _name = 'project.size'
    _description = 'Project Size'
    _rec_name = 'name'
    _order = 'sequence, name'

    name = fields.Char(string='Size Name', required=True)
    sequence = fields.Integer(default=10)
    manday_start = fields.Integer("Manday Start")
    manday_end = fields.Integer("Manday End")
    display_name = fields.Char(compute='_compute_display_name', store=True)

    active = fields.Boolean(default=True)

    @api.depends('name', 'manday_start', 'manday_end')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.name} ({rec.manday_start} - {rec.manday_end})"
