from odoo import models, fields


class ProjectApprover(models.Model):
    _name = 'project.approver'
    _description = 'Project Approver'

    project_id = fields.Many2one('project.project', string='Project', ondelete='cascade')
    user_id = fields.Many2one('res.users', string='User', required=True)
    approve = fields.Boolean(string='Approve')
