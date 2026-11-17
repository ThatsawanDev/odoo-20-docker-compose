from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ServiceMachineAsset(models.Model):
    _inherit = "service.machine.asset"

    ownership_type = fields.Selection([
        ("sold", "ขาย"), ("rental", "เช่า"), ("loan", "ยืม"),
        ("company", "ทรัพย์สินบริษัท"),
    ], string="ประเภทการครอบครอง", default="sold", tracking=True)
    location_history_ids = fields.One2many("jsn.machine.location.history", "machine_id", string="ประวัติการย้าย")

    def action_record_location(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": "บันทึกการย้ายเครื่อง",
            "res_model": "jsn.machine.location.history", "view_mode": "form", "target": "new",
            "context": {"default_machine_id": self.id, "default_from_location": self.install_location},
        }


class MachineLocationHistory(models.Model):
    _name = "jsn.machine.location.history"
    _description = "ประวัติการย้ายเครื่อง"
    _order = "move_date desc, id desc"

    machine_id = fields.Many2one("service.machine.asset", string="เครื่อง", required=True, ondelete="cascade")
    move_date = fields.Date(string="วันที่ย้าย", default=fields.Date.today, required=True)
    from_location = fields.Char(string="จากสถานที่")
    to_location = fields.Char(string="ไปสถานที่", required=True)
    note = fields.Text(string="หมายเหตุ")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record.machine_id.install_location = record.to_location
        return records


class ServiceMachineModel(models.Model):
    _inherit = "service.machine.model"

    document_ids = fields.One2many("jsn.machine.document", "model_id", string="คู่มือและเอกสาร")


class MachineDocument(models.Model):
    _name = "jsn.machine.document"
    _description = "เอกสารรุ่นเครื่อง"

    name = fields.Char(string="ชื่อเอกสาร", required=True)
    model_id = fields.Many2one("service.machine.model", string="รุ่นเครื่อง", required=True, ondelete="cascade")
    document_type = fields.Selection([
        ("user", "คู่มือใช้งาน"), ("repair", "คู่มือซ่อม"), ("other", "อื่น ๆ"),
    ], string="ประเภท", required=True, default="user")
    attachment_id = fields.Many2one("ir.attachment", string="ไฟล์แนบ")
    note = fields.Text(string="รายละเอียด")


