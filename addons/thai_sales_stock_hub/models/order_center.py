from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models


class ThaiSalesStockOrderCenter(models.AbstractModel):
    _name = "thai.sales.stock.order.center"
    _description = "ศูนย์ออเดอร์ทุกช่องทาง"

    def _date_domain(self, date_from, date_to):
        tz = pytz.timezone(self.env.user.tz or "UTC")
        domain = []
        if date_from:
            day = fields.Date.to_date(date_from)
            start = tz.localize(datetime.combine(day, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
            domain.append(("date_order", ">=", start))
        if date_to:
            day = fields.Date.to_date(date_to) + timedelta(days=1)
            end = tz.localize(datetime.combine(day, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
            domain.append(("date_order", "<", end))
        return domain

    def _status_domain(self, status):
        return {
            "pending": [("state", "in", ("draft", "sent"))],
            "to_pay": [("state", "in", ("sale", "done")), ("invoice_ids.payment_state", "in", ("not_paid", "partial"))],
            "to_pack": [("state", "in", ("sale", "done")), ("picking_ids.picking_type_id.code", "=", "outgoing"), ("picking_ids.state", "not in", ("assigned", "done", "cancel"))],
            "ready": [("picking_ids.picking_type_id.code", "=", "outgoing"), ("picking_ids.state", "=", "assigned")],
            "shipped": [("picking_ids.picking_type_id.code", "=", "outgoing"), ("picking_ids.state", "=", "done")],
            "cancel": [("state", "=", "cancel")],
        }.get(status, [])

    def _order_status(self, order):
        if order.state == "cancel":
            return "cancel", "ยกเลิก"
        if order.state in ("draft", "sent"):
            return "pending", "รอยืนยัน"
        outgoing = order.picking_ids.filtered(lambda p: p.picking_type_id.code == "outgoing")
        if outgoing and all(p.state in ("done", "cancel") for p in outgoing) and any(p.state == "done" for p in outgoing):
            return "shipped", "จัดส่งแล้ว"
        if any(p.state == "assigned" for p in outgoing):
            return "ready", "พร้อมจัดส่ง"
        if outgoing:
            return "to_pack", "รอแพ็ก"
        return "pending", "รอดำเนินการ"

    def _detail(self, order):
        if not order:
            return False
        invoices = order.invoice_ids.filtered(lambda move: move.move_type == "out_invoice" and move.state != "cancel")
        code, label = self._order_status(order)
        return {
            "id": order.id,
            "name": order.name,
            "external_ref": order.hub_external_ref or "",
            "channel": dict(order._fields["hub_channel"].selection).get(order.hub_channel, "ขายตรง"),
            "channel_icon": f"/thai_sales_stock_hub/static/src/img/channels/{order.hub_channel or 'direct'}.svg",
            "is_demo": order.hub_is_demo,
            "customer": order.partner_id.display_name,
            "customer_image": f"/web/image/res.partner/{order.partner_id.id}/avatar_128",
            "phone": order.partner_id.phone or order.partner_id.mobile or "",
            "address": order.easy_shipping_address or order.partner_shipping_id.contact_address or "",
            "status": code,
            "status_label": label,
            "payment": "ชำระแล้ว" if invoices and all(m.payment_state in ("paid", "in_payment") for m in invoices) else "ตรวจสอบการชำระเงิน",
            "lines": [{"name": line.product_id.display_name or line.name, "qty": line.product_uom_qty,
                       "image": f"/web/image/product.product/{line.product_id.id}/image_128" if line.product_id else "",
                       "uom": line.product_uom_id.name, "subtotal": line.price_subtotal}
                      for line in order.order_line.filtered(lambda line: not line.display_type)[:15]],
            "amount_untaxed": order.amount_untaxed,
            "amount_tax": order.amount_tax,
            "amount_total": order.amount_total,
            "currency": order.currency_id.symbol or order.currency_id.name,
            "picking_ids": order.picking_ids.filtered(lambda p: p.picking_type_id.code == "outgoing").ids,
        }

    @api.model
    def get_data(self, search="", channel="", status="", date_from="", date_to="", page=1, selected_id=0):
        sale = self.env["sale.order"]
        company_ids = self.env.companies.ids
        base = [("company_id", "in", company_ids)] + self._date_domain(date_from, date_to)
        if search and search.strip():
            query = search.strip()[:100]
            base += ["|", "|", "|",
                     ("name", "ilike", query), ("hub_external_ref", "ilike", query),
                     ("partner_id.name", "ilike", query), ("partner_id.phone", "ilike", query)]
        if channel:
            base.append(("hub_channel", "=", channel))
        domain = base + self._status_domain(status)
        page = max(1, int(page or 1))
        page_size = 25
        total = sale.search_count(domain)
        max_page = max(1, (total + page_size - 1) // page_size)
        page = min(page, max_page)
        orders = sale.search(domain, offset=(page - 1) * page_size, limit=page_size, order="date_order desc, id desc")
        selected = orders.filtered(lambda order: order.id == int(selected_id or 0))[:1] or orders[:1]
        rows = []
        for order in orders:
            code, label = self._order_status(order)
            invoices = order.invoice_ids.filtered(lambda move: move.move_type == "out_invoice" and move.state != "cancel")
            rows.append({
                "id": order.id, "name": order.hub_external_ref or order.name,
                "odoo_name": order.name,
                "channel": order.hub_channel or "direct",
                "channel_icon": f"/thai_sales_stock_hub/static/src/img/channels/{order.hub_channel or 'direct'}.svg",
                "channel_label": dict(sale._fields["hub_channel"].selection).get(order.hub_channel, "ขายตรง"),
                "is_demo": order.hub_is_demo,
                "customer": order.partner_id.display_name,
                "amount": order.amount_total,
                "currency": order.currency_id.symbol or order.currency_id.name,
                "payment": "paid" if invoices and all(m.payment_state in ("paid", "in_payment") for m in invoices) else "unpaid",
                "status": code, "status_label": label,
            })
        channel_keys = ["shopee", "lazada", "tiktok", "website", "store", "direct"]
        labels = dict(sale._fields["hub_channel"].selection)
        channel_counts = [{"key": key, "name": labels[key], "count": sale.search_count(base + [("hub_channel", "=", key)]),
                           "enabled": bool(getattr(self.env.company, f"hub_{key}_enabled", True))}
                          for key in channel_keys]
        status_keys = ["pending", "to_pay", "to_pack", "ready", "shipped", "cancel"]
        status_labels = {"pending": "รอดำเนินการ", "to_pay": "รอชำระเงิน", "to_pack": "รอแพ็ก",
                         "ready": "พร้อมจัดส่ง", "shipped": "จัดส่งแล้ว", "cancel": "ยกเลิก"}
        status_counts = [{"key": key, "name": status_labels[key], "count": sale.search_count(base + self._status_domain(key))}
                         for key in status_keys]
        return {
            "rows": rows, "detail": self._detail(selected), "total": total, "page": page,
            "page_size": page_size, "max_page": max_page,
            "all_count": sale.search_count(base), "channels": channel_counts, "statuses": status_counts,
            "demo_count": sale.search_count(base + [("hub_is_demo", "=", True)]),
            "companies": ", ".join(self.env.companies.mapped("name")),
            "can_configure": self.env.user.has_group("base.group_system"),
        }
