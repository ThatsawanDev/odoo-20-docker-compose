from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    easy_outbound_line_count = fields.Integer(compute="_compute_easy_outbound_summary")
    easy_outbound_total_qty = fields.Float(compute="_compute_easy_outbound_summary")

    @api.depends("move_ids.product_uom_qty", "move_ids.state")
    def _compute_easy_outbound_summary(self):
        for picking in self:
            moves = picking.move_ids.filtered(lambda move: move.state != "cancel")
            picking.easy_outbound_line_count = len(moves)
            picking.easy_outbound_total_qty = sum(moves.mapped("product_uom_qty"))
