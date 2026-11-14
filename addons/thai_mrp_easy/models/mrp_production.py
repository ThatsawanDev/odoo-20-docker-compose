from odoo import api, fields, models

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    @api.model
    def get_easy_list_summary(self):
        """Small, company-scoped counters for the manufacturing order list."""
        domain = [('company_id', '=', self.env.company.id),
                  ('picking_type_id.active', '=', True)]
        active = domain + [('state', 'in', ('confirmed', 'progress', 'to_close'))]
        today = fields.Date.context_today(self)
        return {
            'draft': self.search_count(domain + [('state', '=', 'draft')]),
            'confirmed': self.search_count(domain + [('state', '=', 'confirmed')]),
            'progress': self.search_count(domain + [('state', '=', 'progress')]),
            'material_waiting': self.search_count(active + [('reservation_state', 'in', ('confirmed', 'waiting'))]),
            'done_today': self.search_count(domain + [('state', '=', 'done'), ('date_finished', '>=', today)]),
        }

    easy_material_readiness = fields.Float(
        string='ความพร้อมของวัตถุดิบ (%)',
        compute='_compute_easy_material_readiness'
    )
    easy_is_ready = fields.Boolean(
        string='วัตถุดิบพร้อมผลิต',
        compute='_compute_easy_material_readiness'
    )
    easy_readiness_percent = fields.Float(
        string='ความพร้อม (%)',
        compute='_compute_easy_material_readiness'
    )
    easy_stat_enough = fields.Integer(
        string='วัตถุดิบที่เพียงพอ',
        compute='_compute_easy_material_readiness'
    )
    easy_stat_missing = fields.Integer(
        string='วัตถุดิบที่ขาด',
        compute='_compute_easy_material_readiness'
    )
    easy_notes = fields.Text(string='หมายเหตุ')

    @api.depends('move_raw_ids.product_uom_qty', 'move_raw_ids.product_id', 'move_raw_ids.easy_is_enough')
    def _compute_easy_material_readiness(self):
        for mo in self:
            total = len(mo.move_raw_ids)
            if not total:
                mo.easy_is_ready = True
                mo.easy_readiness_percent = 100.0
                mo.easy_material_readiness = 100.0
                mo.easy_stat_enough = 0
                mo.easy_stat_missing = 0
                continue
            
            ready_moves = mo.move_raw_ids.filtered(lambda m: m.easy_is_enough)
            enough_count = len(ready_moves)
            missing_count = total - enough_count
            
            mo.easy_stat_enough = enough_count
            mo.easy_stat_missing = missing_count
            mo.easy_readiness_percent = (enough_count / total) * 100.0
            mo.easy_material_readiness = mo.easy_readiness_percent
            mo.easy_is_ready = (enough_count == total)

    def action_easy_create_po_for_missing(self):
        self.ensure_one()
        missing_moves = self.move_raw_ids.filtered(lambda m: not m.easy_is_enough)
        if not missing_moves:
            return
        
        # simplified PO creation (in a real scenario we'd group by vendor)
        po_vals = {
            'partner_id': self.env.company.partner_id.id, # Placeholder, should be a real vendor
            'order_line': []
        }
        for move in missing_moves:
            qty_needed = move.product_uom_qty - move.product_id.qty_available
            po_vals['order_line'].append((0, 0, {
                'product_id': move.product_id.id,
                'product_qty': qty_needed,
                'uom_id': move.product_id.uom_id.id,
                'name': move.product_id.name,
                'price_unit': move.product_id.standard_price,
            }))
        
        po = self.env['purchase.order'].create(po_vals)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }

class StockMove(models.Model):
    _inherit = 'stock.move'

    easy_is_enough = fields.Boolean(
        string='เพียงพอ',
        compute='_compute_easy_is_enough'
    )
    easy_qty_available = fields.Float(
        string='คงเหลือ',
        related='product_id.qty_available'
    )

    @api.depends('product_id.qty_available', 'product_uom_qty')
    def _compute_easy_is_enough(self):
        for move in self:
            move.easy_is_enough = move.product_id.qty_available >= move.product_uom_qty
