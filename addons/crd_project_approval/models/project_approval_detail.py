# -*- coding: utf-8 -*-
import random
from odoo import fields, models


class ProjectApprovalDetail(models.Model):
    _name = 'project.approval.detail'
    _description = 'Project Approval Detail'
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(string='Detail', required=True)
    color = fields.Integer(default=lambda self: random.randint(0, 11))
