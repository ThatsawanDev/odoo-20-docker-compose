# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.smart_sale_tiktok import utils

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    tiktok_shop_id = fields.Many2one('tiktok.shop', related='sale_id.tiktok_shop_id', store=True, readonly=True, string="TikTok Shop")
    tiktok_order_id = fields.Char(related='sale_id.tiktok_order_id', store=True, readonly=True, string="TikTok Order SN")
    tiktok_tracking_number = fields.Char(string="TikTok Tracking No", copy=False)
    tiktok_shipping_provider = fields.Char(string="Shipping Carrier", copy=False)
    
    def action_tiktok_rts(self):
        """Trigger 'Ready to Ship' (RTS) via TikTok Shop API for this picking."""
        for picking in self.filtered(lambda p: p.tiktok_shop_id and p.tiktok_order_id):
            package_id = picking.sale_id.tiktok_package_id
            if not package_id:
                raise UserError(_("TikTok package ID is missing. Synchronize the order first."))
            body = {}
            if picking.sale_id.tiktok_delivery_option in ('SELLER', 'SELLER_SHIPPING'):
                if not picking.tiktok_tracking_number or not picking.tiktok_shipping_provider:
                    raise UserError(_(
                        "Tracking number and TikTok shipping provider ID are required "
                        "for seller shipping."
                    ))
                body['self_shipment'] = {
                    'tracking_number': picking.tiktok_tracking_number,
                    'shipping_provider_id': picking.tiktok_shipping_provider,
                }
            else:
                body['handover_method'] = 'DROP_OFF'
            utils.make_tiktok_api_request(
                picking.tiktok_shop_id,
                'ship_package',
                body=body,
                path_values={'package_id': package_id},
            )
            _logger.info(
                "TikTok package %s marked ready to ship from %s",
                package_id, picking.name,
            )
        return True
