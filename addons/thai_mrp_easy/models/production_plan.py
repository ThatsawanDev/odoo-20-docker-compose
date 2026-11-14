from datetime import datetime, time, timedelta

from odoo import api, fields, models


class ThaiMrpEasyPlan(models.AbstractModel):
    _name = "thai.mrp.easy.plan"
    _description = "Manufacturing Gantt data"

    @api.model
    def get_plan_data(self, start_date, end_date):
        start = fields.Date.to_date(start_date)
        end = fields.Date.to_date(end_date)
        if not start or not end or end < start or (end - start).days > 62:
            return []
        # One day of overlap covers dates near the user's timezone boundary.
        start_dt = datetime.combine(start - timedelta(days=1), time.min)
        end_dt = datetime.combine(end + timedelta(days=2), time.min)
        orders = self.env["mrp.production"].search([
            ("company_id", "=", self.env.company.id),
            ("state", "!=", "cancel"),
            ("date_start", "<=", fields.Datetime.to_string(end_dt)),
            "|",
            ("date_finished", "=", False),
            ("date_finished", ">=", fields.Datetime.to_string(start_dt)),
        ], order="date_start, id", limit=500)
        labels = {
            "draft": "แบบร่าง",
            "confirmed": "ยืนยันแล้ว",
            "progress": "กำลังผลิต",
            "to_close": "รอปิดงาน",
            "done": "เสร็จสิ้น",
        }
        result = []
        for order in orders:
            start_local = fields.Datetime.context_timestamp(order, order.date_start).date()
            finish_local = (
                fields.Datetime.context_timestamp(order, order.date_finished).date()
                if order.date_finished else start_local
            )
            if finish_local < start or start_local > end:
                continue
            result.append({
                "id": order.id,
                "name": order.name,
                "product": order.product_id.display_name,
                "quantity": order.product_qty,
                "uom": order.uom_id.name,
                "state": order.state,
                "state_label": labels.get(order.state, order.state),
                "start": start_local.isoformat(),
                "end": max(start_local, finish_local).isoformat(),
            })
        return result
