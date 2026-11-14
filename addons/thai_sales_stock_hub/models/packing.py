from datetime import datetime, time, timedelta

import pytz

import base64
import binascii

from odoo import api, fields, models
from odoo.exceptions import UserError


class PackingStation(models.Model):
    _name = "thai.sales.stock.packing.station"
    _description = "จุดแพ็กสินค้า"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    warehouse_id = fields.Many2one("stock.warehouse", required=True)
    company_id = fields.Many2one(related="warehouse_id.company_id", store=True)
    target_today = fields.Integer(string="เป้าหมายวันนี้", default=0)
    worker_count = fields.Integer(string="จำนวนพนักงาน", default=1)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    hub_packing_station_id = fields.Many2one("thai.sales.stock.packing.station", string="จุดแพ็ก", check_company=True)
    hub_packing_state = fields.Selection([
        ("waiting", "รอแพ็ก"), ("packing", "กำลังแพ็ก"), ("packed", "แพ็กเสร็จ"),
    ], string="สถานะแพ็ก", default="waiting", copy=False, tracking=True)
    hub_packed_at = fields.Datetime(string="แพ็กเสร็จเมื่อ", copy=False, readonly=True)
    hub_packer_id = fields.Many2one("res.users", string="พนักงานแพ็ก", copy=False)
    hub_pack_video_id = fields.Many2one("ir.attachment", string="วิดีโอการแพ็ก", copy=False, readonly=True)
    hub_pack_scan_ids = fields.One2many("thai.sales.stock.packing.scan", "picking_id", string="รายการสแกน", copy=False)
    hub_pack_box_count = fields.Integer(string="จำนวนกล่อง", default=1, copy=False)
    hub_line_count = fields.Integer(string="จำนวนรายการ", compute="_compute_hub_outgoing_quantities")
    hub_total_qty = fields.Float(string="จำนวนทั้งหมด", compute="_compute_hub_outgoing_quantities")
    hub_scanned_qty = fields.Float(string="สแกนแล้ว", compute="_compute_hub_outgoing_quantities")

    @api.depends("move_ids.product_uom_qty", "move_ids.state", "hub_pack_scan_ids.qty_scanned")
    def _compute_hub_outgoing_quantities(self):
        for picking in self:
            moves = picking.move_ids.filtered(lambda move: move.state != "cancel")
            picking.hub_line_count = len(moves)
            picking.hub_total_qty = sum(moves.mapped("product_uom_qty"))
            picking.hub_scanned_qty = sum(picking.hub_pack_scan_ids.mapped("qty_scanned"))

    @api.model
    def get_hub_outgoing_summary(self):
        domain = [("picking_type_id.code", "=", "outgoing"), ("state", "not in", ("done", "cancel"))]
        pickings = self.search(domain)
        return {
            "all": len(pickings),
            "waiting": len(pickings.filtered(lambda picking: picking.hub_packing_state == "waiting" and picking.state == "assigned")),
            "packing": len(pickings.filtered(lambda picking: picking.hub_packing_state == "packing")),
            "packed": len(pickings.filtered(lambda picking: picking.hub_packing_state == "packed")),
            "issues": len(pickings.filtered(lambda picking: picking.hub_packing_state == "waiting" and picking.state != "assigned")),
        }

    def action_hub_start_packing(self):
        for picking in self:
            if picking.picking_type_code != "outgoing" or picking.state != "assigned":
                raise UserError("เริ่มแพ็กได้เมื่อสินค้าในใบส่งพร้อมหยิบครบแล้วเท่านั้น")
            picking.write({"hub_packing_state": "packing", "hub_packer_id": self.env.user.id})

    def action_hub_open_packing_station(self):
        self.ensure_one()
        action = self.env.ref("thai_sales_stock_hub.action_hub_packing_station").read()[0]
        action["params"] = {"picking_id": self.id}
        return action

    def action_hub_finish_packing(self):
        for picking in self:
            if picking.hub_packing_state != "packing":
                raise UserError("กรุณาเริ่มแพ็กก่อนบันทึกว่าแพ็กเสร็จ")
            if not picking.hub_packing_station_id:
                raise UserError("กรุณาเลือกจุดแพ็ก")
            required = picking._hub_required_products()
            scanned = {line.product_id.id: line.qty_scanned for line in picking.hub_pack_scan_ids}
            if any(scanned.get(product_id, 0) < quantity for product_id, quantity in required.items()):
                raise UserError("กรุณาสแกนสินค้าให้ครบตามใบส่ง")
            if not picking.hub_pack_video_id:
                raise UserError("กรุณาบันทึกวิดีโอการแพ็กก่อนยืนยัน")
            picking.write({"hub_packing_state": "packed", "hub_packed_at": fields.Datetime.now()})

    def _hub_required_products(self):
        self.ensure_one()
        result = {}
        for move in self.move_ids.filtered(lambda item: item.state != "cancel"):
            result[move.product_id.id] = result.get(move.product_id.id, 0) + move.product_uom._compute_quantity(move.product_uom_qty, move.product_id.uom_id)
        return result


