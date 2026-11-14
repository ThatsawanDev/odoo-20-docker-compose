from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ThaiSalesStockChannel(models.Model):
    _name = "thai.sales.stock.channel"
    _description = "ช่องทางการขาย"
    _order = "sequence, id"

    name = fields.Char(string="ชื่อช่องทาง", required=True, translate=True)
    code = fields.Selection(
        [("direct", "ขายตรง"), ("store", "หน้าร้าน"), ("website", "เว็บไซต์"),
         ("shopee", "Shopee"), ("lazada", "Lazada"), ("tiktok", "TikTok Shop"),
         ("other", "ช่องทางอื่น")],
        string="รหัสช่องทาง", required=True, readonly=True, index=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(string="เปิดใช้", default=True)
    icon_128 = fields.Image(string="ไอคอน", max_width=128, max_height=128, attachment=False)
    description = fields.Char(string="หมายเหตุ")

    @api.constrains("code")
    def _check_unique_code(self):
        for channel in self:
            if self.search_count([("code", "=", channel.code), ("id", "!=", channel.id)]):
                raise ValidationError("รหัสช่องทางขายนี้มีอยู่แล้ว")
