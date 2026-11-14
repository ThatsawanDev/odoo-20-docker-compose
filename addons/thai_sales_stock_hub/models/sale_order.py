from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _hub_connector_values(self):
        self.ensure_one()
        for channel, ref_field, shop_field in (
            ("shopee", "shopee_order_ref", "shopee_shop_id"),
            ("lazada", "lazada_order_ref", "lazada_shop_id"),
            ("tiktok", "tiktok_order_id", "tiktok_shop_id"),
        ):
            reference = self[ref_field]
            if reference or self[shop_field]:
                values = {"hub_channel": channel}
                if reference:
                    values["hub_external_ref"] = reference
                return values
        return {}

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            values = order._hub_connector_values()
            if values:
                order.with_context(skip_hub_connector_sync=True).write(values)
        return orders

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get("skip_hub_connector_sync") and any(
            key in vals for key in (
                "shopee_order_ref", "shopee_shop_id", "lazada_order_ref", "lazada_shop_id",
                "tiktok_order_id", "tiktok_shop_id",
            )
        ):
            for order in self:
                values = order._hub_connector_values()
                if values:
                    order.with_context(skip_hub_connector_sync=True).write(values)
        return result

    hub_is_demo = fields.Boolean(string="ข้อมูลตัวอย่าง", default=False, copy=False, index=True)
    hub_product_image = fields.Image(string="รูปสินค้า", compute="_compute_hub_product_image")
    hub_channel_id = fields.Many2one(
        "thai.sales.stock.channel", string="ช่องทางขาย", compute="_compute_hub_channel_id",
        inverse="_inverse_hub_channel_id", store=True, readonly=False, index=True,
    )
    hub_channel_icon = fields.Image(string="ไอคอนช่องทาง", related="hub_channel_id.icon_128")

    @api.depends("hub_channel")
    def _compute_hub_channel_id(self):
        channels = self.env["thai.sales.stock.channel"].with_context(active_test=False).search([])
        by_code = {channel.code: channel for channel in channels}
        for order in self:
            order.hub_channel_id = by_code.get(order.hub_channel)

    def _inverse_hub_channel_id(self):
        for order in self:
            if order.hub_channel_id:
                order.hub_channel = order.hub_channel_id.code

    @api.depends("order_line.product_id", "order_line.product_id.image_128")
    def _compute_hub_product_image(self):
        for order in self:
            product_line = order.order_line.filtered(lambda line: line.product_id and not line.display_type)[:1]
            order.hub_product_image = product_line.product_id.image_128 if product_line else False

    hub_channel = fields.Selection(
        selection=[
            ("direct", "ขายตรง"),
            ("store", "หน้าร้าน"),
            ("website", "เว็บไซต์"),
            ("shopee", "Shopee"),
            ("lazada", "Lazada"),
            ("tiktok", "TikTok Shop"),
            ("other", "ช่องทางอื่น"),
        ],
        string="ช่องทางขาย",
        default="direct",
        required=True,
        index=True,
        tracking=True,
    )
    hub_external_ref = fields.Char(
        string="เลขออเดอร์จากช่องทาง",
        copy=False,
        index=True,
        tracking=True,
        help="เลขอ้างอิงจากระบบต้นทาง ใช้ค้นหาและตรวจสอบออเดอร์",
    )
    hub_fulfillment_state = fields.Selection(
        selection=[
            ("quotation", "รอยืนยัน"),
            ("to_ship", "รอจัดส่ง"),
            ("shipping", "กำลังจัดส่ง"),
            ("delivered", "จัดส่งแล้ว"),
            ("cancel", "ยกเลิก"),
        ],
        string="สถานะงาน",
        compute="_compute_hub_fulfillment_state",
    )

    @api.depends("state", "picking_ids.state", "picking_ids.picking_type_id.code")
    def _compute_hub_fulfillment_state(self):
        for order in self:
            outgoing = order.picking_ids.filtered(lambda p: p.picking_type_id.code == "outgoing")
            if order.state == "cancel":
                order.hub_fulfillment_state = "cancel"
            elif order.state in ("draft", "sent"):
                order.hub_fulfillment_state = "quotation"
            elif outgoing and all(p.state in ("done", "cancel") for p in outgoing) and any(p.state == "done" for p in outgoing):
                order.hub_fulfillment_state = "delivered"
            elif any(p.state == "assigned" for p in outgoing):
                order.hub_fulfillment_state = "shipping"
            else:
                order.hub_fulfillment_state = "to_ship"

