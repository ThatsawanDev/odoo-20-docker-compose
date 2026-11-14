import json
import logging
from odoo import http
from odoo.http import request
from markupsafe import Markup

_logger = logging.getLogger(__name__)

class ProjectApprovalController(http.Controller):

    @http.route(
        '/project_approval/teams_callback',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False
    )
    def teams_approval_callback(self):
        def _response(data, status_code=200):
            return request.make_response(
                json.dumps(data),
                headers=[('Content-Type', 'application/json')],
                status=status_code
            )

        # Parse JSON body; fallback to form/query params
        body = {}
        raw_data = request.httprequest.get_data(as_text=True)
        if raw_data:
            try:
                body = json.loads(raw_data)
            except Exception as e:
                return _response({"status": "error", "message": f"Malformed JSON: {str(e)}"}, status_code=400)

        if not body:
            merged = {**request.httprequest.args, **request.httprequest.form}
            if merged:
                body = merged

        # รองรับทั้ง flat และ nested {"params": {...}}
        data = body.get('params', body) if isinstance(body, dict) else {}

        request_id = data.get('request_id')
        action = str(data.get('action', '')).lower()
        approver_name = data.get('approver_name', 'Unknown')
        approver_email = data.get('approver_email', '-')

        def _log(status, error_message=''):
            request.env['api.log'].sudo().create_log(
                model_name='project.approval.signoff',
                method_name='teams_approval_callback',
                body=data,
                url='/project_approval/teams_callback',
                status=status,
                error_message=error_message,
            )

        if not request_id or not action:
            msg = "Incomplete data (Payload is empty or missing required fields)"
            _log('error', msg)
            return _response({"status": "error", "message": msg}, status_code=400)

        user_system_id = request.env['res.users'].sudo().search([('name', '=', approver_name)], limit=1)

        if not user_system_id:
            msg = f"User '{approver_name}' not found in system"
            _log('error', msg)
            return _response({"status": "error", "message": msg}, status_code=400)

        try:
            record = request.env['project.approval.signoff'].sudo().browse(int(request_id))
            if not record.exists():
                msg = f"Record ID {request_id} not found"
                _log('error', msg)
                return _response({"status": "error", "message": msg}, status_code=404)

            if record.state == 'wait_for_approval':
                is_authorized = user_system_id.id in record.approver_ids.ids
            else:
                is_authorized = user_system_id.id in record.assigne_user_id.ids
            if not is_authorized:
                msg = f"User '{approver_name}' is not the assigned approver for this record"
                _log('error', msg)
                return _response({"status": "error", "message": msg}, status_code=403)

            action_text = "อนุมัติ (Approved)" if action == 'approved' else "ปฏิเสธ (Rejected)"
            log_message = Markup(
                f"🎯 <b>ดำเนินการผ่าน MS Teams</b><br/>"
                f"<b>ผลการตัดสินใจ:</b> {action_text}<br/>"
                f"<b>ผู้ดำเนินการ:</b> {approver_name} ({approver_email})"
            )

            record_as_user = record.with_user(user_system_id).sudo()
            if action == 'approved':
                if record.state == 'in_review':
                    record_as_user.action_wait_for_approval()
                elif record.state == 'wait_for_approval':
                    record_as_user.action_sponsor_approve()
                elif record.state == 'wait_it_head_approval':
                    record_as_user.action_it_head_approve()
                else:
                    msg = f"Record state '{record.state}' does not allow approval"
                    _log('error', msg)
                    return _response({"status": "error", "message": msg}, status_code=400)
                record_as_user.message_post(body=log_message)
            elif action == 'rejected':
                if record.state == 'wait_for_approval':
                    record_as_user.action_sponsor_reject()
                elif record.state in ('in_review', 'wait_it_head_approval'):
                    record_as_user.action_reject()
                else:
                    msg = f"Record state '{record.state}' does not allow rejection"
                    _log('error', msg)
                    return _response({"status": "error", "message": msg}, status_code=400)
                record_as_user.message_post(body=log_message)
            else:
                msg = f"Invalid action: {action}"
                _log('error', msg)
                return _response({"status": "error", "message": msg}, status_code=400)

            _log('success')
            _logger.info("Teams callback success: %s -> %s by %s", record.name, action, approver_email)

        except Exception as e:
            _logger.exception("Teams callback error for request_id=%s", request_id)
            _log('error', str(e))
            return _response({"status": "error", "message": str(e)}, status_code=500)

        return _response({"status": "success"})
