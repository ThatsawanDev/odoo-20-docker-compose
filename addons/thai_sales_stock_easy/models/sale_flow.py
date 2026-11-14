from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def get_thai_list_summary(self):
        company_domain = [("company_id", "=", self.env.company.id)]
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        month_orders = self.search(company_domain + [
            ("state", "in", ("sale", "done")),
            ("date_order", ">=", month_start),
        ])
        return {
            "draft": self.search_count(company_domain + [("state", "=", "draft")]),
            "sent": self.search_count(company_domain + [("state", "=", "sent")]),
            "confirmed": self.search_count(company_domain + [("state", "in", ("sale", "done"))]),
            "month_total": sum(month_orders.mapped("amount_total")),
            "currency": self.env.company.currency_id.symbol or self.env.company.currency_id.name,
        }

    thai_easy_enable_pricelist = fields.Boolean(
        related="company_id.thai_easy_enable_pricelist",
        readonly=True,
    )

    @api.depends("company_id")
    def _compute_require_signature(self):
        """Use online customer approval by default for the simplified sales flow."""
        for order in self:
            order.require_signature = True

    def _has_to_be_signed(self):
        """Allow customer approval from the portal until a signature is recorded.

        The simplified backend flow may confirm the order before the customer opens
        the portal, so the standard draft/sent-only condition is too restrictive.
        """
        self.ensure_one()
        return (
            self.state in ("draft", "sent", "sale")
            and not self.is_expired
            and not self.signature
        )

    def _validate_order(self):
        """Do not confirm an order a second time when a portal customer signs it."""
        orders_to_confirm = self.filtered(lambda order: order.state in ("draft", "sent"))
        if orders_to_confirm:
            return super(SaleOrder, orders_to_confirm)._validate_order()
        return None

    easy_line_count = fields.Integer(
        string="จำนวนรายการ",
        compute="_compute_easy_line_count",
    )
    easy_customer_phone = fields.Char(string="เบอร์โทร", related="partner_id.phone")
    easy_customer_email = fields.Char(string="อีเมล", related="partner_id.email")
    easy_has_open_invoice = fields.Boolean(
        string="มีใบแจ้งหนี้ค้างชำระ",
        compute="_compute_easy_has_open_invoice",
    )
    easy_shipping_address = fields.Text(
        string="ที่อยู่จัดส่ง",
        compute="_compute_easy_shipping_address",
        inverse="_inverse_easy_shipping_address",
        store=True,
        readonly=False,
    )
    easy_shipping_street = fields.Char(string="บ้านเลขที่ หมู่ ซอย ถนน", compute="_compute_easy_shipping_parts", inverse="_inverse_easy_shipping_parts", store=True, readonly=False)
    easy_shipping_street2 = fields.Char(string="รายละเอียดที่อยู่เพิ่มเติม", compute="_compute_easy_shipping_parts", inverse="_inverse_easy_shipping_parts", store=True, readonly=False)
    easy_shipping_province_id = fields.Many2one("province", string="จังหวัด", compute="_compute_easy_shipping_parts", inverse="_inverse_easy_shipping_parts", store=True, readonly=False)
    easy_shipping_amphur_id = fields.Many2one("amphur", string="อำเภอ / เขต", compute="_compute_easy_shipping_parts", inverse="_inverse_easy_shipping_parts", store=True, readonly=False)
    easy_shipping_tambon_id = fields.Many2one("tambon", string="ตำบล / แขวง", compute="_compute_easy_shipping_parts", inverse="_inverse_easy_shipping_parts", store=True, readonly=False)
    easy_shipping_postcode_id = fields.Many2one("zip", string="รหัสไปรษณีย์", compute="_compute_easy_shipping_parts", inverse="_inverse_easy_shipping_parts", store=True, readonly=False)
    easy_tracking_number = fields.Char(
        string="เลข Tracking",
        copy=False,
        tracking=True,
    )
    easy_internal_note = fields.Text(
        string="หมายเหตุภายใน",
        copy=False,
        tracking=True,
    )
    easy_invoice_before_delivery = fields.Boolean(
        string="ออกใบแจ้งหนี้ก่อนจัดส่ง",
        compute="_compute_easy_flow_sequence",
    )
    easy_quotation_datetime = fields.Datetime(
        string="วันเวลาสร้างใบเสนอราคา",
        compute="_compute_easy_timeline_dates",
    )
    easy_confirmation_datetime = fields.Datetime(
        string="วันเวลายืนยันการขาย",
        compute="_compute_easy_timeline_dates",
    )
    easy_delivery_datetime = fields.Datetime(
        string="วันเวลาจัดส่ง",
        compute="_compute_easy_timeline_dates",
    )
    easy_invoice_datetime = fields.Datetime(
        string="วันเวลาออกเอกสารการเงิน",
        compute="_compute_easy_timeline_dates",
    )
    easy_payment_datetime = fields.Datetime(
        string="วันเวลารับเงิน",
        compute="_compute_easy_timeline_dates",
    )
    easy_flow_state_delivery_first = fields.Selection(
        [
            ("quotation", "ใบเสนอราคา"),
            ("confirmation", "ยืนยันการขาย"),
            ("delivery", "ตัดสต็อก/จัดส่ง"),
            ("invoice", "เอกสารการเงิน"),
            ("payment", "รับเงิน"),
            ("cancel", "ยกเลิก"),
        ],
        compute="_compute_easy_flow_state",
        string="ขั้นตอนการขาย",
    )
    easy_flow_state_invoice_first = fields.Selection(
        [
            ("quotation", "ใบเสนอราคา"),
            ("confirmation", "ยืนยันการขาย"),
            ("invoice", "เอกสารการเงิน"),
            ("delivery", "ตัดสต็อก/จัดส่ง"),
            ("payment", "รับเงิน"),
            ("cancel", "ยกเลิก"),
        ],
        compute="_compute_easy_flow_state",
        string="ขั้นตอนการขาย",
    )

    @api.depends(
        "state",
        "easy_invoice_before_delivery",
        "easy_invoice_datetime",
        "easy_delivery_datetime",
        "easy_payment_datetime",
    )
    def _compute_easy_flow_state(self):
        for order in self:
            if order.state == "cancel":
                stage = "cancel"
            elif order.easy_payment_datetime:
                stage = "payment"
            elif order.easy_invoice_before_delivery:
                stage = "delivery" if order.easy_delivery_datetime else (
                    "invoice" if order.easy_invoice_datetime else (
                        "confirmation" if order.state in ("sale", "done") else "quotation"
                    )
                )
            else:
                stage = "invoice" if order.easy_invoice_datetime else (
                    "delivery" if order.easy_delivery_datetime else (
                        "confirmation" if order.state in ("sale", "done") else "quotation"
                    )
                )
            order.easy_flow_state_delivery_first = stage
            order.easy_flow_state_invoice_first = stage

    @api.depends("order_line.display_type")
    def _compute_easy_line_count(self):
        for order in self:
            order.easy_line_count = len(order.order_line.filtered(lambda line: not line.display_type))

    @api.depends("invoice_ids.state", "invoice_ids.move_type", "invoice_ids.amount_residual")
    def _compute_easy_has_open_invoice(self):
        for order in self:
            order.easy_has_open_invoice = any(
                invoice.move_type == "out_invoice"
                and invoice.state == "posted"
                and invoice.amount_residual > 0
                for invoice in order.invoice_ids
            )

    @api.depends(
        "easy_shipping_street",
        "easy_shipping_street2",
        "easy_shipping_province_id",
        "easy_shipping_amphur_id",
        "easy_shipping_tambon_id",
        "easy_shipping_postcode_id",
        "partner_shipping_id.city",
        "partner_shipping_id.state_id",
        "partner_shipping_id.zip",
        "partner_shipping_id.country_id",
    )
    def _compute_easy_shipping_address(self):
        for order in self:
            shipping = order.partner_shipping_id
            locality = " ".join(filter(None, [
                order.easy_shipping_tambon_id.name,
                order.easy_shipping_amphur_id.name,
                order.easy_shipping_province_id.name,
                order.easy_shipping_postcode_id.name,
            ])) or " ".join(filter(None, [shipping.city, shipping.state_id.name, shipping.zip]))
            order.easy_shipping_address = "\n".join(filter(None, [
                order.easy_shipping_street,
                order.easy_shipping_street2,
                locality,
                shipping.country_id.name if shipping.country_id.code != "TH" else False,
            ]))

    def _inverse_easy_shipping_address(self):
        """Keep order-specific addresses without changing the customer master."""
        return

    @api.depends(
        "partner_shipping_id",
        "partner_shipping_id.street",
        "partner_shipping_id.street2",
        "partner_shipping_id.province_id",
        "partner_shipping_id.amphur_id",
        "partner_shipping_id.tambon_id",
        "partner_shipping_id.thai_postcode_id",
        "partner_shipping_id.city",
        "partner_shipping_id.state_id",
    )
    def _compute_easy_shipping_parts(self):
        for order in self:
            shipping = order.partner_shipping_id
            province = shipping.province_id
            if not province and shipping.country_id.code == "TH":
                for name in (shipping.state_id.name, shipping.city):
                    if name:
                        province = self.env["province"].search([("name", "=", name)], limit=1)
                    if province:
                        break
            order.easy_shipping_street = shipping.street or False
            order.easy_shipping_street2 = shipping.street2 or False
            order.easy_shipping_province_id = province
            order.easy_shipping_amphur_id = shipping.amphur_id
            order.easy_shipping_tambon_id = shipping.tambon_id
            order.easy_shipping_postcode_id = shipping.thai_postcode_id

    def _inverse_easy_shipping_parts(self):
        """Edited address components belong to this order only."""
        return

    @api.onchange("easy_shipping_province_id")
    def _onchange_easy_shipping_province(self):
        if self.easy_shipping_amphur_id.province_id != self.easy_shipping_province_id:
            self.easy_shipping_amphur_id = False
            self.easy_shipping_tambon_id = False
            self.easy_shipping_postcode_id = False

    @api.onchange("easy_shipping_amphur_id")
    def _onchange_easy_shipping_amphur(self):
        if self.easy_shipping_amphur_id:
            self.easy_shipping_province_id = self.easy_shipping_amphur_id.province_id
        if self.easy_shipping_tambon_id.amphur_id != self.easy_shipping_amphur_id:
            self.easy_shipping_tambon_id = False
            self.easy_shipping_postcode_id = False

    @api.onchange("easy_shipping_tambon_id")
    def _onchange_easy_shipping_tambon(self):
        if self.easy_shipping_tambon_id:
            self.easy_shipping_amphur_id = self.easy_shipping_tambon_id.amphur_id
            self.easy_shipping_province_id = self.easy_shipping_tambon_id.province_id
            self.easy_shipping_postcode_id = self.easy_shipping_tambon_id.zip_ids[:1]

    @api.onchange("easy_shipping_postcode_id")
    def _onchange_easy_shipping_postcode(self):
        if self.easy_shipping_postcode_id:
            self.easy_shipping_tambon_id = self.easy_shipping_postcode_id.tambon_id
            self.easy_shipping_amphur_id = self.easy_shipping_postcode_id.amphur_id
            self.easy_shipping_province_id = self.easy_shipping_postcode_id.province_id

    def _compute_easy_flow_sequence(self):
        invoice_first = self.env["ir.config_parameter"].sudo().get_str(
            "thai_sales_stock_easy.sale_flow_sequence", "invoice_first"
        ) == "invoice_first"
        for order in self:
            order.easy_invoice_before_delivery = invoice_first

    def action_easy_open_customer(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("กรุณาเลือกลูกค้าก่อน"))
        return {
            "type": "ir.actions.act_window",
            "name": _("ข้อมูลลูกค้า"),
            "res_model": "res.partner",
            "res_id": self.partner_id.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.depends(
        "create_date",
        "date_order",
        "state",
        "picking_ids.state",
        "picking_ids.date_done",
        "invoice_ids.state",
        "invoice_ids.create_date",
        "invoice_ids.payment_state",
    )
    def _compute_easy_timeline_dates(self):
        for order in self:
            order.easy_quotation_datetime = order.create_date
            order.easy_confirmation_datetime = (
                order.date_order if order.state in ("sale", "done") else False
            )

            completed_pickings = order.picking_ids.filtered(
                lambda picking: picking.picking_type_id.code == "outgoing"
                and picking.state == "done"
                and picking.date_done
            )
            order.easy_delivery_datetime = max(
                completed_pickings.mapped("date_done"), default=False
            )

            invoices = order.invoice_ids.filtered(
                lambda invoice: invoice.move_type == "out_invoice"
                and invoice.state != "cancel"
            )
            order.easy_invoice_datetime = min(
                invoices.mapped("create_date"), default=False
            )

            payments = self.env["account.payment"]
            for invoice in invoices:
                payments |= invoice._get_reconciled_payments()
            order.easy_payment_datetime = max(
                payments.mapped("create_date"), default=False
            )

    def action_easy_print_sale_document(self):
        self.ensure_one()
        return self.env.ref("thai_sales_stock_easy.action_report_saleorder_clean").report_action(self)

    def action_easy_print_delivery(self):
        self.ensure_one()
        picking = self.picking_ids.filtered(
            lambda record: record.picking_type_id.code == "outgoing" and record.state != "cancel"
        )[:1]
        if not picking:
            raise UserError(_("ยังไม่มีเอกสารจัดส่งสำหรับรายการนี้"))
        return self.env.ref("stock.action_report_delivery").report_action(picking)

    def action_easy_confirm_stock_delivery(self):
        """Reserve and validate every pending customer delivery from the sale screen."""
        self.ensure_one()
        if self.state not in ("sale", "done"):
            raise UserError(_("กรุณายืนยันการขายก่อนตัดสต็อก"))
        if self.easy_invoice_before_delivery and not self.invoice_ids.filtered(
            lambda invoice: invoice.move_type == "out_invoice" and invoice.state != "cancel"
        ):
            raise UserError(_("Workflow นี้กำหนดให้ออกใบแจ้งหนี้ก่อนตัดสต็อก"))

        pickings = self.picking_ids.filtered(
            lambda picking: picking.picking_type_id.code == "outgoing"
            and picking.state not in ("done", "cancel")
        )
        if not pickings:
            completed = self.picking_ids.filtered(
                lambda picking: picking.picking_type_id.code == "outgoing"
                and picking.state == "done"
            )
            if completed:
                raise UserError(_("รายการนี้ตัดสต็อกเรียบร้อยแล้ว"))
            raise UserError(_("ไม่พบรายการจัดส่งสำหรับตัดสต็อก"))

        for picking in pickings:
            picking.action_assign()
            pending_moves = picking.move_ids.filtered(
                lambda stock_move: stock_move.state not in ("done", "cancel")
            )
            shortages = []
            for move in pending_moves:
                if float_compare(
                    move.quantity,
                    move.product_uom_qty,
                    precision_rounding=move.product_uom.rounding,
                ) < 0:
                    shortages.append(
                        _("• %(product)s: ต้องใช้ %(required).2f %(uom)s, จองได้ %(available).2f %(uom)s")
                        % {
                            "product": move.product_id.display_name,
                            "required": move.product_uom_qty,
                            "available": move.quantity,
                            "uom": move.product_uom.name,
                        }
                    )

            if shortages:
                raise UserError(
                    _("สต็อกไม่เพียงพอ ไม่สามารถยืนยันตัดสต็อกได้\n\n%s")
                    % "\n".join(shortages)
                )

            for move in pending_moves:
                move.quantity = move.product_uom_qty
            # The simplified flow must finish the transfer in one click.  The
            # installed ``stock_sms`` module otherwise returns its confirmation
            # wizard here; ignoring that returned action leaves the picking in
            # ``assigned`` and makes the button appear to do nothing.
            picking.with_context(
                skip_backorder=True,
                skip_sms=True,
                skip_expired=True,
            ).button_validate()
            if picking.state != "done":
                raise UserError(
                    _("ไม่สามารถยืนยันตัดสต็อก %(picking)s ได้ กรุณาตรวจสอบรายการจัดส่ง")
                    % {"picking": picking.display_name}
                )

        # Reload the active sale-order page so the delivery status and available
        # workflow buttons are read again from the server without navigating away.
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_easy_register_payment(self):
        """Open the native payment dialog for the oldest unpaid customer invoice."""
        self.ensure_one()
        invoices = self.invoice_ids.filtered(
            lambda invoice: invoice.move_type == "out_invoice"
            and invoice.state == "posted"
            and invoice.amount_residual > 0
        ).sorted(key=lambda invoice: (invoice.invoice_date or invoice.date, invoice.id))
        if not invoices:
            raise UserError(_("ไม่มีใบแจ้งหนี้ที่ยืนยันแล้วและค้างชำระสำหรับรายการนี้"))
        return invoices[0].action_register_payment()

    def action_easy_print_invoice(self):
        self.ensure_one()
        invoices = self.invoice_ids.filtered(
            lambda move: move.move_type == "out_invoice" and move.state != "cancel"
        )
        if not invoices:
            raise UserError(_("ยังไม่มีใบแจ้งหนี้สำหรับรายการนี้"))
        return self.env.ref("account.account_invoices").report_action(invoices)

    def action_easy_create_and_post_invoice(self):
        """Create and post the customer invoice without leaving the sale order."""
        self.ensure_one()
        if self.state not in ("sale", "done"):
            raise UserError(_("กรุณายืนยันการขายก่อนสร้างใบแจ้งหนี้"))
        if not self.easy_invoice_before_delivery and not self.picking_ids.filtered(
            lambda picking: picking.picking_type_id.code == "outgoing"
            and picking.state == "done"
        ):
            raise UserError(_("Workflow นี้กำหนดให้ตัดสต็อก/จัดส่งก่อนออกใบแจ้งหนี้"))

        invoices = self.invoice_ids.filtered(
            lambda invoice: invoice.move_type == "out_invoice"
            and invoice.state != "cancel"
        )
        if not invoices:
            invoices = self._create_invoices()

        draft_invoices = invoices.filtered(lambda invoice: invoice.state == "draft")
        if draft_invoices:
            draft_invoices.action_post()

        self.message_post(
            body=_("สร้างและยืนยันใบแจ้งหนี้ %s เรียบร้อยแล้ว")
            % ", ".join(invoices.mapped("name"))
        )
        return {"type": "ir.actions.client", "tag": "reload"}


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    easy_stock_available = fields.Float(
        string="พร้อมใช้",
        compute="_compute_easy_stock_status",
        digits="Product Unit of Measure",
    )
    easy_stock_label = fields.Char(
        string="สถานะสต็อก",
        compute="_compute_easy_stock_status",
    )
    easy_stock_level = fields.Selection(
        [("enough", "เพียงพอ"), ("short", "ไม่เพียงพอ"), ("untracked", "ไม่ติดตามสต็อก")],
        compute="_compute_easy_stock_status",
    )
    easy_stock_tracked = fields.Boolean(compute="_compute_easy_stock_status")

    @api.depends("product_id", "product_uom_qty", "product_uom_id", "display_type", "company_id")
    def _compute_easy_stock_status(self):
        for line in self:
            product = line.product_id
            tracked = bool(product and product.is_storable and not line.display_type)
            line.easy_stock_tracked = tracked
            if not tracked:
                line.easy_stock_available = 0
                line.easy_stock_level = "untracked"
                line.easy_stock_label = "ไม่ติดตามสต็อก" if product and not line.display_type else ""
                continue
            available = product.with_company(line.company_id).free_qty
            uom = line.product_uom_id or product.uom_id
            available = product.uom_id._compute_quantity(available, uom)
            line.easy_stock_available = available
            enough = float_compare(
                available, line.product_uom_qty,
                precision_digits=2,
            ) >= 0
            line.easy_stock_level = "enough" if enough else "short"
            line.easy_stock_label = f"{available:g}"

    def action_easy_view_stock_locations(self):
        self.ensure_one()
        if not self.product_id or not self.product_id.is_storable:
            raise UserError(_("รายการนี้ไม่มีสต็อกให้ตรวจสอบ"))
        return {
            "type": "ir.actions.act_window",
            "name": _("สต็อกตามคลัง: %s", self.product_id.display_name),
            "res_model": "stock.quant",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [
                ("product_id", "=", self.product_id.id),
                ("location_id.usage", "=", "internal"),
                ("location_id.company_id", "in", [False, self.company_id.id]),
                ("quantity", ">", 0),
            ],
            "context": {"group_by": "location_id", "search_default_internal_loc": 1},
            "target": "current",
        }

    product_image = fields.Binary(
        string="รูปสินค้า",
        related="product_id.image_128",
        readonly=True,
    )


class ThaiSaleFlow(models.AbstractModel):
    _name = "thai.sales.stock.flow"
    _description = "หน้าดำเนินงานขายแบบง่าย"

    def _get_order(self, order_id):
        order = self.env["sale.order"].browse(int(order_id)).exists()
        if not order:
            raise UserError(_("ไม่พบรายการขาย"))
        return order

    def _invoice(self, order):
        return order.invoice_ids.filtered(lambda move: move.move_type == "out_invoice" and move.state != "cancel")[:1]

    @api.model
    def get_order_flow(self, order_id):
        order = self._get_order(order_id)
        picking = order.picking_ids.filtered(lambda p: p.picking_type_id.code == "outgoing" and p.state != "cancel")[:1]
        invoice = self._invoice(order)
        delivered = bool(picking and picking.state == "done")
        invoiced = bool(invoice and invoice.state == "posted")
        paid = bool(invoiced and invoice.payment_state in ("paid", "in_payment"))
        partner = order.partner_id
        shipping = order.partner_shipping_id
        return {
            "id": order.id, "name": order.name, "state": order.state,
            "state_label": dict(order._fields["state"].selection).get(order.state, order.state),
            "date": fields.Datetime.context_timestamp(self, order.date_order).strftime("%d/%m/%Y"),
            "quotation": order.origin or order.client_order_ref or "-",
            "customer": {"name": partner.display_name, "phone": partner.phone or partner.mobile or "-",
                         "email": partner.email or "-", "vat": partner.vat or "-"},
            "shipping": {"name": shipping.display_name, "phone": shipping.phone or shipping.mobile or "-",
                         "address": (order.easy_shipping_address or "").replace("\n", ", ") or "-"},
            "lines": [{"id": line.id, "product_id": line.product_id.id,
                       "image": f"/web/image/product.product/{line.product_id.id}/image_128",
                       "code": line.product_id.default_code or "-", "name": line.name,
                       "qty": line.product_uom_qty, "uom": line.product_uom_id.name,
                       "price": line.price_unit, "discount": line.discount,
                       "subtotal": line.price_subtotal, "stock": line.product_id.free_qty}
                      for line in order.order_line.filtered(lambda line: not line.display_type)],
            "untaxed": order.amount_untaxed, "tax": order.amount_tax, "total": order.amount_total,
            "currency": order.currency_id.symbol or order.currency_id.name, "note": order.note or "",
            "confirmed": order.state in ("sale", "done"), "delivered": delivered,
            "invoiced": invoiced, "paid": paid, "invoice_id": invoice.id if invoice else 0,
            "invoice_name": invoice.name if invoice else "", "residual": invoice.amount_residual if invoice else 0,
            "due_date": fields.Date.to_string(invoice.invoice_date_due) if invoice and invoice.invoice_date_due else "",
            "can_cancel": order.state not in ("cancel", "done"),
        }

    @api.model
    def confirm_and_deliver(self, order_id):
        order = self._get_order(order_id)
        if order.state in ("draft", "sent"):
            order.action_confirm()
        for picking in order.picking_ids.filtered(lambda p: p.picking_type_id.code == "outgoing" and p.state not in ("done", "cancel")):
            picking.action_assign()
            for move in picking.move_ids.filtered(lambda m: m.state not in ("done", "cancel")):
                move.quantity = move.product_uom_qty
            picking.with_context(skip_backorder=True).button_validate()
        return self.get_order_flow(order.id)

    @api.model
    def create_invoice(self, order_id, invoice_date=None, due_date=None):
        order = self._get_order(order_id)
        if order.state not in ("sale", "done"):
            self.confirm_and_deliver(order.id)
        invoice = self._invoice(order)
        if not invoice:
            invoice = order._create_invoices()
        invoice.write({"invoice_date": invoice_date or fields.Date.context_today(self)})
        if due_date:
            invoice.invoice_date_due = due_date
        if invoice.state == "draft":
            invoice.action_post()
        return self.get_order_flow(order.id)

    @api.model
    def get_payment_options(self):
        journals = self.env["account.journal"].search([
            ("company_id", "=", self.env.company.id), ("type", "in", ("cash", "bank"))
        ])
        return [{"id": journal.id, "name": journal.name, "type": journal.type} for journal in journals]

    @api.model
    def register_payment(self, order_id, journal_id, amount, payment_date=None, memo=None):
        order = self._get_order(order_id)
        invoice = self._invoice(order)
        if not invoice or invoice.state != "posted":
            self.create_invoice(order.id)
            invoice = self._invoice(order)
        if invoice.payment_state in ("paid", "in_payment"):
            return self.get_order_flow(order.id)
        wizard = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create({"journal_id": int(journal_id), "amount": float(amount),
                  "payment_date": payment_date or fields.Date.context_today(self),
                  "communication": memo or invoice.name})
        wizard.action_create_payments()
        return self.get_order_flow(order.id)

    @api.model
    def cancel_order(self, order_id):
        order = self._get_order(order_id)
        if order.invoice_ids.filtered(lambda move: move.state == "posted"):
            raise UserError(_("รายการนี้มีเอกสารบัญชีที่ยืนยันแล้ว กรุณาทำใบลดหนี้ก่อนยกเลิก"))
        for picking in order.picking_ids.filtered(lambda p: p.state == "done" and p.picking_type_id.code == "outgoing"):
            return_wizard = self.env["stock.return.picking"].with_context(active_id=picking.id, active_model="stock.picking").create({"picking_id": picking.id})
            return_wizard.product_return_moves.quantity = return_wizard.product_return_moves.move_id.quantity
            result = return_wizard.action_create_returns()
            returned = self.env["stock.picking"].browse(result.get("res_id"))
            returned.action_assign()
            for move in returned.move_ids:
                move.quantity = move.product_uom_qty
            returned.with_context(skip_backorder=True).button_validate()
        order.action_cancel()
        return self.get_order_flow(order.id)
