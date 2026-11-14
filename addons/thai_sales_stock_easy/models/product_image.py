from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    thai_image_ids = fields.One2many(
        "thai.product.image", "product_tmpl_id", string="รูปสินค้าเพิ่มเติม"
    )


class ThaiProductImage(models.Model):
    _name = "thai.product.image"
    _description = "รูปสินค้าเพิ่มเติม"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="คำอธิบายรูป", required=True, default="รูปสินค้า")
    product_tmpl_id = fields.Many2one(
        "product.template", string="สินค้า", required=True, ondelete="cascade", index=True
    )
    image_1920 = fields.Image(
        string="รูปภาพ", required=True, max_width=1920, max_height=1920
    )
