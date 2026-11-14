# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectApprovalBusinessImpact(models.Model):
    _name = 'project.approval.business.impact'
    _description = 'Project Approval Business Impact'
    _order = 'id'

    signoff_id = fields.Many2one(
        comodel_name='project.approval.signoff',
        required=True,
        ondelete='cascade',
    )
    dept_id = fields.Many2one(
        comodel_name='hr.department',
        string='Department',
    )
    user_id = fields.Many2one('res.users', string='Stake holder')
    change_impact_description = fields.Text(string='Change to Impact Description')
