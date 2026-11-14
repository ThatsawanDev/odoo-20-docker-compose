# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.smart_sale_tiktok import utils


class TikTokItem(models.Model):
    _name = 'tiktok.item'
    _description = "TikTok Shop Mapped Item / SKU"
    _order = 'name'

    name = fields.Char(string="TikTok Product Title", required=True)
    shop_id = fields.Many2one('tiktok.shop', string="Shop", required=True, ondelete='cascade')
    tiktok_product_id = fields.Char(string="TikTok Product ID", required=True, copy=False)
    tiktok_sku_id = fields.Char(string="TikTok SKU ID", required=True, copy=False)
    
    product_id = fields.Many2one('product.product', string="Linked Odoo Product", required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='shop_id.company_id', store=True, readonly=True)
    
    sync_stock = fields.Boolean(string="Synchronize Inventory", default=True)
    last_synced_quantity = fields.Float(string="Last Synced Qty", readonly=True)
    last_inventory_sync_date = fields.Datetime(readonly=True, copy=False)
    last_inventory_sync_error = fields.Text(readonly=True, copy=False)

    @api.constrains('shop_id', 'tiktok_sku_id')
    def _check_unique_sku_per_shop(self):
        for record in self:
            domain = [
                ('shop_id', '=', record.shop_id.id),
                ('tiktok_sku_id', '=', record.tiktok_sku_id),
                ('id', '!=', record.id),
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(_("A TikTok SKU ID must be unique per Shop!"))

    def _get_inventory_quantity(self):
        self.ensure_one()
        product = self.product_id.with_company(self.company_id)
        if self.shop_id.warehouse_id:
            product = product.with_context(location=self.shop_id.warehouse_id.lot_stock_id.id)
        return max(0, int(product.free_qty))

    def _sync_inventory(self):
        """Push current Odoo available quantity to TikTok, grouped by product."""
        for product_id, items in self.filtered(
            lambda item: item.sync_stock and item.shop_id.state == 'active'
        ).grouped('tiktok_product_id').items():
            shop = items[0].shop_id
            inventory = []
            for item in items:
                quantity = item._get_inventory_quantity()
                inventory.append({'id': item.tiktok_sku_id, 'quantity': quantity})
            try:
                # The v202309 endpoint accepts SKU inventory rows. Shops using multiple
                # TikTok warehouses must extend each row with warehouse inventory data.
                utils.make_tiktok_api_request(
                    shop,
                    'update_stock',
                    body={'skus': inventory},
                    path_values={'product_id': product_id},
                )
                now = fields.Datetime.now()
                for item, row in zip(items, inventory):
                    item.write({
                        'last_synced_quantity': row['quantity'],
                        'last_inventory_sync_date': now,
                        'last_inventory_sync_error': False,
                    })
            except Exception as error:
                items.write({'last_inventory_sync_error': str(error)})
                raise
