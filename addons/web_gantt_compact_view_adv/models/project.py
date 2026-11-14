from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    gantt_start_date = fields.Date(compute='_compute_gantt_info', string="Gantt Start Date", store=True)
    gantt_end_date = fields.Date(compute='_compute_gantt_info', string="Gantt End Date", store=True)
    gantt_color = fields.Char(compute='_compute_gantt_info', string="Gantt Color", store=True)

    @api.depends('start_date', 'end_date', 'date_start', 'date')
    def _compute_gantt_info(self):
        for project in self:
            if project.start_date and project.end_date:
                project.gantt_start_date = project.start_date
                project.gantt_end_date = project.end_date
                project.gantt_color = '#0190d9'
            else:
                project.gantt_start_date = project.date_start
                project.gantt_end_date = project.date
                project.gantt_color = '#cecece'


class ProjectTask(models.Model):
    _inherit = "project.task"

    date_from = fields.Datetime(string='Planned start', index=True, copy=False)
    date_to = fields.Datetime(string='Planned stop', index=True, copy=False)
    task_type = fields.Selection([
        ('task', 'Task'),
        ('milestone', 'Milestone')
        ], string="Task Type", required=True, default='task')
    color = fields.Integer('Project color', default=4)
    task_link_ids = fields.One2many('project.task.link', 'source_id', string="Task Links")
    task_priority = fields.Selection([
        ('normal', 'Normal'),
        ('low', 'Low'),        
        ('high', 'High')
    ], string='Priority', required=True, default='normal')
    progress = fields.Integer(tracking=True)

    @api.onchange('date_to')
    def onchange_gantt_stop_date(self):
        if self.date_from and self.date_to and self.date_to < self.date_from:
            self.date_to = self.date_from


    @api.model
    def search_read_links(self, domain=None):
        datas = []
        tasks = self.env['project.task'].search(domain)
        for task in tasks:
            if task.task_link_ids:                
                for link in task.task_link_ids:                    
                    link_vals = {
                        'id' : link.id,
                        'source' : task.id,
                        'target': link.target_id.id, 
                        'type': link.link_type,
                    }
                    datas.append(link_vals)
        return datas

class ProjectTaskLink(models.Model):
    _name = "project.task.link"
    _description = "Project Task Links"

    source_id = fields.Many2one('project.task', string='Task')
    target_id = fields.Many2one('project.task', string='Target Task', required=True)
    link_type = fields.Selection([
        ('0', "Finish to Start"), 
        ('1', "Start to Start"), 
        ('2', "Finish to Finish"),
        ('3', "Start to Finish")
        ], string="Link Type", required=True, default='1')