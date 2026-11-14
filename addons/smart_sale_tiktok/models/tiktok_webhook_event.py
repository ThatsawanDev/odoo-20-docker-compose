# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging

from odoo import api, fields, models

from odoo.addons.smart_sale_tiktok import utils

_logger = logging.getLogger(__name__)


class TikTokWebhookEvent(models.Model):
    _name = 'tiktok.webhook.event'
    _description = 'TikTok Shop Webhook Event'
    _order = 'create_date desc'

    notification_id = fields.Char(required=True, index=True, readonly=True)
    shop_id = fields.Many2one('tiktok.shop', required=True, ondelete='cascade', readonly=True)
    event_type = fields.Char(readonly=True)
    order_id = fields.Char(index=True, readonly=True)
    payload = fields.Text(required=True, readonly=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('error', 'Error'),
    ], default='pending', required=True, index=True, readonly=True)
    error_message = fields.Text(readonly=True)
    processed_at = fields.Datetime(readonly=True)

    _notification_unique = models.Constraint(
        'UNIQUE(notification_id)',
        'The TikTok webhook notification has already been received.',
    )

    def _process(self):
        for event in self.filtered(lambda row: row.state != 'done'):
            try:
                payload = json.loads(event.payload)
                data = payload.get('data') or {}
                order_id = str(data.get('order_id') or event.order_id or '')
                if order_id:
                    order = self.env['sale.order'].search([
                        ('tiktok_shop_id', '=', event.shop_id.id),
                        ('tiktok_order_id', '=', order_id),
                    ], limit=1)
                    # Fetch full order data for new orders and address/package changes.
                    if not order or payload.get('type') != 1:
                        detail = utils.make_tiktok_api_request(
                            event.shop_id,
                            'get_order_detail',
                            path_values={'order_id': order_id},
                        )
                        order_data = detail.get('order') or detail
                        order = event.shop_id._import_single_order(
                            event.shop_id, order_data,
                        )
                    elif data.get('order_status'):
                        order.write({
                            'tiktok_order_status': data['order_status'],
                            'tiktok_last_update': fields.Datetime.now(),
                        })
                        order._apply_tiktok_status()
                event.write({
                    'state': 'done',
                    'error_message': False,
                    'processed_at': fields.Datetime.now(),
                })
            except Exception as error:
                _logger.exception("Failed to process TikTok webhook %s", event.notification_id)
                event.write({'state': 'error', 'error_message': str(error)})

    @api.model
    def _cron_retry_events(self):
        self.search([('state', 'in', ('pending', 'error'))], limit=100)._process()

