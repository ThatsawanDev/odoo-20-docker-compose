from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    # ===== Cost =====
    cost_cloud = fields.Float(string="Cloud Cost")
    cost_client = fields.Float(string="Client Cost")
    cost_security = fields.Float(string="Security Cost")

    # ===== Effort =====
    effort = fields.Float(string="Effort (Manday)")

    # ===== Project Dates =====
    start_date = fields.Date(string="Project Start Date")
    end_date = fields.Date(string="Project End Date")
    progress = fields.Integer(string='Progress')

    # ===== Business Impact =====
    impact_legal = fields.Boolean(string="Legal or Corporate Compliance")
    impact_legal_note = fields.Char(string="Details")

    impact_revenue = fields.Boolean(string="Revenue Increasing")
    impact_revenue_note = fields.Char(string="Details")

    impact_cost = fields.Boolean(string="Cost Saving")
    impact_cost_note = fields.Char(string="Details")

    impact_customer = fields.Boolean(string="Customer Satisfaction")
    impact_customer_note = fields.Char(string="Details")

    impact_reputation = fields.Boolean(string="Corporate Reputation")
    impact_reputation_note = fields.Char(string="Details")

    impact_productivity = fields.Boolean(string="Productivity Improvement")
    impact_productivity_note = fields.Char(string="Details")

    impact_employee = fields.Boolean(string="Employee Engagement")
    impact_employee_note = fields.Char(string="Details")

    business_target_date = fields.Char(string="Business Target Date")
    business_owner = fields.Char(string="Business Owner")

    # Optional summary
    # business_impact = fields.Text(string="Business Impact Summary")
    # solution = fields.Text(string="Solution")
    # benefits = fields.Text(string="Benefits")


    # BU
    bu = fields.Char("Bu")

    # Approvers
    approver_ids = fields.One2many('project.approver', 'project_id', string='Approvers')
    is_current_user_approver = fields.Boolean(
        string='Is Current User Approver',
        compute='_compute_is_current_user_approver',
    )

    @api.depends('approver_ids.user_id', 'approver_ids.approve')
    def _compute_is_current_user_approver(self):
        for project in self:
            project.is_current_user_approver = bool(
                project.approver_ids.filtered(
                    lambda a: a.user_id == self.env.user and not a.approve
                )
            )

    def action_approve_project(self):
        self.ensure_one()
        approver = self.approver_ids.filtered(
            lambda a: a.user_id == self.env.user and not a.approve
        )
        if approver:
            approver.write({'approve': True})

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        for project in projects:
            project._sync_manager_approver()
        return projects

    def write(self, vals):
        if 'stage_id' in vals:
            for project in self:
                if project.approver_ids and not all(project.approver_ids.mapped('approve')):
                    pending = project.approver_ids.filtered(lambda a: not a.approve).mapped('user_id.name')
                    raise UserError(_(
                        "Cannot change stage of project '%(project)s' — pending approval from: %(users)s",
                        project=project.display_name,
                        users=', '.join(pending),
                    ))
        return super().write(vals)




    def api_create_ticket(self, **kw):
        try:
            document_name = kw.get('document_name')
            project_name = kw.get('project_name')
            business_owner = kw.get('business_owner')
            legal_compliance_detail = kw.get('legal_compliance_detail')
            customer_satisfaction_detail = kw.get('customer_satisfaction_detail')
            corporate_reputation_detail = kw.get('corporate_reputation_detail')
            productivity_improvement_detail = kw.get('productivity_improvement_detail')
            employee_engagement_detail = kw.get('employee_engagement_detail')
            revenue_increasing = kw.get('revenue_increasing')
            cost_decreasing_avoidance = kw.get('cost_decreasing_avoidance')

            project = self.create({
                'name': project_name,
                'business_owner': business_owner,
                'impact_legal': bool(legal_compliance_detail),
                'impact_customer': bool(customer_satisfaction_detail),
                'impact_reputation': bool(corporate_reputation_detail),
                'impact_productivity': bool(productivity_improvement_detail),
                'impact_employee': bool(employee_engagement_detail),
                'impact_revenue': bool(revenue_increasing),
                'impact_cost': bool(cost_decreasing_avoidance),
                'impact_legal_note': legal_compliance_detail or '',
                'impact_customer_note': customer_satisfaction_detail or '',
                'impact_reputation_note': corporate_reputation_detail or '',
                'impact_productivity_note': productivity_improvement_detail or '',
                'impact_employee_note': employee_engagement_detail or '',
                'impact_revenue_note': revenue_increasing or '',
                'impact_cost_note': cost_decreasing_avoidance or '',
            })
            base_url = self.env['ir.config_parameter'].sudo().get_str('web.base.url')
            project_url = f"{base_url}/odoo/project/{project.id}"
            return {
                'status': 'success',
                'message': 'Ticket created successfully',
                'project_name': project.name,
                'project_url': project_url,
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
            }


    def _sync_manager_approver(self):
        self.ensure_one()
        if not self.user_id:
            return
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.user_id.id)], limit=1
        )
        manager_user = employee.parent_id.user_id
        if not manager_user:
            return
        exists = self.approver_ids.filtered(lambda a: a.user_id == manager_user)
        if exists:
            return
        self.env['project.approver'].create({
            'project_id': self.id,
            'user_id': manager_user.id,
        })