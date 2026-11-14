# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectApprovalRole(models.Model):
    _name = 'project.approval.role'
    _description = 'Project Approval Role'
    _rec_name = 'name'

    name = fields.Char(string='Role Name', required=True)
    dept = fields.Char(string='Department')
