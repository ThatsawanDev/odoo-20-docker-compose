# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectApprovalSettings(models.Model):
    _name = 'project.approval.settings'
    _description = 'Project Approval Settings'

    auto_assign_user_id = fields.Many2one(
        'res.users',
        string='Auto Assign User (In Review)',
    )
    auto_assign_it_head_user_id = fields.Many2one(
        'res.users',
        string='Auto Assign User (IT Head Approval)',
    )
    send_assignment_email = fields.Boolean(
        string='Send Email on Assignment',
        default=True,
    )
    send_assignment_teams = fields.Boolean(
        string='Send MS Teams on Assignment',
        default=True,
    )
    send_requester_notification = fields.Boolean(
        string='Send Email to Requester on Status Update',
        default=True,
    )
    ms_team_project_request = fields.Char(
        string='MS Teams Webhook URL (Project Request)',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ICP = self.env['ir.config_parameter'].sudo()

        user_id = ICP.get_str('crd_project_approval.auto_assign_user_id')
        if user_id and str(user_id).isdigit():
            res['auto_assign_user_id'] = int(user_id)

        it_head_id = ICP.get_str('crd_project_approval.auto_assign_it_head_user_id')
        if it_head_id and str(it_head_id).isdigit():
            res['auto_assign_it_head_user_id'] = int(it_head_id)

        res['send_assignment_email'] = (
            ICP.get_str('crd_project_approval.send_assignment_email', default='True') != 'False'
        )
        res['send_assignment_teams'] = (
            ICP.get_str('crd_project_approval.send_assignment_teams', default='True') != 'False'
        )
        res['send_requester_notification'] = (
            ICP.get_str('crd_project_approval.send_requester_notification', default='True') != 'False'
        )
        res['ms_team_project_request'] = ICP.get_str('setting.ms_team_project_request', default='')

        return res

    def write(self, vals):
        result = super().write(vals)
        self._sync_to_icp()
        return result

    def _sync_to_icp(self):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_str('crd_project_approval.auto_assign_user_id', self.auto_assign_user_id.id or '')
        ICP.set_str('crd_project_approval.auto_assign_it_head_user_id', self.auto_assign_it_head_user_id.id or '')
        ICP.set_str('crd_project_approval.send_assignment_email', 'True' if self.send_assignment_email else 'False')
        ICP.set_str('crd_project_approval.send_assignment_teams', 'True' if self.send_assignment_teams else 'False')
        ICP.set_str('crd_project_approval.send_requester_notification', 'True' if self.send_requester_notification else 'False')
        ICP.set_str('setting.ms_team_project_request', self.ms_team_project_request or '')

    @api.model
    def action_open_settings(self):
        self.sudo().search([]).unlink()
        record = self.sudo().create({})
        return {
            'type': 'ir.actions.act_window',
            'name': 'Project Approval Settings',
            'res_model': self._name,
            'res_id': record.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_save(self):
        self.ensure_one()
        return self.action_open_settings()
