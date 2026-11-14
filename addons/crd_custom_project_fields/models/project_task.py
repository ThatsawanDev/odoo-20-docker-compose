import logging
from odoo.exceptions import ValidationError
import base64
import tempfile
from odoo import models, fields, api, _ 
from odoo.exceptions import UserError
from odoo import SUPERUSER_ID


_logger = logging.getLogger(__name__)
CLOSED_STATES = {
    '1_done': 'Done',
    # '1_pending': 'Pending',
    '1_canceled': 'Cancelled',
}

class ProjectTask(models.Model):
    _inherit = 'project.task'

    checklist_ids = fields.One2many(
        'project.task.checklist',
        'task_id',
        string='Checklist',
        tracking=True
    )

    checklist_progress = fields.Float(
        string='Checklist Progress (%)',
        compute='_compute_checklist_progress',
        store=True
    )
    state = fields.Selection([
        ('00_new', 'New'),
        ('01_in_progress', 'In Progress'),
        # ('02_changes_requested', 'Changes Requested'),
        # ('03_approved', 'Approved'),
        *CLOSED_STATES.items(),
        ('04_waiting_normal', 'On Hold'),
    ], string='State', copy=False, default='00_new', required=True, compute='_compute_state',
        inverse='_inverse_state', readonly=False, store=True, index=True, recursive=True, tracking=True)


    attachment_ids = fields.Many2many(
        'ir.attachment',
        'project_task_attachment_rel',
        'task_id',
        'attachment_id',
        string='Attach a file'
    )

    subtask_completion_percentage = fields.Float(
        string="Completion Percentage",
        compute="_compute_subtask_completion_percentage",
        store=True,  # จำเป็นเพื่อให้แก้ไขและบันทึกค่าได้
        readonly=False,  # เปิดให้แก้ไขด้วยมือได้ในหน้า UI
        export_string_translation=False
    )
    is_subtask_computed = fields.Boolean(compute="_compute_is_subtask_computed")

    @api.depends('parent_id', 'child_ids', 'state')
    def _compute_is_subtask_computed(self):
        for rec in self:
            rec.is_subtask_computed = bool(rec.child_ids or rec.state != '01_in_progress')

    @api.depends('state', 'child_ids.subtask_completion_percentage', 'child_ids.state')
    def _compute_subtask_completion_percentage(self):
        for rec in self:
            if rec.state == '1_done':
                rec.subtask_completion_percentage = 1.0
            elif rec.child_ids:
                active_subtasks = rec.child_ids.filtered(lambda r: r.state != '1_canceled')
                if active_subtasks:
                    total_progress = sum(active_subtasks.mapped('subtask_completion_percentage'))
                    rec.subtask_completion_percentage = total_progress / len(active_subtasks)
                else:
                    rec.subtask_completion_percentage = 0.0
            else:
                rec.subtask_completion_percentage = rec.subtask_completion_percentage

    #Overwrite Project
    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.state != '04_waiting_normal':
            self.state = '00_new'

    def write(self, vals):
        if vals.get('state') == '1_done':
            incomplete_tasks = self.filtered(
                lambda r: r.subtask_count > 0 and r.subtask_completion_percentage < 1.0
            )
            if incomplete_tasks:
                raise UserError(_(
                    "ไม่สามารถปิดงาน '%s' ได้: เนื่องจากยังมีงานย่อย (Subtasks) ที่ยังดำเนินการไม่เสร็จสิ้น "
                    "(ความคืบหน้าปัจจุบัน: %s%%)"
                ) % (incomplete_tasks[0].display_name, int(incomplete_tasks[0].subtask_completion_percentage * 100)))
        return super().write(vals)

    @api.depends('checklist_ids.checkbox')
    def _compute_checklist_progress(self):
        for task in self:
            total = len(task.checklist_ids)
            if not total:
                task.checklist_progress = 0.0
            else:
                done = len(task.checklist_ids.filtered('checkbox'))
                task.checklist_progress = (done / total) * 100

    @api.constrains('checklist_ids')
    def _check_has_checklist(self):
        for task in self:
            if not task.checklist_ids:
                raise ValidationError(
                    "ต้องกำหนด Checklist อย่างน้อย 1 รายการก่อนบันทึก Task"
                )

    @api.depends('child_ids.state')
    def _compute_subtask_count(self):
        for task in self:
            valid_subtasks = task.child_ids.filtered(lambda r: r.state != '1_canceled')
            task.subtask_count = len(valid_subtasks)
            task.closed_subtask_count = len(valid_subtasks.filtered(lambda r: r.state in CLOSED_STATES))

    @api.constrains('stage_id')
    def _check_progress_before_done(self):
        for task in self:
            if task.stage_id.fold and task.checklist_progress < 100:
                raise ValidationError(
                    "Checklist ต้องครบ 100% ก่อนปิด Task"
                )

class ProjectTaskChecklist(models.Model):
    _name = 'project.task.checklist'
    _description = 'Task Checklist'
    _rec_name = "description"

    task_id = fields.Many2one(
        'project.task',
        required=False,
        ondelete='cascade'
    )
    sequence = fields.Integer(default=10)
    description = fields.Char(string="Description")
    topic = fields.Char(required=True,string="Topic")
    task_stage_id = fields.Many2one(related='task_id.stage_id', store=True)
    checkbox = fields.Boolean(string='Done', default=False)
