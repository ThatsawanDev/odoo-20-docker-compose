# -*- coding: utf-8 -*-
from attr import field

from odoo import _, api, fields, models


class ProjectApprovalTeamLine(models.Model):
    _name = 'project.approval.team.line'
    _description = 'Project Approval Team Member'

    approval_id = fields.Many2one('project.approval.signoff', ondelete='cascade')
    role_id = fields.Many2one('project.approval.role', string='Role')
    department = fields.Char(string='Dept')
    user_id = fields.Many2one('res.users', string='Name')
    dept_id = fields.Many2one('hr.department', string='Department')
    description = fields.Text("Description")

    @api.onchange('role_id')
    def _onchange_role_id(self):
        self.department = self.role_id.dept if self.role_id else False
        self.user_id = False
