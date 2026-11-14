# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectApprovalHistory(models.Model):
    _name = 'project.approval.history'
    _description = 'Project Approval History'
    _rec_name = 'detail'
    _order = "id desc"
    approval_id = fields.Many2one(
        'project.approval.signoff',
        ondelete='cascade',
        required=True,
    )
    actor_id = fields.Many2one('res.users', string='Action By')
    detail = fields.Char(string='Detail')
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string='Waiting For')
    row_type = fields.Selection(
        selection=[
            ('action', 'Action'),
            ('waiting', 'Waiting For'),
            ('reassign', 'Reassign'),
        ],
        string='Type',
        required=True,
        default='action',
    )
    status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('done', 'Done'),
            ('rejected', 'Rejected'),
            ('reset', 'Reset'),
            ('cancelled', 'Cancelled'),
            ('auto_rejected', 'Auto Rejected'),
        ], string='Status')
    reason = fields.Text(string='Reason')
