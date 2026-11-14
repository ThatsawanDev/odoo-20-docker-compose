from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ThaiSalesStockDashboard(models.AbstractModel):
    _name = "thai.sales.stock.dashboard"
    _description = "ภาพรวมระบบขายและสต็อก"

    @api.model
    def get_dashboard_data(self):
        company = self.env.company
        today = fields.Date.context_today(self)
        sale_domain = [("company_id", "=", company.id)]
        picking_domain = [("company_id", "=", company.id), ("state", "not in", ("done", "cancel"))]

        quotations = self.env["sale.order"].search_count(sale_domain + [("state", "in", ("draft", "sent"))])
        outgoing = self.env["stock.picking"].search_count(
            picking_domain + [("picking_type_id.code", "=", "outgoing")]
        )
        incoming = self.env["stock.picking"].search_count(
            picking_domain + [("picking_type_id.code", "=", "incoming")]
        )
        incoming_today = self.env["stock.picking"].search_count(
            picking_domain
            + [("picking_type_id.code", "=", "incoming"), ("scheduled_date", ">=", today),
               ("scheduled_date", "<", fields.Date.add(today, days=1))]
        )
        invoices = self.env["account.move"].search(
            [("company_id", "=", company.id), ("move_type", "=", "out_invoice"),
             ("state", "=", "posted"), ("payment_state", "in", ("not_paid", "partial"))]
        )
        receivable = sum(invoices.mapped("amount_residual"))
        draft_invoices = self.env["account.move"].search_count(
            [("company_id", "=", company.id), ("move_type", "=", "out_invoice"), ("state", "=", "draft")]
        )
        purchase_orders = self.env["purchase.order"].search_count(
            [("company_id", "=", company.id), ("state", "in", ("draft", "sent", "to approve"))]
        )
        vendor_bills = self.env["account.move"].search_count(
            [("company_id", "=", company.id), ("move_type", "=", "in_invoice"),
             ("state", "=", "draft")]
        )
        vendor_payments = self.env["account.move"].search_count(
            [("company_id", "=", company.id), ("move_type", "=", "in_invoice"),
             ("state", "=", "posted"), ("payment_state", "in", ("not_paid", "partial"))]
        )
        low_stock = self.env["product.product"].search_count(
            [("is_storable", "=", True), ("active", "=", True), ("free_qty", "<=", 5)]
        )
        orders_30 = self.env["sale.order"].search(
            sale_domain + [("state", "in", ("sale", "done")), ("date_order", ">=", today - timedelta(days=29))]
        )
        daily_totals = {today - timedelta(days=offset): 0.0 for offset in range(29, -1, -1)}
        for order in orders_30:
            order_day = fields.Datetime.context_timestamp(self, order.date_order).date()
            if order_day in daily_totals:
                daily_totals[order_day] += order.amount_total
        max_daily = max(daily_totals.values(), default=0.0) or 1.0
        recent_orders = self.env["sale.order"].search(
            sale_domain + [("state", "!=", "cancel")], order="date_order desc", limit=5
        )
        low_products = self.env["product.product"].search(
            [("is_storable", "=", True), ("active", "=", True), ("free_qty", "<=", 5)]
        ).sorted(key=lambda product: (product.free_qty, product.name or ""))[:5]
        invoice_first = self.env["ir.config_parameter"].sudo().get_str(
            "thai_sales_stock_easy.sale_flow_sequence", "invoice_first"
        ) == "invoice_first"
        recent_order_values = []
        for order in recent_orders:
            invoices = order.invoice_ids.filtered(
                lambda move: move.move_type == "out_invoice" and move.state != "cancel"
            )
            delivered = bool(order.picking_ids.filtered(
                lambda picking: picking.picking_type_id.code == "outgoing"
                and picking.state == "done"
            ))
            paid = bool(invoices) and all(
                invoice.payment_state in ("paid", "in_payment") for invoice in invoices
            )

            if order.state in ("draft", "sent"):
                stage, stage_label = "confirm", "ยืนยันการขาย"
            elif paid:
                stage, stage_label = "paid", "รับเงินแล้ว"
            elif invoice_first and not invoices:
                stage, stage_label = "invoice", "เอกสารการเงิน"
            elif not invoice_first and not delivered:
                stage, stage_label = "delivery", "ตัดสต็อก/จัดส่ง"
            elif not invoice_first and not invoices:
                stage, stage_label = "invoice", "เอกสารการเงิน"
            elif invoice_first and not delivered:
                stage, stage_label = "delivery", "ตัดสต็อก/จัดส่ง"
            else:
                stage, stage_label = "payment", "รอรับเงิน"

            recent_order_values.append({
                "id": order.id,
                "name": order.name,
                "customer": order.partner_id.display_name,
                "date": fields.Datetime.context_timestamp(self, order.date_order).strftime("%d/%m/%Y"),
                "amount": order.amount_total,
                "state": stage,
                "state_label": stage_label,
            })
        today_sales = sum(
            order.amount_total for order in orders_30
            if fields.Datetime.context_timestamp(self, order.date_order).date() == today
        )
        invoice_total = self.env["account.move"].search_count(
            [("company_id", "=", company.id), ("move_type", "=", "out_invoice"), ("state", "=", "posted")]
        )
        return {
            "date_th": self._thai_date(today),
            "quotations": quotations,
            "outgoing": outgoing,
            "receivable": receivable,
            "receivable_count": len(invoices),
            "draft_invoices": draft_invoices,
            "purchase_orders": purchase_orders,
            "vendor_bills": vendor_bills,
            "vendor_payments": vendor_payments,
            "incoming": incoming,
            "incoming_today": incoming_today,
            "low_stock": low_stock,
            "currency": company.currency_id.symbol or company.currency_id.name,
            "company_name": company.name,
            "user_name": self.env.user.name,
            "today_sales": today_sales,
            "invoice_total": invoice_total,
            "recent_orders": recent_order_values,
            "low_products": [{
                "id": product.id, "name": product.display_name, "stock": product.free_qty,
                "uom": product.uom_id.name,
                "image": f"/web/image/product.product/{product.id}/image_128" if product.image_128 else False,
            } for product in low_products],
            "sales_chart": [{
                "label": day.strftime("%d"), "amount": amount,
                "height": round((amount / max_daily) * 100, 1),
            } for day, amount in daily_totals.items()],
            "sales_30_total": sum(daily_totals.values()),
        }

    @api.model
    def get_quotation_form_data(self):
        customers = self.env["res.partner"].search(
            [("customer_rank", ">", 0), ("active", "=", True)], order="name", limit=100
        )
        products = self.env["product.product"].search(
            [("sale_ok", "=", True), ("active", "=", True)], order="name", limit=200
        )
        curry_product = self.env.ref("thai_sales_stock_easy.product_sour_curry_pouch", raise_if_not_found=False)
        pouch_uom = self.env.ref("thai_sales_stock_easy.uom_pouch", raise_if_not_found=False)
        case_uom = self.env.ref("thai_sales_stock_easy.uom_case_6", raise_if_not_found=False)
        product_options = []
        for product in products:
            units = (pouch_uom | case_uom) if product == curry_product and pouch_uom and case_uom else product.uom_id
            for unit in units:
                product_options.append({
                    "key": f"{product.id}-{unit.id}",
                    "id": product.id,
                    "name": product.display_name,
                    "price": product.uom_id._compute_price(product.lst_price, unit),
                    "uom_id": unit.id,
                    "uom": unit.name,
                    "category_id": product.categ_id.id,
                    "category": product.categ_id.name,
                    "stock": product.uom_id._compute_quantity(product.free_qty, unit),
                    "image": "/thai_sales_stock_easy/static/src/img/sour_curry_case.png"
                    if unit == case_uom else f"/web/image/product.product/{product.id}/image_256",
                })
        return {
            "customers": [
                {
                    "id": partner.id,
                    "name": partner.display_name,
                    "phone": partner.phone or partner.mobile or "",
                    "vat": partner.vat or "",
                    "address": ", ".join(filter(None, [partner.street, partner.street2, partner.city,
                                                         partner.state_id.name, partner.zip,
                                                         partner.country_id.name])),
                }
                for partner in customers
            ],
            "products": product_options,
            "currency": self.env.company.currency_id.symbol or self.env.company.currency_id.name,
        }

    @api.model
    def get_quick_quotation_totals(self, partner_id, lines):
        company = self.env.company
        currency = company.currency_id
        partner = self.env["res.partner"].browse(int(partner_id)).exists() if partner_id else False
        fiscal_position = self.env["account.fiscal.position"]._get_fiscal_position(partner) if partner else False
        amount_untaxed = amount_tax = amount_total = 0.0
        tax_names = set()
        for line in lines:
            product = self.env["product.product"].browse(int(line.get("product_id", 0))).exists()
            if not product or float(line.get("quantity", 0)) <= 0:
                continue
            taxes = product.taxes_id.filtered(lambda tax: tax.company_id == company)
            if fiscal_position:
                taxes = fiscal_position.map_tax(taxes)
            result = taxes.compute_all(
                float(line.get("price", 0)), currency=currency,
                quantity=float(line.get("quantity", 0)), product=product, partner=partner,
            )
            amount_untaxed += result["total_excluded"]
            amount_total += result["total_included"]
            amount_tax += result["total_included"] - result["total_excluded"]
            tax_names.update(tax["name"] for tax in result.get("taxes", []) if tax.get("name"))
        return {
            "untaxed": currency.round(amount_untaxed),
            "tax": currency.round(amount_tax),
            "total": currency.round(amount_total),
            "tax_label": ", ".join(sorted(tax_names)) if tax_names else _("ไม่มี VAT"),
        }

    @api.model
    def create_quick_quotation(self, partner_id, lines, note=False, customer_data=None, validity_date=None):
        customer_data = customer_data or {}
        if not partner_id and customer_data.get("name"):
            partner = self.env["res.partner"].create({
                "name": customer_data["name"].strip(),
                "phone": (customer_data.get("phone") or "").strip() or False,
                "street": (customer_data.get("street") or "").strip() or False,
                "city": (customer_data.get("city") or "").strip() or False,
                "zip": (customer_data.get("zip") or "").strip() or False,
                "customer_rank": 1,
            })
            partner_id = partner.id
        if not partner_id:
            raise UserError(_("กรุณาเลือกลูกค้า หรือกรอกชื่อลูกค้าใหม่"))
        valid_lines = [line for line in lines if line.get("product_id") and line.get("uom_id")
                       and float(line.get("quantity", 0)) > 0]
        if not valid_lines:
            raise UserError(_("กรุณาเพิ่มสินค้าอย่างน้อย 1 รายการ"))
        order = self.env["sale.order"].create({
            "partner_id": int(partner_id),
            "note": note or False,
            "validity_date": validity_date or False,
            "order_line": [fields.Command.create({
                "product_id": int(line["product_id"]),
                "product_uom_id": int(line["uom_id"]),
                "product_uom_qty": float(line["quantity"]),
                "price_unit": float(line.get("price", 0)),
            }) for line in valid_lines],
        })
        return {"id": order.id, "name": order.name, "amount_total": order.amount_total}

    @api.model
    def _thai_date(self, value):
        day_names = ["วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์", "วันเสาร์", "วันอาทิตย์"]
        month_names = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
                       "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
        return f"{day_names[value.weekday()]}ที่ {value.day} {month_names[value.month]} {value.year + 543}"
