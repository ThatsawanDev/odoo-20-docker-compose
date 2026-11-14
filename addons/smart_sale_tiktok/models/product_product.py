# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    tiktok_item_ids = fields.One2many('tiktok.item', 'product_id', string="TikTok Mapped SKUs")
