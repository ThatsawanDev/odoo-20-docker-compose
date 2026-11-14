from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models


class ThaiSalesStockHubDashboard(models.AbstractModel):
    _name = "thai.sales.stock.hub.dashboard"
    _description = "ภาพรวมการดำเนินงานทุกช่องทาง"

    @api.model
    def get_overview(self):
        companies = self.env.companies
        company_ids = companies.ids
        today = fields.Date.context_today(self)
        user_tz = pytz.timezone(self.env.user.tz or "UTC")
        start = user_tz.localize(datetime.combine(today, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        end = user_tz.localize(datetime.combine(today + timedelta(days=1), time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        sale = self.env["sale.order"]
        picking = self.env["stock.picking"]
        purchase = self.env["purchase.order"]
        base_sale = [("company_id", "in", company_ids), ("state", "!=", "cancel")]
        today_sale = base_sale + [("date_order", ">=", start), ("date_order", "<", end)]
        today_orders = sale.search(today_sale)
        confirmed_today = today_orders.filtered(lambda order: order.state in ("sale", "done"))
        channel_records = self.env["thai.sales.stock.channel"].with_context(active_test=False).search([])
        channel_by_code = {channel.code: channel for channel in channel_records}
        channel_labels = {key: channel_by_code[key].name if key in channel_by_code else label
                          for key, label in sale._fields["hub_channel"].selection}
        channel_amounts = {key: 0.0 for key in channel_labels}
        channel_counts = {key: 0 for key in channel_labels}
        for order in sale.search(base_sale):
            channel_counts[order.hub_channel or "direct"] += 1
        for order in confirmed_today:
            channel_amounts[order.hub_channel or "direct"] += order.amount_total
        total_sales = sum(channel_amounts.values())
        channels = [
            {"key": key, "name": channel_labels[key], "amount": amount, "count": channel_counts[key],
             "icon": f"/web/image/thai.sales.stock.channel/{channel_by_code[key].id}/icon_128" if key in channel_by_code else "",
             "percent": round(amount / total_sales * 100, 1) if total_sales else 0}
            for key, amount in channel_amounts.items()
        ]
        channels.sort(key=lambda item: item["amount"], reverse=True)
        open_outgoing = [("company_id", "in", company_ids),
                         ("picking_type_id.code", "=", "outgoing"),
                         ("state", "not in", ("done", "cancel"))]
        ready = picking.search_count(open_outgoing + [("state", "=", "assigned")])
        waiting = picking.search_count(open_outgoing + [("state", "!=", "assigned")])
        shipped = picking.search_count([
            ("company_id", "in", company_ids), ("picking_type_id.code", "=", "outgoing"),
            ("state", "=", "done"), ("date_done", ">=", start), ("date_done", "<", end),
        ])
        issue_count = picking.search_count(open_outgoing + [("scheduled_date", "<", start)])
        low_products = self.env["product.product"].search([
            ("is_storable", "=", True), ("active", "=", True), ("free_qty", "<=", 5),
        ], limit=5, order="name")
        low_stock = [
            {"id": product.id, "name": product.display_name,
             "qty": product.free_qty, "uom": product.uom_id.name}
            for product in low_products
        ]
        purchase_waiting = purchase.search_count([
            ("company_id", "in", company_ids), ("state", "in", ("draft", "sent", "to approve")),
        ])
        production = []
        if "mrp.production" in self.env:
            mos = self.env["mrp.production"].search([
                ("company_id", "in", company_ids), ("state", "not in", ("done", "cancel")),
            ], limit=3, order="date_start asc")
            production = [
                {"name": mo.name, "product": mo.product_id.display_name,
                 "qty": mo.product_qty, "uom": mo.product_uom_id.name, "state": mo.state}
                for mo in mos
            ]
        orders_total = sale.search_count(base_sale)
        month_start = user_tz.localize(datetime.combine(today.replace(day=1), time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        month_revenue = sum(sale.search(base_sale + [("state", "in", ("sale", "done")),
            ("date_order", ">=", month_start), ("date_order", "<", end)]).mapped("amount_total"))
        statuses = [
            {"name": "รอยืนยัน", "count": sale.search_count(base_sale + [("state", "in", ("draft", "sent"))]), "color": "#8b5cf6"},
            {"name": "กำลังดำเนินการ", "count": sale.search_count(base_sale + [("state", "=", "sale")]), "color": "#1681ef"},
            {"name": "เสร็จสิ้น", "count": sale.search_count(base_sale + [("state", "=", "done")]), "color": "#21b45b"},
        ]
        return {
            "date": today.strftime("%d/%m/%Y"),
            "companies": ", ".join(companies.mapped("name")),
            "company_count": len(companies),
            "currency": self.env.company.currency_id.symbol or "฿",
            "new_orders": len(today_orders),
            "waiting_pack": waiting,
            "ready_ship": ready,
            "shipped_today": shipped,
            "issues": issue_count,
            "sales_today": total_sales,
            "orders_total": orders_total,
            "month_revenue": month_revenue,
            "shipped_total": picking.search_count([("company_id", "in", company_ids),
                ("picking_type_id.code", "=", "outgoing"), ("state", "=", "done")]),
            "statuses": statuses,
            "channels": channels,
            "low_stock": low_stock,
            "purchase_waiting": purchase_waiting,
            "production": production,
            "mrp_available": "mrp.production" in self.env,
            "can_configure": self.env.user.has_group("base.group_system"),
            "marketplace_enabled": [
                {"name": "Shopee", "shop_count": self.env["shopee.shop"].sudo().search_count([("company_id", "in", company_ids)])},
                {"name": "Lazada", "shop_count": self.env["lazada.shop"].sudo().search_count([("company_id", "in", company_ids)])},
                {"name": "TikTok Shop", "shop_count": self.env["tiktok.shop"].sudo().search_count([("company_id", "in", company_ids)])},
            ],
        }
