# -*- coding: utf-8 -*-
from odoo import fields, models

class ProjectApprovalFeatureImpact(models.Model):
    _name = 'project.approval.feature.impact'
    _description = 'Project Approval Feature Impact'
    _order = 'id'

    signoff_id = fields.Many2one(
        comodel_name='project.approval.signoff',
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(string='Key Features & Function Impact')
