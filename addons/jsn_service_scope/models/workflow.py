from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MachineAsset(models.Model):
    _inherit = "service.machine.asset"

    sale_order_id = fields.Many2one("sale.order", string="ใบขายเครื่อง", readonly=True, copy=False, index=True)
    delivery_picking_id = fields.Many2one("stock.picking", string="ใบส่งเครื่อง", readonly=True, copy=False)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    service_machine_ids = fields.One2many("service.machine.asset", "sale_order_id", string="เครื่องที่ขาย")
    service_machine_count = fields.Integer(compute="_compute_service_machine_count", string="เครื่องที่ลงทะเบียน")

    @api.depends("service_machine_ids")
    def _compute_service_machine_count(self):
        for order in self:
            order.service_machine_count = len(order.service_machine_ids)

    def action_register_service_machine(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": "ลงทะเบียนเครื่องจากใบขาย",
            "res_model": "jsn.sale.machine.wizard", "view_mode": "form", "target": "new",
            "context": {"default_sale_order_id": self.id},
        }

    def action_view_service_machines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": "เครื่องที่ขาย",
            "res_model": "service.machine.asset", "view_mode": "list,form",
            "domain": [("sale_order_id", "=", self.id)],
        }


class SaleMachineWizard(models.TransientModel):
    _name = "jsn.sale.machine.wizard"
    _description = "ลงทะเบียนเครื่องจากใบขายที่ส่งแล้ว"

    sale_order_id = fields.Many2one("sale.order", required=True, readonly=True, string="ใบขาย")
    product_id = fields.Many2one("product.product", required=True, string="สินค้าเครื่อง")
    model_id = fields.Many2one("service.machine.model", required=True, string="รุ่นเครื่อง")
    lot_id = fields.Many2one("stock.lot", string="S/N จากใบส่งสินค้า", domain="[('product_id', '=', product_id)]")
    serial_number = fields.Char(string="หมายเลขเครื่อง S/N")
    install_location = fields.Char(string="สถานที่ติดตั้ง")
    installation_date = fields.Date(string="วันที่ติดตั้ง", default=fields.Date.today)
    warranty_end_date = fields.Date(string="สิ้นสุดประกัน")

    @api.onchange("lot_id")
    def _onchange_lot_id(self):
        if self.lot_id:
            self.serial_number = self.lot_id.name

    def action_register(self):
        self.ensure_one()
        sale = self.sale_order_id
        if sale.state != "sale":
            raise UserError(_("กรุณายืนยันใบขายก่อนลงทะเบียนเครื่อง"))
        if self.product_id not in sale.order_line.mapped("product_id"):
            raise UserError(_("สินค้าเครื่องต้องอยู่ในใบขายนี้"))
        done_pickings = sale.picking_ids.filtered(lambda picking: picking.state == "done")
        if not done_pickings:
            raise UserError(_("กรุณายืนยันใบส่งสินค้าก่อนลงทะเบียนเครื่อง"))
        delivered_lines = done_pickings.move_line_ids.filtered(
            lambda line: line.product_id == self.product_id and line.quantity > 0
        )
        if not delivered_lines:
            raise UserError(_("ไม่พบสินค้าเครื่องที่ส่งแล้วในใบขายนี้"))
        if self.product_id.tracking == "serial":
            if not self.lot_id or self.lot_id not in delivered_lines.mapped("lot_id"):
                raise UserError(_("กรุณาเลือก S/N ที่ส่งแล้วจากใบส่งสินค้านี้"))
        serial = self.lot_id.name if self.lot_id else (self.serial_number or "").strip()
        if not serial:
            raise UserError(_("กรุณาระบุหมายเลขเครื่อง S/N"))
        if self.env["service.machine.asset"].search([("serial_number", "=", serial)], limit=1):
            raise ValidationError(_("หมายเลขเครื่อง S/N นี้ถูกลงทะเบียนแล้ว"))
        machine = self.env["service.machine.asset"].create({
            "name": self.model_id.name,
            "model_id": self.model_id.id,
            "product_id": self.product_id.id,
            "serial_number": serial,
            "lot_id": self.lot_id.id or False,
            "partner_id": sale.partner_id.id,
            "sale_order_id": sale.id,
            "delivery_picking_id": delivered_lines[0].picking_id.id,
            "delivery_date": fields.Date.today(),
            "installation_date": self.installation_date,
            "warranty_start_date": self.installation_date,
            "warranty_end_date": self.warranty_end_date,
            "install_location": self.install_location,
            "ownership_type": "sold",
            "state": "operational",
        })
        return {"type": "ir.actions.act_window", "res_model": "service.machine.asset", "res_id": machine.id, "view_mode": "form"}


