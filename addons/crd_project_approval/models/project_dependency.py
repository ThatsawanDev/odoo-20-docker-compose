# -*- coding: utf-8 -*-
import random
from odoo import fields, models


class ProjectDependency(models.Model):
    _name = 'project.dependency'
    _description = 'Project Dependency'
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    color = fields.Integer(default=lambda self: random.randint(0, 11))