class ServiceOrder(models.Model):
    _inherit = "service.order"

    machine_image_128 = fields.Image(related="machine_id.image_1920", string="รูปเครื่อง", readonly=True)

    report_kind = fields.Selection([
        ("general", "ทั่วไป"), ("on_field", "บริการหน้างาน"),
        ("in_house", "ซ่อมภายใน"), ("receive", "รับเครื่องกลับ"),
        ("return", "ส่งเครื่องคืน"),
    ], string="ประเภทรายงานบริการ", required=True, default="general", tracking=True)
    repair_stage = fields.Selection([
        ("received", "รับงาน"), ("diagnosing", "ตรวจวิเคราะห์"),
        ("repairing", "กำลังซ่อม"), ("quotation", "เสนอราคา / รออนุมัติ"),
        ("testing", "ทดสอบ"), ("returned", "ส่งคืน"),
    ], string="ขั้นตอนงานซ่อม", default="received", tracking=True)
    document_number = fields.Char(string="เลขที่เอกสารลูกค้า")
    customer_po = fields.Char(string="เลขที่ PO อ้างอิง")
    issue_picking_id = fields.Many2one("stock.picking", string="ใบเบิกอะไหล่", readonly=True, copy=False)
    sale_order_id = fields.Many2one("sale.order", string="ใบเสนอราคา", readonly=True, copy=False)

    def action_create_quotation(self):
        self.ensure_one()
        if self.sale_order_id:
            return {"type": "ir.actions.act_window", "res_model": "sale.order", "res_id": self.sale_order_id.id, "view_mode": "form"}
        if self.billing_policy == "warranty":
            raise UserError(_("งานนี้อยู่ในประกัน หากมีรายการคิดเงิน กรุณาเปลี่ยนการคิดค่าบริการเป็น 'คิดค่าบริการ' ก่อนสร้างใบเสนอราคา"))
        labor = self.env.ref("jsn_service_scope.product_service_labor", raise_if_not_found=False)
        labor = labor or self.env["product.product"].search([("default_code", "=", "SVC-LABOR")], limit=1)
        if not labor:
            raise UserError(_("ไม่พบสินค้า 'ค่าแรงบริการช่าง' กรุณาสร้างสินค้าบริการรหัส SVC-LABOR ก่อน"))
        lines = []
        if self.labor_hours > 0:
            lines.append((0, 0, {
                "product_id": labor.id,
                "product_uom_qty": self.labor_hours,
                "price_unit": self.labor_rate,
            }))
        for part in self.part_line_ids.filtered(lambda line: line.new_product_id and line.quantity > 0):
            lines.append((0, 0, {
                "product_id": part.new_product_id.id,
                "product_uom_qty": part.quantity,
                "price_unit": part.unit_price or part.new_product_id.list_price,
            }))
        quotation = self.env["sale.order"].create({
            "partner_id": self.partner_id.id,
            "origin": self.name,
            "client_order_ref": self.customer_po,
            "order_line": lines,
        })
        self.sale_order_id = quotation
        return {"type": "ir.actions.act_window", "res_model": "sale.order", "res_id": quotation.id, "view_mode": "form"}

    def action_create_spare_issue(self):
        self.ensure_one()
        if self.issue_picking_id:
            return {"type": "ir.actions.act_window", "res_model": "stock.picking", "res_id": self.issue_picking_id.id, "view_mode": "form"}
        lines = self.part_line_ids.filtered(lambda line: line.new_product_id and line.quantity > 0 and line.action != "remove")
        if not lines:
            raise UserError(_("กรุณาระบุอะไหล่และจำนวนในใบงานก่อนเบิก"))
        warehouse = self.warehouse_id or self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)
        if not warehouse:
            raise UserError(_("ไม่พบคลังสินค้าของบริษัท"))
        needed = {}
        for line in lines:
            needed[line.new_product_id] = needed.get(line.new_product_id, 0) + line.quantity
        shortages = []
        for product, quantity in needed.items():
            available = self.env["stock.quant"]._get_available_quantity(product, warehouse.lot_stock_id)
            if available < quantity:
                shortages.append(_("%(product)s: ต้องการ %(need)s มี %(available)s", product=product.display_name, need=quantity, available=available))
        if shortages:
            raise UserError(_("อะไหล่ไม่พอ กรุณาสั่งซื้อและรับเข้าคลังก่อนเบิก:") + "\n" + "\n".join(shortages))
        picking_type = warehouse.out_type_id
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id or warehouse.lot_stock_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id or self.env.ref("stock.stock_location_customers").id,
            "partner_id": self.partner_id.id,
            "origin": self.name,
        })
        for line in lines:
            move = self.env["stock.move"].create({
                "product_id": line.new_product_id.id,
                "product_uom_qty": line.quantity,
                "uom_id": line.new_product_id.uom_id.id,
                "picking_id": picking.id,
                "location_id": picking_type.default_location_src_id.id or warehouse.lot_stock_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id or self.env.ref("stock.stock_location_customers").id,
            })
            line.issue_move_id = move
        picking.action_confirm()
        picking.action_assign()
        self.issue_picking_id = picking
        return {"type": "ir.actions.act_window", "res_model": "stock.picking", "res_id": picking.id, "view_mode": "form"}


class ServiceOrderPart(models.Model):
    _inherit = "service.order.part"

    issue_move_id = fields.Many2one("stock.move", string="รายการเบิกสต็อก", readonly=True, copy=False)
    available_qty = fields.Float(string="คงเหลือในคลัง", compute="_compute_available_qty", compute_sudo=True)

    @api.depends("new_product_id", "order_id.warehouse_id")
    def _compute_available_qty(self):
        for line in self:
            warehouse = line.order_id.warehouse_id
            line.available_qty = self.env["stock.quant"]._get_available_quantity(line.new_product_id, warehouse.lot_stock_id) if warehouse and line.new_product_id else 0


class AccountAsset(models.Model):
    _inherit = "account.asset.asset"

    service_machine_id = fields.Many2one("service.machine.asset", string="เครื่องจักรที่เกี่ยวข้อง", index=True)
    service_location = fields.Char(string="สถานที่จัดเก็บ")
    service_responsible_id = fields.Many2one("res.users", string="ผู้รับผิดชอบ")

