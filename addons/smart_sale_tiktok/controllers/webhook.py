# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import time

from psycopg2 import IntegrityError

from odoo import http
from odoo.http import request

from odoo.addons.smart_sale_tiktok import utils


class TikTokWebhookController(http.Controller):

    @http.route(
        '/smart_sale_tiktok/oauth/callback',
        type='http',
        auth='user',
        methods=['GET'],
        csrf=False,
    )
    def tiktok_oauth_callback(self, code=None, state=None, error=None, **kwargs):
        shop = request.env['tiktok.shop'].search([('oauth_state', '=', state)], limit=1)
        if error or not code or not shop:
            return request.redirect('/odoo')
        utils.request_access_token(shop, authorization_code=code)
        shop.write({'state': 'active', 'oauth_state': False})
        return request.redirect(f'/odoo/tiktok.shop/{shop.id}')

    @http.route(
        '/smart_sale_tiktok/webhook',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def receive_tiktok_webhook(self):
        raw_body = request.httprequest.get_data(cache=True)
        try:
            payload = json.loads(raw_body)
        except (TypeError, ValueError):
            return request.make_json_response({'message': 'Invalid JSON'}, status=400)

        shop_identifier = str(payload.get('shop_id') or '')
        shop = request.env['tiktok.shop'].sudo().search([
            ('shop_identifier', '=', shop_identifier),
            ('state', '=', 'active'),
        ], limit=1)
        signature = request.httprequest.headers.get('Authorization')
        if not shop or not utils.verify_webhook_signature(
            shop.account_id, raw_body, signature,
        ):
            return request.make_json_response({'message': 'Unauthorized'}, status=401)

        timestamp = int(payload.get('timestamp') or 0)
        if not timestamp or abs(int(time.time()) - timestamp) > 600:
            return request.make_json_response({'message': 'Expired event'}, status=401)

        notification_id = str(
            payload.get('tts_notification_id')
            or f"{shop_identifier}:{payload.get('type')}:{timestamp}"
        )
        event_model = request.env['tiktok.webhook.event'].sudo()
        event = event_model.search([('notification_id', '=', notification_id)], limit=1)
        if not event:
            try:
                with request.env.cr.savepoint():
                    event = event_model.create({
                        'notification_id': notification_id,
                        'shop_id': shop.id,
                        'event_type': str(payload.get('type') or ''),
                        'order_id': str((payload.get('data') or {}).get('order_id') or ''),
                        'payload': raw_body.decode('utf-8'),
                    })
            except IntegrityError:
                event = event_model.search([
                    ('notification_id', '=', notification_id),
                ], limit=1)
        if event and event.state != 'done':
            event._process()
        return request.make_json_response({'message': 'OK'})
