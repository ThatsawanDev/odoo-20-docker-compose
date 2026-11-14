# -*- coding: utf-8 -*-
import random
from odoo import fields, models


class ProjectRelatedSystem(models.Model):
    _name = 'project.related.system'
    _description = 'Project Related System'
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    color = fields.Integer(default=lambda self: random.randint(0, 11))
