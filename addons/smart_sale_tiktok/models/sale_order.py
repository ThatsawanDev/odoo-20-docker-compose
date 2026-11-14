# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    tiktok_order_id = fields.Char(string="TikTok Order SN", copy=False, readonly=True, index=True)
    tiktok_shop_id = fields.Many2one('tiktok.shop', string="TikTok Shop", copy=False, readonly=True)
    tiktok_order_status = fields.Char(string="TikTok Status", copy=False, readonly=True)
    tiktok_package_id = fields.Char(string="TikTok Package ID", copy=False, readonly=True)
    tiktok_delivery_option = fields.Char(
        string="TikTok Delivery Option", copy=False, readonly=True,
    )
    tiktok_last_update = fields.Datetime(copy=False, readonly=True)
    is_tiktok_order = fields.Boolean(compute='_compute_is_tiktok_order', store=True)

    @api.depends('tiktok_order_id', 'tiktok_shop_id')
    def _compute_is_tiktok_order(self):
        for order in self:
            order.is_tiktok_order = bool(order.tiktok_order_id or order.tiktok_shop_id)

    def _apply_tiktok_status(self):
        """Apply marketplace state without allowing TikTok to invoice in Odoo."""
        for order in self.filtered('is_tiktok_order'):
            status = order.tiktok_order_status
            if status in ('CANCEL', 'CANCELLED') and order.state != 'cancel':
                order._action_cancel()
            elif status in (
                'AWAITING_SHIPMENT', 'AWAITING_COLLECTION', 'IN_TRANSIT',
                'DELIVERED', 'COMPLETED',
            ) and order.state in ('draft', 'sent') and order.order_line:
                order.action_confirm()
            if status in ('DELIVERED', 'COMPLETED'):
                for picking in order.picking_ids.filtered(
                    lambda picking: picking.state not in ('done', 'cancel')
                ):
                    picking.with_context(skip_tiktok_rts=True).button_validate()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    tiktok_order_item_id = fields.Char(string="TikTok Item ID", copy=False, readonly=True)
    tiktok_sku_id = fields.Char(string="TikTok SKU ID", copy=False, readonly=True)
    tiktok_seller_sku = fields.Char(string="TikTok Seller SKU", copy=False, readonly=True)
