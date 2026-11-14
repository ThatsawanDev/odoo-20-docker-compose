import json
import logging
import pprint

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class ReceiveTicketController(http.Controller):

    @http.route(
        '/create/project',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def create_project(self, **kwargs):
        try:
            raw = request.httprequest.get_data(as_text=True) or '{}'
            payload = json.loads(raw) if raw.strip() else {}
        except ValueError as e:
            _logger.warning("Invalid JSON body for /create/project: %s", e)
            return Response(
                json.dumps({'success': False, 'error': 'Invalid JSON body'}),
                status=400,
                content_type='application/json',
            )

        if not isinstance(payload, dict):
            payload = {}

        sender_email = payload.get('sender_email')
        project_name = payload.get('project_name')
        data = payload.get('data') or {}

        result = request.env['project.task'].sudo().create_from_ticket({
            'data': data,
            'sender_email': sender_email,
            'project_name': project_name,
        })
        return Response(
            json.dumps(result, default=str, ensure_ascii=False),
            status=200,
            content_type='application/json',
        )
