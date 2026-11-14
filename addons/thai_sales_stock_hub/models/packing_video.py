from html import escape

from odoo import api, fields, models


class PackingVideo(models.Model):
    _name = "thai.sales.stock.packing.video"
    _description = "หลักฐานวิดีโอการแพ็ก"
    _rec_name = "picking_id"
    _order = "recorded_at desc, id desc"

    name = fields.Char(required=True, readonly=True)
    picking_id = fields.Many2one("stock.picking", required=True, readonly=True, index=True, ondelete="cascade")
    attachment_id = fields.Many2one("ir.attachment", required=True, readonly=True, ondelete="cascade")
    recorded_at = fields.Datetime(default=fields.Datetime.now, required=True, readonly=True, index=True)
    packer_id = fields.Many2one("res.users", readonly=True)
    station_id = fields.Many2one("thai.sales.stock.packing.station", readonly=True)
    company_id = fields.Many2one(related="picking_id.company_id", store=True, index=True)
    sale_id = fields.Many2one(related="picking_id.sale_id", store=True)
    is_demo = fields.Boolean(related="sale_id.hub_is_demo", store=True, string="ข้อมูลตัวอย่าง")
    partner_id = fields.Many2one(related="picking_id.partner_id", store=True)
    carrier_tracking_ref = fields.Char(related="picking_id.carrier_tracking_ref", store=True)
    hub_external_ref = fields.Char(related="sale_id.hub_external_ref", store=True)
    hub_channel_id = fields.Many2one(related="sale_id.hub_channel_id", store=True)
    hub_channel_icon = fields.Image(related="hub_channel_id.icon_128")
    hub_packing_state = fields.Selection(related="picking_id.hub_packing_state", store=True)
    picking_state = fields.Selection(related="picking_id.state")
    product_count = fields.Integer(compute="_compute_products_html")
    products_html = fields.Html(compute="_compute_products_html", sanitize=False)
    video_html = fields.Html(compute="_compute_video_html", sanitize=False)

    @api.depends("picking_id.move_ids.product_id", "picking_id.move_ids.product_uom_qty", "picking_id.hub_pack_scan_ids.qty_scanned")
    def _compute_products_html(self):
        for video in self:
            picking = video.picking_id
            required = picking._hub_required_products() if picking else {}
            scanned = {line.product_id.id: line.qty_scanned for line in picking.hub_pack_scan_ids}
            products = self.env["product.product"].browse(list(required))
            video.product_count = len(products)
            rows = []
            for index, product in enumerate(products, 1):
                code = escape(product.default_code or product.barcode or "—")
                name = escape(product.name or "")
                qty = required[product.id]
                done = scanned.get(product.id, 0)
                uom = escape(product.uom_id.name or "")
                rows.append(
                    f'<tr><td>{index}</td><td><img src="/web/image/product.product/{product.id}/image_128" '
                    f'alt=""/><span>{name}</span></td><td>{code}</td><td>{done:g} / {qty:g}</td><td>{uom}</td></tr>'
                )
            video.products_html = (
                '<table class="o_hub_video_products_table"><thead><tr><th>#</th><th>สินค้า</th><th>รหัสสินค้า</th>'
                '<th>แพ็กแล้ว / ทั้งหมด</th><th>หน่วย</th></tr></thead><tbody>'
                + ("".join(rows) or '<tr><td colspan="5">ไม่มีสินค้าในใบส่ง</td></tr>')
                + "</tbody></table>"
            )

    @api.depends("attachment_id")
    def _compute_video_html(self):
        for video in self:
            video.video_html = (
                f'<video controls preload="metadata" playsinline style="display:block;width:100%;min-height:280px;max-height:520px;background:#0b1c35;border-radius:14px" '
                f'src="/web/content/{video.attachment_id.id}"></video>'
            ) if video.attachment_id else False

    def action_download_video(self):
        self.ensure_one()
        self.check_access("read")
        return {"type": "ir.actions.act_url", "url": f"/web/content/{self.attachment_id.id}?download=true", "target": "self"}
