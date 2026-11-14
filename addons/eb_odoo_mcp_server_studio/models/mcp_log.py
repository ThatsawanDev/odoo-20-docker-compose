# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class McpLog(models.Model):
    """
    Comprehensive audit log for every MCP interaction.
    Captures user, tool, parameters, result, timing, errors,
    session context, and full tracebacks for debugging.
    """
    _name        = 'mcp.log'
    _description = 'MCP Execution Log'
    _order       = 'create_date desc'
    _log_access  = True

    # ── Core fields ───────────────────────────────────────────────────────
    tool_name      = fields.Char(string='Tool', readonly=True, index=True)
    model_name     = fields.Char(string='Model', readonly=True)
    method         = fields.Char(
        string='MCP Method', readonly=True, index=True,
        help="JSON-RPC method: initialize, tools/call, prompts/get, etc.",
    )
    operation      = fields.Selection([
        ('search_read',     'Search / Read'),
        ('create',          'Create'),
        ('write',           'Update'),
        ('unlink',          'Delete'),
        ('get_fields',      'Get Fields'),
        ('list_models',     'List Models'),
        ('execute',         'Execute'),
        ('code',            'Code'),
        ('webapp',          'Web App'),
        ('echart',          'EChart'),
        ('module',          'Module'),
        ('snippet',         'Snippet'),
        ('report',          'Report'),
        ('email_template',  'Email Template'),
        ('protocol',        'Protocol'),
    ], string='Operation', readonly=True)

    # ── Severity ──────────────────────────────────────────────────────────
    log_level      = fields.Selection([
        ('debug',   'Debug'),
        ('info',    'Info'),
        ('warning', 'Warning'),
        ('error',   'Error'),
    ], string='Level', default='info', readonly=True, index=True)

    # ── Identity & context ────────────────────────────────────────────────
    user_id        = fields.Many2one(
        'res.users', string='User', readonly=True, index=True,
    )
    ip_address     = fields.Char(string='IP Address', readonly=True)
    session_id     = fields.Char(
        string='Session', readonly=True, index=True,
        help="Groups all calls from the same MCP client session.",
    )
    request_id     = fields.Char(
        string='Request ID', readonly=True,
        help="JSON-RPC request ID for correlation.",
    )

    # ── Payload & result ──────────────────────────────────────────────────
    payload        = fields.Text(string='Parameters', readonly=True)
    result_summary = fields.Text(string='Result', readonly=True)
    response_size  = fields.Integer(
        string='Response (bytes)', readonly=True,
        help="Size of the JSON response payload in bytes.",
    )

    # ── Timing ────────────────────────────────────────────────────────────
    duration_ms    = fields.Integer(string='Duration (ms)', readonly=True)

    # ── State & errors ────────────────────────────────────────────────────
    state          = fields.Selection([
        ('ok',    'OK'),
        ('error', 'Error'),
    ], string='State', default='ok', readonly=True, index=True)
    error_message  = fields.Text(string='Error', readonly=True)
    traceback_info = fields.Text(
        string='Traceback', readonly=True,
        help="Full Python stack trace for debugging errors.",
    )

    # ── Auto-cleanup ──────────────────────────────────────────────────────

    @api.model
    def _cron_cleanup_logs(self, days=30):
        """
        Delete MCP logs older than `days` days.
        Called by scheduled action (daily).
        """
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old_logs = self.search([('create_date', '<', cutoff)])
        count = len(old_logs)
        if count:
            old_logs.unlink()
            _logger.info(
                "MCP log cleanup: deleted %d log(s) older than %d days.",
                count, days,
            )
        return True