class PackingScan(models.Model):
    _name = "thai.sales.stock.packing.scan"
    _description = "จำนวนสินค้าที่สแกนสำหรับแพ็ก"
    _rec_name = "product_id"

    picking_id = fields.Many2one("stock.picking", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("product.product", required=True)
    qty_scanned = fields.Float(default=0, digits="Product Unit of Measure")
    company_id = fields.Many2one(related="picking_id.company_id", store=True)

    _unique_picking_product = models.Constraint("unique(picking_id, product_id)", "สแกนสินค้านี้ซ้ำในใบส่งเดียวกัน")


class PackingDashboard(models.AbstractModel):
    _name = "thai.sales.stock.hub.packing.dashboard"
    _description = "Packing Control Center"

    def _station_picking(self, picking_id):
        if not self.env.user.has_group("stock.group_stock_user"):
            raise UserError("ต้องมีสิทธิ์ใช้งานคลังสินค้า")
        picking = self.env["stock.picking"].browse(int(picking_id)).exists()
        if not picking or picking.picking_type_code != "outgoing" or picking.state in ("done", "cancel"):
            raise UserError("ไม่พบใบส่งสินค้าที่เปิดใช้งาน")
        picking.check_access("read")
        return picking

    @api.model
    def get_station_queue(self, station_id=False):
        if not self.env.user.has_group("stock.group_stock_user"):
            raise UserError("ต้องมีสิทธิ์ใช้งานคลังสินค้า")
        stations = self.env["thai.sales.stock.packing.station"].search([("company_id", "in", self.env.companies.ids)])
        station = self.env["thai.sales.stock.packing.station"]
        if station_id:
            station = stations.filtered(lambda item: item.id == int(station_id))[:1]
            if not station:
                raise UserError("ไม่พบจุดแพ็กที่เลือก")
        domain = [("company_id", "in", self.env.companies.ids), ("picking_type_code", "=", "outgoing"),
                  ("state", "not in", ["done", "cancel"]), ("hub_packing_state", "in", ["waiting", "packing"])]
        if station:
            domain += [("picking_type_id.warehouse_id", "=", station.warehouse_id.id),
                       "|", ("hub_packing_station_id", "=", False), ("hub_packing_station_id", "=", station.id)]
        pickings = self.env["stock.picking"].search(domain, order="scheduled_date asc, id asc", limit=60)
        return {"stations": [{"id": item.id, "name": item.name, "warehouse": item.warehouse_id.name} for item in stations],
                "can_manage_stations": self.env.user.has_group("stock.group_stock_manager"),
                "user": self.env.user.name, "queue": [{"id": item.id, "name": item.name,
                "customer": item.partner_id.name or "—", "state": item.hub_packing_state,
                "station_id": item.hub_packing_station_id.id or False} for item in pickings]}

    @api.model
    def get_station_order(self, picking_id):
        picking = self._station_picking(picking_id)
        required = picking._hub_required_products()
        scanned = {line.product_id.id: line.qty_scanned for line in picking.hub_pack_scan_ids}
        channels = self.env["thai.sales.stock.channel"].search([])
        channel = picking.sale_id.hub_channel_id
        if channel not in channels:
            channel = self.env["thai.sales.stock.channel"]
        products = self.env["product.product"].browse(list(required))
        return {"id": picking.id, "name": picking.name, "sale_name": picking.sale_id.name or "",
                "customer": picking.partner_id.name or "—", "phone": picking.partner_id.phone or picking.partner_id.mobile or "",
                "address": picking.partner_id.contact_address or "", "channel": channel.name or "—",
                "channel_icon": f"/web/image/thai.sales.stock.channel/{channel.id}/icon_128" if channel else "",
                "state": picking.hub_packing_state, "station_id": picking.hub_packing_station_id.id or False,
                "packer": picking.hub_packer_id.name or "", "video_id": picking.hub_pack_video_id.id or False,
                "box_count": picking.hub_pack_box_count,
                "lines": [{"id": product.id, "code": product.default_code or "", "barcode": product.barcode or "",
                           "name": product.display_name, "required": required[product.id], "scanned": scanned.get(product.id, 0),
                           "image": f"/web/image/product.product/{product.id}/image_128"} for product in products]}

    @api.model
    def start_station_order(self, picking_id, station_id):
        picking = self._station_picking(picking_id)
        stations = self.env["thai.sales.stock.packing.station"].search([("company_id", "in", self.env.companies.ids)])
        station = stations.filtered(lambda item: item.id == int(station_id))[:1]
        if not station or station.warehouse_id != picking.picking_type_id.warehouse_id:
            raise UserError("จุดแพ็กต้องอยู่ในคลังเดียวกับใบส่งสินค้า")
        if picking.hub_packing_station_id and picking.hub_packing_station_id != station:
            raise UserError("ใบส่งสินค้านี้ถูกมอบหมายให้จุดแพ็กอื่น")
        picking.write({"hub_packing_station_id": station.id, "hub_packer_id": self.env.user.id})
        picking.action_hub_start_packing()
        return self.get_station_order(picking.id)

    @api.model
    def scan_station_product(self, picking_id, barcode):
        picking = self._station_picking(picking_id)
        if picking.hub_packing_state != "packing" or not picking.hub_packing_station_id:
            raise UserError("กรุณาเริ่มงานที่จุดแพ็กก่อนสแกน")
        code = (barcode or "").strip()
        required = picking._hub_required_products()
        product = self.env["product.product"].browse(list(required)).filtered(
            lambda item: code and code in (item.barcode, item.default_code))[:1]
        if not product:
            raise UserError("ไม่พบรหัสสินค้านี้ในใบส่ง")
        line = picking.hub_pack_scan_ids.filtered(lambda item: item.product_id == product)[:1]
        if line and line.qty_scanned >= required[product.id]:
            raise UserError("สินค้านี้สแกนครบจำนวนแล้ว")
        if line:
            line.qty_scanned += 1
        else:
            self.env["thai.sales.stock.packing.scan"].create({"picking_id": picking.id, "product_id": product.id, "qty_scanned": 1})
        return self.get_station_order(picking.id)

    @api.model
    def save_station_video(self, picking_id, filename, data, mimetype):
        picking = self._station_picking(picking_id)
        if picking.hub_packing_state != "packing":
            raise UserError("กรุณาเริ่มแพ็กก่อนบันทึกวิดีโอ")
        if mimetype not in ("video/webm", "video/mp4") or not data or len(data) > 70_000_000:
            raise UserError("รองรับไฟล์ WebM หรือ MP4 ขนาดไม่เกินประมาณ 50 MB")
        try:
            base64.b64decode(data, validate=True)
        except (ValueError, TypeError, binascii.Error):
            raise UserError("ข้อมูลวิดีโอไม่ถูกต้อง")
        attachment = self.env["ir.attachment"].create({"name": filename or f"packing-{picking.name}.webm",
            "res_model": "stock.picking", "res_id": picking.id, "type": "binary", "datas": data, "mimetype": mimetype})
        self.env["thai.sales.stock.packing.video"].create({
            "name": attachment.name, "picking_id": picking.id, "attachment_id": attachment.id,
            "packer_id": self.env.user.id, "station_id": picking.hub_packing_station_id.id,
        })
        picking.hub_pack_video_id = attachment.id
        return self.get_station_order(picking.id)

    @api.model
    def next_station_box(self, picking_id):
        picking = self._station_picking(picking_id)
        if picking.hub_packing_state != "packing":
            raise UserError("กรุณาเริ่มแพ็กก่อนเปลี่ยนกล่อง")
        picking.hub_pack_box_count += 1
        return self.get_station_order(picking.id)

    @api.model
    def finish_station_order(self, picking_id):
        picking = self._station_picking(picking_id)
        picking.action_hub_finish_packing()
        return True

    @api.model
    def get_overview(self, warehouse_id=False):
        companies = self.env.companies
        warehouses = self.env["stock.warehouse"].search([("company_id", "in", companies.ids)])
        if warehouse_id:
            warehouse_id = int(warehouse_id)
            if warehouse_id not in warehouses.ids:
                raise UserError("ไม่มีสิทธิ์เข้าถึงคลังสินค้าที่เลือก")
        today = fields.Date.context_today(self)
        tz = pytz.timezone(self.env.user.tz or "UTC")
        start = tz.localize(datetime.combine(today, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        end = tz.localize(datetime.combine(today + timedelta(days=1), time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        domain = [("company_id", "in", companies.ids), ("picking_type_code", "=", "outgoing")]
        if warehouse_id:
            domain.append(("picking_type_id.warehouse_id", "=", warehouse_id))
        picking = self.env["stock.picking"]
        open_domain = domain + [("state", "not in", ["done", "cancel"])]
        stages = {
            "waiting": picking.search_count(open_domain + [("hub_packing_state", "=", "waiting")]),
            "packing": picking.search_count(open_domain + [("hub_packing_state", "=", "packing")]),
            "packed": picking.search_count(open_domain + [("hub_packing_state", "=", "packed")]),
        }
        done_today = picking.search_count(domain + [("state", "=", "done"), ("date_done", ">=", start), ("date_done", "<", end)])
        ready_to_ship = picking.search_count(open_domain + [("hub_packing_state", "=", "packed"), ("state", "=", "assigned")])
        sale_domain = [("company_id", "in", companies.ids), ("state", "in", ["sale", "done"])]
        if warehouse_id:
            sale_domain.append(("warehouse_id", "=", warehouse_id))
        orders_today = self.env["sale.order"].search_count(sale_domain + [("date_order", ">=", start), ("date_order", "<", end)])
        queue = picking.browse()
        for stage in ("waiting", "packing", "packed"):
            queue |= picking.search(open_domain + [("hub_packing_state", "=", stage)], order="scheduled_date asc, id asc", limit=8)
        channels = self.env["thai.sales.stock.channel"].search([])
        icon_by_code = {item.code: f"/web/image/thai.sales.stock.channel/{item.id}/icon_128" for item in channels}
        rows = []
        for record in queue:
            sale = record.sale_id
            rows.append({
                "id": record.id, "name": record.name, "channel": sale.hub_channel_id.name if sale and sale.hub_channel_id else "—",
                "channel_icon": icon_by_code.get(sale.hub_channel or "") if sale else "",
                "customer": record.partner_id.name or "—", "items": len(record.move_ids),
                "state": record.hub_packing_state, "deadline": fields.Datetime.to_string(record.scheduled_date) if record.scheduled_date else "",
                "station": record.hub_packing_station_id.name or "—",
            })
        station_domain = [("company_id", "in", companies.ids)]
        if warehouse_id:
            station_domain.append(("warehouse_id", "=", warehouse_id))
        stations = []
        for station in self.env["thai.sales.stock.packing.station"].search(station_domain):
            count = picking.search_count(domain + [("hub_packing_station_id", "=", station.id), ("hub_packed_at", ">=", start), ("hub_packed_at", "<", end)])
            stations.append({"id": station.id, "name": station.name, "workers": station.worker_count, "packed": count,
                             "target": station.target_today, "percent": round(count / station.target_today * 100) if station.target_today else 0})
        return {
            "date": today.strftime("%d/%m/%Y"), "date_start": fields.Datetime.to_string(start), "date_end": fields.Datetime.to_string(end),
            "warehouses": [{"id": w.id, "name": w.display_name} for w in warehouses],
            "selected_warehouse": warehouse_id or False, "orders_today": orders_today,
            "open_total": sum(stages.values()), "stages": stages, "ready_to_ship": ready_to_ship, "done_today": done_today,
            "queue": rows, "stations": stations,
            "can_manage_stations": self.env.user.has_group("stock.group_stock_manager"),
        }
