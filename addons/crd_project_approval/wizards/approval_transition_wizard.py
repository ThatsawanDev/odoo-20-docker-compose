# -*- coding: utf-8 -*-
from odoo import fields, models


class ApprovalTransitionWizard(models.TransientModel):
    _name = 'project.approval.transition.wizard'
    _description = 'Approval Transition Wizard'

    approval_id = fields.Many2one(
        'project.approval.signoff',
        required=True,
        ondelete='cascade',
    )
    action = fields.Char(required=True)
    reason = fields.Text()

    def action_confirm(self):
        method_map = {
            'submit': 'action_submit',
            'wait_for_approval': 'action_wait_for_approval',
            'it_head_approve': 'action_it_head_approve',
            'reject': 'action_reject',
            'cancel': 'action_cancel',
            'sponsor_approve': 'action_sponsor_approve',
            'sponsor_reject': 'action_sponsor_reject',
        }
        method_name = method_map.get(self.action)
        if method_name:
            getattr(
                self.approval_id.with_context(transition_reason=self.reason or ''),
                method_name,
            )()
        return {'type': 'ir.actions.act_window_close'}
