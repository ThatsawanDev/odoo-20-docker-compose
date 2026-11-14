from odoo import _, fields, models
from odoo.exceptions import UserError


class ThaiQuickStockIssue(models.TransientModel):
    _name = "thai.quick.stock.issue"
    _description = "เบิกสินค้าออกแบบง่าย"

    partner_id = fields.Many2one("res.partner", string="ลูกค้า / ผู้รับสินค้า")
    product_id = fields.Many2one(
        "product.product", string="สินค้า", required=True,
        domain="[('is_storable', '=', True)]",
    )
    quantity = fields.Float(string="จำนวนที่เบิก", required=True, default=1.0)
    product_uom_id = fields.Many2one(related="product_id.uom_id", string="หน่วย", readonly=True)
    note = fields.Char(string="หมายเหตุ / เลขที่อ้างอิง")

    def action_issue_now(self):
        self.ensure_one()
        if self.quantity <= 0:
            raise UserError(_("จำนวนที่เบิกต้องมากกว่า 0"))
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], order="sequence, id", limit=1
        )
        if not warehouse:
            raise UserError(_("ยังไม่มีคลังสินค้าหลัก กรุณาให้ผู้ดูแลระบบตั้งค่าคลังก่อน"))
        destination = (self.partner_id.property_stock_customer if self.partner_id else
                       self.env.ref("stock.stock_location_customers"))
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.out_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": destination.id,
            "partner_id": self.partner_id.id,
            "origin": self.note or _("เบิกสินค้าออกแบบง่าย"),
        })
        move = self.env["stock.move"].create({
            "name": self.product_id.display_name,
            "product_id": self.product_id.id,
            "product_uom_qty": self.quantity,
            "product_uom": self.product_uom_id.id,
            "picking_id": picking.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": destination.id,
        })
        picking.action_confirm()
        picking.action_assign()
        if self.product_id.tracking == "none":
            move.quantity = self.quantity
            result = picking.button_validate()
            if isinstance(result, dict):
                return result
        return {
            "type": "ir.actions.act_window",
            "name": _("ใบส่งสินค้า"),
            "res_model": "stock.picking",
            "res_id": picking.id,
            "view_mode": "form",
            "target": "current",
        }