class ServiceOrder(models.Model):
    _inherit = "service.order"

    billing_policy = fields.Selection([
        ("warranty", "อยู่ในประกัน ไม่คิดค่าบริการ"),
        ("contract", "ตามสัญญาบริการ"),
        ("billable", "คิดค่าบริการ"),
    ], string="การคิดค่าบริการ", default="billable", required=True, tracking=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="คลังอะไหล่", default=lambda self: self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1))
    purchase_order_id = fields.Many2one("purchase.order", string="ใบสั่งซื้ออะไหล่", readonly=True, copy=False)

    @api.onchange("machine_id")
    def _onchange_machine_warranty(self):
        if self.machine_id and self.machine_id.warranty_status == "in_warranty":
            self.billing_policy = "warranty"

    def action_create_parts_purchase(self):
        self.ensure_one()
        if self.purchase_order_id:
            return {"type": "ir.actions.act_window", "res_model": "purchase.order", "res_id": self.purchase_order_id.id, "view_mode": "form"}
        return {
            "type": "ir.actions.act_window", "name": "สั่งซื้ออะไหล่ที่ขาด",
            "res_model": "jsn.service.purchase.wizard", "view_mode": "form", "target": "new",
            "context": {"default_service_order_id": self.id, "default_warehouse_id": self.warehouse_id.id},
        }

    def _check_parts_issued(self):
        for order in self:
            needing_parts = order.part_line_ids.filtered(lambda line: line.new_product_id and line.quantity > 0 and line.action != "remove")
            if needing_parts and (not order.issue_picking_id or order.issue_picking_id.state != "done"):
                raise UserError(_("กรุณายืนยันใบเบิกอะไหล่ให้เสร็จก่อนบันทึกการเปลี่ยนชิ้นส่วนหรือปิดงาน"))

    def action_apply_parts(self):
        self._check_parts_issued()
        return super().action_apply_parts()

    def action_done(self):
        self._check_parts_issued()
        return super().action_done()


class ServicePurchaseWizard(models.TransientModel):
    _name = "jsn.service.purchase.wizard"
    _description = "สั่งซื้ออะไหล่ที่ขาดสำหรับใบงานบริการ"

    service_order_id = fields.Many2one("service.order", required=True, readonly=True, string="ใบงานบริการ")
    vendor_id = fields.Many2one("res.partner", required=True, string="ผู้ขาย", domain="[('supplier_rank', '>', 0)]")
    warehouse_id = fields.Many2one("stock.warehouse", required=True, string="คลังรับเข้า")

    def action_create_purchase(self):
        self.ensure_one()
        order = self.service_order_id
        if order.purchase_order_id:
            raise UserError(_("ใบงานนี้มีใบสั่งซื้ออะไหล่แล้ว"))
        needed = {}
        for line in order.part_line_ids.filtered(lambda part: part.new_product_id and part.quantity > 0 and part.action != "remove"):
            needed[line.new_product_id] = needed.get(line.new_product_id, 0) + line.quantity
        lines = []
        for product, quantity in needed.items():
            available = self.env["stock.quant"]._get_available_quantity(product, self.warehouse_id.lot_stock_id)
            shortage = max(quantity - available, 0)
            if shortage:
                lines.append((0, 0, {
                    "product_id": product.id,
                    "product_qty": shortage,
                    "uom_id": product.uom_id.id,
                    "price_unit": product.standard_price,
                    "date_planned": fields.Datetime.now(),
                }))
        if not lines:
            raise UserError(_("อะไหล่ในคลังมีเพียงพอแล้ว ไม่ต้องสร้างใบสั่งซื้อ"))
        purchase = self.env["purchase.order"].create({
            "partner_id": self.vendor_id.id,
            "picking_type_id": self.warehouse_id.in_type_id.id,
            "origin": order.name,
            "order_line": lines,
        })
        order.purchase_order_id = purchase
        return {"type": "ir.actions.act_window", "res_model": "purchase.order", "res_id": purchase.id, "view_mode": "form"}
