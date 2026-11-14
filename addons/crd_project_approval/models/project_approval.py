# -*- coding: utf-8 -*-
import logging
import requests
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ProjectApprovalSignoff(models.Model):
    _name = 'project.approval.signoff'
    _description = 'Project Approval Sign-Off'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = "name desc"



    name = fields.Char(string='Request No.', required=True, default='New', copy=False)
    project_name = fields.Char(string='Project Name', required=True)
    business_owner = fields.Many2many(
        comodel_name='res.users',
        relation='project_approval_signoff_business_owner_rel',
        column1='signoff_id',
        column2='user_id',
        string='Business Owner',
        required=True,
    )
    business_sponsor_ids = fields.Many2many(
        comodel_name='res.users',
        relation='project_approval_signoff_business_sponsor_rel',
        column1='signoff_id',
        column2='user_id',
        required=True,
        string='Business Sponsor',
        default=lambda self: self._default_business_sponsor_ids(),
    )
    date_due = fields.Date(string='Date')
    requester_id = fields.Many2one(
        comodel_name='res.users',
        string='Requester By',
        default=lambda self: self.env.user,
    )
    date_request = fields.Date(string='Request Date', default=fields.Date.today)
    project_objective = fields.Text(string='Project Background & Objective',required=True)
    scope_pain_points = fields.Text(string='Scope / Pain Points',required=True)
    state = fields.Selection(
            selection=[
                ('draft', 'New'),
                ('in_review', 'Waiting IT Review'),
                ('wait_for_approval', 'Waiting for Biz Sponsor Approval'),
                ('wait_it_head_approval', 'Waiting IT Head Approval'),
                ('approved', 'Project Registered'),
                ('rejected', 'Project Rejected '),
                ('cancelled', 'Cancelled'),
            ],
            string='Status',
            default='draft',
            tracking=True,
        )




    #Business Impact
    is_legal_or_corporate_compliance = fields.Boolean(string='Is Legal or Corporate Compliance')
    legal_compliance_detail = fields.Char(string='Legal or Corporate Compliance')
    is_customer_satisfaction = fields.Boolean(string='Is Customer Satisfaction Impact')
    customer_satisfaction_detail = fields.Char(string='Customer Satisfaction Impact')
    is_corporate_reputaion = fields.Boolean(string='Is Corporate Reputation')
    corporate_reputation_detail = fields.Char(string='Corporate Reputation')
    is_productivity_improvement = fields.Boolean(string='Is Productivity Improvement')
    productivity_improvement_detail = fields.Char(string='Productivity Improvement')
    is_employee_engagement = fields.Boolean(string='Is Employee Engagement')
    employee_engagement_detail = fields.Char(string='Employee Engagement')
    is_exp_golive_date = fields.Boolean(string='Is Expected Go Live Date')
    exp_golive_date = fields.Char(string="Expected Go Live Date", tracking=True)


    #Financial Impact
    is_revenue_increasing = fields.Boolean(string='Revenue Increasing')
    revenue_increasing = fields.Char(string='Revenue Increasing')
    is_cost_decreasing_avoidance = fields.Boolean(string='Cost Decreasing/Avoidance')
    cost_decreasing_avoidance = fields.Char(string='Cost Decreasing Avoidance')



    #Technical Information
        #Technical Impact
    tech_impact = fields.Text(string='Technical Impact')
    related_systems = fields.Text(string='Related Systems')
    #Planning & Effort
    estimated_effort = fields.Char(string='Estimated Effort')
    project_size_id = fields.Many2one(
        comodel_name='project.size',
        string='Project Size',
        help='ขนาดโครงการตาม effort และความซับซ้อน เช่น S / M / L / XL',
    )
    date_timeline_start = fields.Date(string='Timeline Start')
    date_timeline_end = fields.Date(string='Timeline End')

    approver_ids = fields.Many2many(
        comodel_name='res.users',
        string='Assign Approvers',
    )

    bo_signature = fields.Binary(string='Business Owner Signature', attachment=True)
    bo_sign_date = fields.Date(string='BO Sign Date')
    sponsor_signature = fields.Binary(string='Project Sponsor Signature', attachment=True)
    sponsor_sign_date = fields.Date(string='Sponsor Sign Date')
    remark = fields.Text(string='Remark')
    # team_line_ids = fields.One2many('project.approval.team.line', 'approval_id', string='Project Team')
    history_ids = fields.One2many('project.approval.history', 'approval_id', string='History')
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        relation='project_approval_signoff_attachment_rel',
        column1='approval_id',
        column2='attachment_id',
        string='Additional Documents',
    )


    #Technical Information
    #Technical Impact
    assigne_user_id = fields.Many2many(
        comodel_name='res.users',
        relation='project_approval_signoff_assignee_rel',
        column1='approval_id',
        column2='user_id',
        string='Action By',
    )
    project_owner_id = fields.Many2one('res.users', string='Project Owner')

    technical_impact = fields.Text(string='Technical Impact')
    related_system = fields.Text(string='Related System')
    related_system_ids = fields.Many2many(
        comodel_name='project.related.system',
        relation='project_approval_signoff_related_system_rel',
        column1='signoff_id',
        column2='related_system_id',
        string='Related System',
    )
    dependency_ids = fields.Many2many(
        comodel_name='project.dependency',
        relation='project_approval_signoff_dependency_rel',
        column1='signoff_id',
        column2='dependency_id',
        string='Project Dependency',
    )
    detail_ids = fields.Many2many(
        comodel_name='project.approval.detail',
        relation='project_approval_signoff_detail_rel',
        column1='signoff_id',
        column2='detail_id',
        string='Tag',
    )
    business_impact_ids = fields.One2many(
        comodel_name='project.approval.business.impact',
        inverse_name='signoff_id',
        string='Business Impact',
    )
    feature_impact_ids = fields.One2many(
        comodel_name='project.approval.feature.impact',
        inverse_name='signoff_id',
        string='Key Features & Function Impact',
    )
    project_url = fields.Char(string='Project URL', readonly=True)

    is_editable = fields.Boolean(compute='_compute_is_editable')
    is_pending_sponsor_approver = fields.Boolean(
        string='Is Pending Sponsor Approver',
        compute='_compute_is_pending_sponsor_approver',
    )



    def _default_business_sponsor_ids(self):
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
        if employee and employee.coach_id and employee.coach_id.user_id:
            return [(6, 0, [employee.coach_id.user_id.id])]
        return False

    @api.onchange('estimated_effort', 'project_size_id')
    def _onchange_estimated_effort_check_range(self):
        if not self.project_size_id or not self.estimated_effort:
            return
        try:
            effort_value = float(self.estimated_effort)
        except (ValueError, TypeError):
            return
        size = self.project_size_id
        manday_start = size.manday_start or 0
        manday_end = size.manday_end or 0
        if manday_end and not (manday_start <= effort_value <= manday_end):
            return {
                'warning': {
                    'title': _('Estimated Effort Out of Range'),
                    'message': _(
                        'Estimated Effort (%(effort)s mandays) is outside the range of '
                        'Project Size "%(size)s" (%(start)s – %(end)s mandays).'
                    ) % {
                        'effort': effort_value,
                        'size': size.name,
                        'start': manday_start,
                        'end': manday_end,
                    },
                }
            }

    @api.depends('state')
    def _compute_is_editable(self):
        is_manager = self.env.user.has_group('base.group_erp_manager')
        for record in self:
            record.is_editable = (
                is_manager
                or record.state == 'draft'
                # wait_for_approval: assigne_user_id holds business_sponsor_ids
                # for display only (Action By column) — editing rights there
                # are governed by is_pending_sponsor_approver instead.
                or (
                    record.state != 'wait_for_approval'
                    and self.env.user in record.assigne_user_id
                )
            )

    @api.depends('approver_ids', 'history_ids.status', 'history_ids.user_id', 'history_ids.row_type')
    def _compute_is_pending_sponsor_approver(self):
        uid = self.env.user.id
        for record in self:
            record.is_pending_sponsor_approver = bool(
                uid in record.approver_ids.ids
                and record.history_ids.filtered(
                    lambda h: h.row_type == 'waiting'
                    and h.status == 'pending'
                    and h.user_id.id == uid
                )
            )

    def _close_pending_history(self, new_status):
        # Close every currently-pending 'waiting' history row for this
        # record, not just the single most recent one — the same pattern
        # already used by action_cancel, since a record can have more than
        # one pending row open concurrently (e.g. multi-approver voting).
        pending = self.env['project.approval.history'].search(
            [
                ('approval_id', '=', self.id),
                ('row_type', '=', 'waiting'),
                ('status', '=', 'pending'),
            ],
        )
        if pending:
            pending.write({'status': new_status})

    def _send_teams_notification(self, users=None):
        self.ensure_one()
        send_teams = self.env['ir.config_parameter'].sudo().get_str(
            'crd_project_approval.send_assignment_teams', default='True'
        )
        if send_teams == 'False':
            return
        webhook_url = self.env['ir.config_parameter'].sudo().get_str(
            'setting.ms_team_project_request'
        )
        if not webhook_url:
            return
        details = (
            f"Project Name: {self.project_name}\n"
            f"Business Owner: {', '.join(self.business_owner.mapped('name')) or '-'}\n"
            f"Business Sponsor: {', '.join(self.business_sponsor_ids.mapped('name')) or '-'}\n"
            f"Project Background & Objective: {self.project_objective or '-'}\n"
            f"Scope / Pain Points: {self.scope_pain_points or '-'}"
        )
        # `users` lets multi-approver steps (e.g. wait_for_approval) notify
        # every recipient instead of the assigne_user_id display value.
        # Falls back to assigne_user_id when omitted so existing
        # single-assignee call sites are unaffected.
        recipients = users if users is not None else self.assigne_user_id
        # Each recipient needs their own Teams approval card and their own
        # response, so send one webhook call per person instead of combining
        # every email into a single payload (which only ever registers one
        # person's decision on the Flow side).
        for recipient_email in filter(None, recipients.mapped('email')):
            payload = {
                'request_id': str(self.id),  # แก้ไขจุดนี้
                'request_name': self.name or "",
                'requester_emails': recipient_email,
                'view_url': self.get_base_url() + '/web#model=project.approval.signoff&id=' + str(self.id),
                'details': details,
            }
            try:
                response = requests.post(webhook_url, json=payload, timeout=10)
                self.env['api.log'].sudo().create_log(
                    model_name='project.approval.signoff',
                    method_name='_send_teams_notification',
                    body=payload,
                    url=webhook_url,
                    status=str(response.status_code),
                    error_message='' if response.ok else response.text,
                )
            except Exception as e:
                _logger.warning('MS Teams notification failed for %s: %s', self.name, e)
                self.env['api.log'].sudo().create_log(
                    model_name='project.approval.signoff',
                    method_name='_send_teams_notification',
                    body=payload,
                    url=webhook_url,
                    status='error',
                    error_message=str(e),
                )

    def _send_assignment_email(self, template_xml_id, users=None):
        self.ensure_one()
        send_email = self.env['ir.config_parameter'].sudo().get_str(
            'crd_project_approval.send_assignment_email', default='True'
        )
        if send_email == 'False':
            return
        template = self.env.ref(template_xml_id, raise_if_not_found=False)
        if not template:
            return
        # `users` lets multi-approver steps (e.g. wait_for_approval) notify
        # every recipient instead of just the assigne_user_id display value.
        # The template's own `email_to` still renders off
        # `object.assigne_user_id`, so each recipient's address is passed
        # via email_values to override it per send. When omitted, behavior
        # is unchanged for existing single-assignee call sites.
        if users is not None:
            for user in users:
                if not user.email:
                    continue
                template.send_mail(
                    self.id, email_values={'email_to': user.email}, force_send=False
                )
            return
        if not self.assigne_user_id:
            return
        template.send_mail(self.id, force_send=False)

    def _send_requester_notification(self):
        self.ensure_one()
        send_email = self.env['ir.config_parameter'].sudo().get_str(
            'crd_project_approval.send_requester_notification', default='True'
        )
        if send_email == 'False':
            return
        template = self.env.ref(
            'crd_project_approval.email_template_requester_notification',
            raise_if_not_found=False,
        )
        if not template or not self.requester_id.email:
            return
        template.send_mail(self.id, force_send=False)

    def _open_transition_wizard(self, action):
        label_map = {
            'submit': 'Submit',
            'wait_for_approval': 'Submit For Biz Approval',
            'approve': 'Submit for IT Head Approval',
            'it_head_approve': 'Approve',
            'reject': 'Reject',
            'cancel': 'Cancel',
            'sponsor_approve': 'Approve',
            'sponsor_reject': 'Reject',
        }
        return {
            'type': 'ir.actions.act_window',
            'name': label_map.get(action, 'Confirm'),
            'res_model': 'project.approval.transition.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_approval_id': self.id,
                'default_action': action,
            },
        }

    def action_submit_wizard(self):
        return self._open_transition_wizard('submit')

    def action_wait_for_approval_wizard(self):
        return self._open_transition_wizard('wait_for_approval')

    def action_it_head_approve_wizard(self):
        return self._open_transition_wizard('it_head_approve')

    def action_reject_wizard(self):
        return self._open_transition_wizard('reject')

    def action_cancel_wizard(self):
        return self._open_transition_wizard('cancel')

    def action_sponsor_approve_wizard(self):
        return self._open_transition_wizard('sponsor_approve')

    def action_sponsor_reject_wizard(self):
        return self._open_transition_wizard('sponsor_reject')

    def action_submit(self):
        vals = {'state': 'in_review'}
        auto_assign_param = self.env['ir.config_parameter'].sudo().get_str(
            'crd_project_approval.auto_assign_user_id'
        )
        assignee_id = None
        if auto_assign_param:
            try:
                assignee_id = int(auto_assign_param)
            except ValueError:
                pass
        if assignee_id is None:
            assignee_id = self.env.user.id
        # assigne_user_id is Many2many: wrap the resolved plain id in an m2m
        # command; keep the plain id around separately for actor_id below,
        # which is a Many2one and needs a plain int, not the command list.
        vals['assigne_user_id'] = [(6, 0, [assignee_id])]
        self._close_pending_history('done')
        self.with_context(skip_reassign_history=True).write(vals)
        self.env['project.approval.history'].create([
            {
                'approval_id': self.id,
                'row_type': 'action',
                'actor_id': self.env.user.id,
                'detail': 'Submitted request',
                'date': fields.Datetime.now(),
                'status': 'done',
                'reason': self.env.context.get('transition_reason', ''),
            },
            {
                'approval_id': self.id,
                'row_type': 'waiting',
                'actor_id': assignee_id,
                'detail': 'IT Review and Approve',
                'date': fields.Datetime.now(),
                'status': 'pending',
            },
        ])
        self._send_assignment_email(
            'crd_project_approval.email_template_assignment_in_review'
        )
        self._send_requester_notification()

    def action_wait_for_approval(self):
        missing = []
        if not self.technical_impact:
            missing.append("- Technical Impact")
        if not self.related_system_ids:
            missing.append("- Related System")
        if not self.dependency_ids:
            missing.append("- Project Dependency")
        if not self.estimated_effort:
            missing.append("- Estimated Effort")
        if not self.date_timeline_start:
            missing.append("- Timeline Start")
        if not self.date_timeline_end:
            missing.append("- Timeline End")
        if not self.business_sponsor_ids:
            missing.append("- Business Sponsor")
        if not self.project_size_id:
            missing.append("- Project Size")
        if not self.feature_impact_ids:
            missing.append("- Key Features & Function Impact")
        if not self.business_impact_ids:
            missing.append("- Business and Organization Impact")




        if missing:
            raise UserError(_("กรุณากรอกข้อมูลให้ครบก่อน Submit:\n%s") % "\n".join(missing))
        self._close_pending_history('done')
        approvers = self.business_sponsor_ids
        self.with_context(skip_reassign_history=True).write({
            'state': 'wait_for_approval',
            'approver_ids': [(6, 0, approvers.ids)],
            # Display-only: mirrors business_sponsor_ids so "Action By" in
            # tree/search views shows who's pending; edit rights during this
            # state are governed by is_pending_sponsor_approver, not this field.
            'assigne_user_id': [(6, 0, approvers.ids)],
        })
        now = fields.Datetime.now()
        history_vals = [{
            'approval_id': self.id,
            'row_type': 'action',
            'actor_id': self.env.user.id,
            'detail': 'IT Review completed — forwarded for Business Approval',
            'date': now,
            'status': 'done',
            'reason': self.env.context.get('transition_reason', ''),
        }]
        for sponsor in approvers:
            history_vals.append({
                'approval_id': self.id,
                'row_type': 'waiting',
                'actor_id': sponsor.id,
                'user_id': sponsor.id,
                'detail': 'Business Sponsor Review and Approve',
                'date': now,
                'status': 'pending',
            })
        self.env['project.approval.history'].create(history_vals)
        # assigne_user_id is False for this multi-approver step, so notify
        # every Business Sponsor in approver_ids instead of a single assignee.
        self._send_assignment_email(
            'crd_project_approval.email_template_assignment_wait_approval',
            users=approvers,
        )
        self._send_requester_notification()
        self._send_teams_notification(users=approvers)

    def action_approve(self):
        it_head_param = self.env['ir.config_parameter'].sudo().get_str(
            'crd_project_approval.auto_assign_it_head_user_id'
        )
        if not it_head_param:
            raise UserError(_("กรุณาตั้งค่า IT Head Approver ในหน้า Settings ก่อนดำเนินการต่อ"))
        it_head_id = int(it_head_param)
        self._close_pending_history('done')
        self.with_context(skip_reassign_history=True).write({
            'state': 'wait_it_head_approval',
            'assigne_user_id': [(6, 0, [it_head_id])],
        })
        now = fields.Datetime.now()
        self.env['project.approval.history'].create([
            {
                'approval_id': self.id,
                'row_type': 'action',
                'actor_id': self.env.user.id,
                'detail': 'Business Sponsor approved — forwarded to IT Head for final approval',
                'date': now,
                'status': 'done',
                'reason': self.env.context.get('transition_reason', ''),
            },
            {
                'approval_id': self.id,
                'row_type': 'waiting',
                'actor_id': it_head_id,
                'detail': 'IT Head Review and Approve',
                'date': now,
                'status': 'pending',
            },
        ])
        self._send_requester_notification()
        self._send_teams_notification()

    def _get_own_pending_sponsor_row(self):
        self.ensure_one()
        return self.history_ids.filtered(
            lambda h: h.row_type == 'waiting'
            and h.status == 'pending'
            and h.user_id.id == self.env.user.id
        )

    def _sponsor_vote(self, new_status):
        self.ensure_one()
        if self.env.user.id not in self.approver_ids.ids:
            raise UserError(_("Only assigned Business Sponsors can perform this action."))
        pending_row = self._get_own_pending_sponsor_row()
        if not pending_row:
            raise UserError(_("You do not have a pending approval for this request."))
        pending_row.write({
            'status': new_status,
            'reason': self.env.context.get('transition_reason', ''),
        })
        self._evaluate_sponsor_votes()

    def action_sponsor_approve(self):
        for record in self:
            record._sponsor_vote('done')

    def action_sponsor_reject(self):
        for record in self:
            record._sponsor_vote('rejected')

    def _evaluate_sponsor_votes(self):
        """Evaluate the Business Sponsor votes for the current wait_for_approval step.

        First rejection wins: as soon as any sponsor rejects, the request is
        rejected immediately and every sponsor still pending is marked
        'auto_rejected' instead of being left waiting. Otherwise, the request
        only proceeds to approval once every sponsor has voted done.

        Kept isolated from the individual vote actions so this rule can be
        swapped later without touching action_sponsor_approve/reject.
        """
        self.ensure_one()
        if not self.approver_ids:
            return
        # For each currently assigned approver, take their most recent sponsor
        # waiting-row only — this naturally scopes the evaluation to the current
        # voting round and ignores rows left over from a previous round.
        current_rows = self.env['project.approval.history']
        for approver in self.approver_ids:
            row = self.history_ids.filtered(
                lambda h: h.row_type == 'waiting' and h.user_id.id == approver.id
            ).sorted('date', reverse=True)[:1]
            current_rows |= row
        if current_rows.filtered(lambda h: h.status == 'rejected'):
            current_rows.filtered(lambda h: h.status == 'pending').write({
                'status': 'auto_rejected',
            })
            self.action_reject()
            return
        if any(row.status == 'pending' for row in current_rows):
            return  # still waiting on at least one approver
        self.action_approve()

    def action_it_head_approve(self):
        self._close_pending_history('done')
        self.write({'state': 'approved', 'assigne_user_id': [(6, 0, [])]})
        self.env['project.approval.history'].create({
            'approval_id': self.id,
            'row_type': 'action',
            'actor_id': self.env.user.id,
            'detail': 'IT Head approved — request fully approved',
            'date': fields.Datetime.now(),
            'status': 'done',
            'reason': self.env.context.get('transition_reason', ''),
        })
        self._send_requester_notification()
        try:
            self.send_to_external_api()
        except Exception as e:
            _logger.exception("Failed to enqueue API call for %s: %s", self.name, e)
            url = self.env['ir.config_parameter'].sudo().get_str('crd_project_approval.myproject_url', '')
            self.env['project.approval.api.queue'].sudo().create({
                'approval_id': self.id,
                'url': url,
                'payload': '{}',
                'state': 'failed',
                'error_message': str(e),
            })
            self.env['api.log'].sudo().create_log(
                model_name='project.approval.signoff',
                method_name='action_it_head_approve',
                url=url,
                status='error',
                error_message=str(e),
            )

    def action_reject(self):
        self._close_pending_history('rejected')
        self.with_context(skip_reassign_history=True).write({
            'state': 'rejected',
            'assigne_user_id': [(6, 0, [])],
        })
        self.env['project.approval.history'].create({
            'approval_id': self.id,
            'row_type': 'action',
            'actor_id': self.env.user.id,
            'detail': 'Request rejected — awaiting requester to reset to New or Cancel',
            'date': fields.Datetime.now(),
            'status': 'done',
            'reason': self.env.context.get('transition_reason', ''),
        })
        self._send_requester_notification()

    def action_reset_to_new(self):
        self.with_context(skip_reassign_history=True).write({
            'state': 'draft',
            'assigne_user_id': [(6, 0, [self.requester_id.id])],
        })
        self.env['project.approval.history'].create({
            'approval_id': self.id,
            'row_type': 'action',
            'actor_id': self.env.user.id,
            'detail': 'Request reset to New by requester',
            'date': fields.Datetime.now(),
            'status': 'done',
            'reason': self.env.context.get('transition_reason', ''),
        })
        self._send_requester_notification()

    def action_cancel(self):
        for record in self:
            if record.state in ('cancelled', 'approved'):
                raise UserError(_(
                    'Cannot cancel a request that is already %s.'
                ) % dict(record._fields['state'].selection).get(record.state, record.state))
        # _close_pending_history only closes the single most recent pending
        # row, but wait_for_approval can have one pending row per Business
        # Sponsor voting concurrently — close all of them so none are left
        # dangling as 'pending' after the record moves to 'cancelled'.
        self.history_ids.filtered(
            lambda h: h.row_type == 'waiting' and h.status == 'pending'
        ).write({'status': 'cancelled'})
        self.with_context(skip_reassign_history=True).write({'state': 'cancelled'})
        self.env['project.approval.history'].create({
            'approval_id': self.id,
            'row_type': 'action',
            'actor_id': self.env.user.id,
            'detail': 'Request cancelled by requester',
            'date': fields.Datetime.now(),
            'status': 'done',
            'reason': self.env.context.get('transition_reason', ''),
        })
        self._send_requester_notification()

    def _fix_attachment_res_id(self):
        self.ensure_one()
        attachments = self.sudo().attachment_ids.filtered(
            lambda a: a.res_model == self._name and not a.res_id
        )
        if attachments:
            attachments.sudo().write({'res_id': self.id})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('project.approval.signoff') or 'New'
        records = super().create(vals_list)
        for record in records:
            record._fix_attachment_res_id()
        return records

    def write(self, vals):
        skip_reassign = self.env.context.get('skip_reassign_history', False)
        tracking = 'assigne_user_id' in vals and not skip_reassign
        if tracking:
            # Capture recordsets (not raw ids) before the write, since
            # assigne_user_id is Many2many: `vals['assigne_user_id']` is an
            # ORM command list, not a plain id, and can't be parsed directly.
            old_assignees = {rec.id: rec.assigne_user_id for rec in self}
            prev_pending = {
                rec.id: rec.history_ids.filtered(
                    lambda h: h.row_type == 'waiting' and h.status == 'pending'
                )
                for rec in self
            }
        result = super().write(vals)
        if tracking:
            for rec in self:
                old_users = old_assignees.get(rec.id, self.env['res.users'])
                new_users = rec.assigne_user_id  # read post-write, reflects the actual new set
                old_ids = set(old_users.ids)
                new_ids = set(new_users.ids)
                if old_ids == new_ids:
                    continue
                removed = old_users.filtered(lambda u: u.id not in new_ids)
                added = new_users.filtered(lambda u: u.id not in old_ids)
                pending_history = prev_pending.get(rec.id, self.env['project.approval.history'])
                if removed and pending_history:
                    # Untagged rows (no user_id — the legacy single-assignee
                    # shape) only apply to the removed set as a whole when
                    # no assignee survives; otherwise they may belong to a
                    # user who is still assigned and must not be closed.
                    no_survivors = not (old_ids & new_ids)
                    to_close = pending_history.filtered(
                        lambda h: (h.user_id and h.user_id in removed)
                        or (not h.user_id and no_survivors)
                    )
                    if to_close:
                        reason = (
                            'Reassigned to %s' % ', '.join(added.mapped('name'))
                            if added else _('Unassigned')
                        )
                        to_close.write({
                            'row_type': 'reassign',
                            'status': 'done',
                            'reason': reason,
                        })
                if added:
                    detail = pending_history[:1].detail if pending_history else _('Pending Action')
                    self.env['project.approval.history'].create([{
                        'approval_id': rec.id,
                        'row_type': 'waiting',
                        'status': 'pending',
                        'actor_id': user.id,
                        'user_id': user.id,
                        'detail': detail,
                        'date': fields.Datetime.now(),
                    } for user in added])
                    # Send reassignment email to newly added users
                    rec._send_assignment_email(
                        'crd_project_approval.email_template_assignment_reassign',
                        users=added
                    )
        for record in self:
            record._fix_attachment_res_id()
        return result

    def unlink(self):
        for record in self:
            if record.requester_id != self.env.user:
                raise UserError(_('Only the requester can delete this project approval request.'))
        return super().unlink()

    def send_to_external_api(self):
        self.ensure_one()
        import json as _json
        ICP = self.env['ir.config_parameter'].sudo()
        base_url = ICP.get_str('crd_project_approval.myproject_url', 'https://dev-myproject.ofm.co.th/api/project.project/execute_kw')
        api_key = ICP.get_str('crd_project_approval.myproject_api_key', '')
        url = '%s?api_key=%s' % (base_url, api_key) if api_key else base_url

        payload = {
            "method": "api_create_ticket",
            "args": [[]],
            "kw": {
                "name": self.name,
                "project_name": "%s %s" % (self.name or '', self.project_name or ''),
                "business_owner": ', '.join(self.business_owner.mapped('name')) or '',
                "business_sponsor": ', '.join(self.business_sponsor_ids.mapped('name')) or '',
                "requester_id": self.requester_id.email or '',
                "date_request": str(self.date_request) if self.date_request else '',
                "legal_compliance_detail": self.legal_compliance_detail or '',
                "customer_satisfaction_detail": self.customer_satisfaction_detail or '',
                "corporate_reputation_detail": self.corporate_reputation_detail or '',
                "productivity_improvement_detail": self.productivity_improvement_detail or '',
                "employee_engagement_detail": self.employee_engagement_detail or '',
                "revenue_increasing": self.revenue_increasing or '',
                "cost_decreasing_avoidance": self.cost_decreasing_avoidance or '',
            },
        }

        queue = self.env['project.approval.api.queue'].create({
            'approval_id': self.id,
            'url': url,
            'payload': _json.dumps(payload, ensure_ascii=False, indent=2),
        })
        return queue





