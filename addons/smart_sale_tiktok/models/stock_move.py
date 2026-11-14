# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        res = super()._action_done(cancel_backorder=cancel_backorder)
        # Check if any completed stock move affects products mapped to TikTok items
        products = res.mapped('product_id').filtered(lambda p: p.tiktok_item_ids)
        if products:
            items = products.tiktok_item_ids.filtered(
                lambda item: item.sync_stock and item.shop_id.state == 'active'
            )
            for shop, shop_items in items.grouped('shop_id').items():
                try:
                    shop_items._sync_inventory()
                    shop.last_inventory_sync_date = fields.Datetime.now()
                except Exception:
                    # Do not roll back a warehouse operation because a marketplace is
                    # temporarily unavailable; the inventory cron is the reconciliation path.
                    _logger.exception(
                        "Immediate TikTok stock sync failed for shop %s", shop.display_name,
                    )
        return res
