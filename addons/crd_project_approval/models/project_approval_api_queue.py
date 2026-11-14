# -*- coding: utf-8 -*-
import logging
import requests

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

MAX_RETRY = 3


class ProjectApprovalApiQueue(models.Model):
    _name = 'project.approval.api.queue'
    _description = 'Project Approval API Queue'
    _rec_name = 'name'
    _order = 'create_date desc'

    name = fields.Char(string='Reference', required=True, copy=False, default='New')
    approval_id = fields.Many2one(
        'project.approval.signoff',
        string='Project Request',
        ondelete='set null',
        index=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Pending'),
            ('done', 'Success'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        index=True,
        tracking=True,
    )
    url = fields.Char(string='URL')
    payload = fields.Text(string='Payload (JSON)')
    http_status = fields.Char(string='HTTP Status')
    response_body = fields.Text(string='Response Body')
    error_message = fields.Text(string='Error Message')
    retry_count = fields.Integer(string='Retry Count', default=0)
    max_retry = fields.Integer(string='Max Retry', default=MAX_RETRY)
    last_attempt_date = fields.Datetime(string='Last Attempt')
    next_retry_date = fields.Datetime(string='Next Retry After')
    can_retry = fields.Boolean(compute='_compute_can_retry', store=False)


    @api.depends('state', 'retry_count', 'max_retry')
    def _compute_can_retry(self):
        for rec in self:
            rec.can_retry = rec.state == 'failed' and rec.retry_count < rec.max_retry

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('project.approval.api.queue') or 'New'
        return super().create(vals_list)

    def _do_send(self):
        self.ensure_one()
        import json as _json
        try:
            payload_dict = _json.loads(self.payload or '{}')
        except Exception:
            payload_dict = {}

        headers = {'Content-Type': 'application/json'}

        now = fields.Datetime.now()
        try:
            response = requests.post(self.url, json=payload_dict, headers=headers, timeout=15)
            response_text = response.text[:5000]

            if not response.ok:
                self._handle_failure(
                    http_status=str(response.status_code),
                    response_body=response_text,
                    error_message='HTTP %s: %s' % (response.status_code, response.text[:500]),
                    now=now,
                )
                return

            try:
                body = response.json()
            except Exception:
                body = {}

            result = body.get('result', {})
            if result.get('status') == 'error':
                self._handle_failure(
                    http_status=str(response.status_code),
                    response_body=response_text,
                    error_message=result.get('message', 'Unknown error from API'),
                    now=now,
                )
            else:
                self.write({
                    'state': 'done',
                    'http_status': str(response.status_code),
                    'response_body': response_text,
                    'error_message': False,
                    'last_attempt_date': now,
                })
                project_url = body.get('result', {}).get('project_url', False)
                if self.approval_id and project_url:
                    self.approval_id.write({'project_url': project_url})

        except Exception as e:
            self._handle_failure(
                http_status='error',
                response_body='',
                error_message=str(e),
                now=now,
            )

    def _handle_failure(self, http_status, response_body, error_message, now):
        new_retry = self.retry_count + 1
        backoff_minutes = 2 ** new_retry
        next_retry = fields.Datetime.add(now, minutes=backoff_minutes)
        self.write({
            'state': 'failed',
            'http_status': http_status,
            'response_body': response_body,
            'error_message': error_message,
            'retry_count': new_retry,
            'last_attempt_date': now,
            'next_retry_date': next_retry if new_retry < self.max_retry else False,
        })
        _logger.warning('API queue %s failed (attempt %s/%s): %s', self.name, new_retry, self.max_retry, error_message)

    def action_retry(self):
        for rec in self:
            if rec.state == 'failed':
                rec._do_send()

    def action_cancel(self):
        self.filtered(lambda r: r.state in ('draft', 'failed')).write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.filtered(lambda r: r.state in ('failed', 'cancelled')).write({
            'state': 'draft',
            'retry_count': 0,
            'error_message': False,
            'next_retry_date': False,
        })

    @api.model
    def _cron_cleanup_old_records(self):
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), months=2)
        old_records = self.search([
            ('create_date', '<', cutoff),
            ('state', 'in', ('done', 'cancelled', 'failed')),
        ])
        _logger.info('Cleaning up %s old API queue records older than 2 months', len(old_records))
        old_records.unlink()

    @api.model
    def _cron_process_queue(self):
        now = fields.Datetime.now()
        domain = [
            ('state', 'in', ('draft', 'failed')),
            '|',
            ('next_retry_date', '=', False),
            ('next_retry_date', '<=', now),
            ('retry_count', '<', MAX_RETRY),
        ]
        records = self.search(domain, limit=20, order='create_date asc')
        for rec in records:
            rec._do_send()
