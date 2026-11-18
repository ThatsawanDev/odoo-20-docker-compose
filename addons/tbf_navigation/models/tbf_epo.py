from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TbfEpo(models.Model):
    _name = 'tbf.epo'
    _description = 'TBF Picking Order (E-PO)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(default='/', readonly=True, copy=False, required=True, tracking=True)
    sale_order_id = fields.Many2one('sale.order', required=True, readonly=True, copy=False, index=True)
    picking_id = fields.Many2one('stock.picking', required=True, readonly=True, copy=False, index=True)
    partner_id = fields.Many2one(related='sale_order_id.partner_id', store=True)
    parent_id = fields.Many2one('tbf.epo', readonly=True, copy=False, index=True)
    child_ids = fields.One2many('tbf.epo', 'parent_id', string='เอกสารส่งบางส่วน')
    state = fields.Selection([
        ('new', 'รอส่งงานให้ QC'),
        ('confirmed', 'QC รับทราบ'),
        ('verified', 'QC ตรวจสอบผ่าน'),
        ('ready', 'ย้ายไป Awaiting to Sell แล้ว'),
        ('shipped', 'จัดส่งแล้ว'),
    ], default='new', required=True, tracking=True)
    line_ids = fields.One2many('tbf.epo.line', 'epo_id', string='รายการสินค้า')
    scan_code = fields.Char(string='สแกน Barcode หรือรหัสสินค้า', copy=False)
    internal_picking_id = fields.Many2one('stock.picking', string='ใบย้ายสต็อก', readonly=True, copy=False)
    awaiting_location_id = fields.Many2one('stock.location', string='Awaiting to Sell', readonly=True, copy=False)
    officer_id = fields.Many2one('res.users', string='ผู้รับผิดชอบคลัง', tracking=True)

    _sql_constraints = [
        ('picking_unique', 'unique(picking_id)', 'ใบจัดส่งนี้มี E-PO อยู่แล้ว'),
        ('name_unique', 'unique(name)', 'เลข E-PO ซ้ำ'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('tbf.epo') or '/'
        return super().create(vals_list)

    def _notify_officer(self):
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        for epo in self:
            officer = epo.officer_id or self.env.ref('base.user_admin')
            epo.activity_schedule(
                activity_type_id=activity_type.id,
                user_id=officer.id,
                summary=_('E-PO ใหม่: พิมพ์และส่งให้ทีม QC'),
                note=_('กรุณาพิมพ์ %s และส่งให้ทีม QC') % epo.name,
            )

    def _require_state(self, expected):
        for epo in self:
            if epo.state != expected:
                raise UserError(_('ต้องทำขั้นตอนก่อนหน้าให้เสร็จก่อน: %s') % epo.name)

    def action_qc_confirm(self):
        self._require_state('new')
        self.write({'state': 'confirmed'})

    def action_product_verified(self):
        self._require_state('confirmed')
        for epo in self:
            if not epo.line_ids:
                raise UserError(_('E-PO ไม่มีรายการสินค้า'))
            for line in epo.line_ids:
                if line.product_id.tracking:
                    raise UserError(_('สินค้าที่ติดตาม Lot/Serial ต้องจัดการผ่านใบโอนย้ายมาตรฐานก่อน: %s') % line.product_id.display_name)
                if line.uom_id.compare(line.picked_qty, 0) < 0:
                    raise ValidationError(_('จำนวนที่หยิบต้องไม่ติดลบ'))
                if line.uom_id.compare(line.picked_qty, line.requested_qty) > 0:
                    raise ValidationError(_('จำนวนที่หยิบมากกว่าจำนวนที่สั่ง: %s') % line.product_id.display_name)
            if not any(line.picked_qty for line in epo.line_ids):
                raise UserError(_('กรุณาระบุจำนวนที่ QC ตรวจผ่านอย่างน้อยหนึ่งรายการ'))
        self.write({'state': 'verified'})

    def _awaiting_location(self):
        self.ensure_one()
        warehouse = self.picking_id.picking_type_id.warehouse_id
        if not warehouse:
            raise UserError(_('ไม่พบคลังของใบจัดส่ง'))
        location = self.env['stock.location'].search([
            ('location_id', '=', warehouse.view_location_id.id),
            ('name', '=', 'Awaiting to Sell'),
            ('usage', '=', 'internal'),
        ], limit=1)
        if not location:
            location = self.env['stock.location'].create({
                'name': 'Awaiting to Sell',
                'location_id': warehouse.view_location_id.id,
                'usage': 'internal',
                'company_id': warehouse.company_id.id,
            })
        return location

    def action_picking_completed(self):
        self._require_state('verified')
        for epo in self:
            if epo.picking_id.state in ('done', 'cancel'):
                raise UserError(_('ใบจัดส่งถูกปิดแล้ว'))
            warehouse = epo.picking_id.picking_type_id.warehouse_id
            if not warehouse.int_type_id:
                raise UserError(_('ไม่พบประเภทการโอนย้ายภายในคลัง'))
            awaiting = epo._awaiting_location()
            picked = epo.line_ids.filtered(lambda l: l.picked_qty)
            # The sale delivery may already reserve these goods. Release its
            # reservation before checking stock for the internal transfer.
            epo.picking_id.do_unreserve()
            for line in picked:
                available = self.env['stock.quant']._get_available_quantity(line.product_id, line.source_location_id)
                if line.uom_id.compare(available, line.picked_qty) < 0:
                    raise UserError(_('สต็อกไม่พอที่ %s: %s') % (line.source_location_id.display_name, line.product_id.display_name))
            transfer = self.env['stock.picking'].create({
                'picking_type_id': warehouse.int_type_id.id,
                'location_id': picked[0].source_location_id.id,
                'location_dest_id': awaiting.id,
                'origin': epo.name,
                'move_ids': [Command.create({
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.picked_qty,
                    'uom_id': line.uom_id.id,
                    'location_id': line.source_location_id.id,
                    'location_dest_id': awaiting.id,
                }) for line in picked],
            })
            transfer.action_confirm()
            for move in transfer.move_ids:
                move.quantity = move.product_uom_qty
                move.picked = True
            result = transfer.with_context(skip_backorder=True).button_validate()
            if transfer.state != 'done':
                raise UserError(_('ย้ายสต็อกไม่สำเร็จ: %s') % result)
            for line in epo.line_ids:
                line.move_id.location_id = awaiting.id
                line.move_id.quantity = line.picked_qty
                line.move_id.picked = bool(line.picked_qty)
            epo.picking_id.location_id = awaiting.id
            epo.picking_id.action_assign()
            epo.write({
                'internal_picking_id': transfer.id,
                'awaiting_location_id': awaiting.id,
                'state': 'ready',
            })

    def action_scan(self):
        self.ensure_one()
        self._require_state('ready')
        code = (self.scan_code or '').strip()
        if not code:
            raise UserError(_('กรุณาสแกน Barcode หรือใส่รหัสสินค้า'))
        lines = self.line_ids.filtered(
            lambda l: code in (l.product_id.barcode, l.product_id.default_code)
            and l.uom_id.compare(l.scanned_qty, l.picked_qty) < 0
        )
        if not lines:
            raise UserError(_('ไม่พบสินค้าที่ยังรอสแกนสำหรับรหัส %s') % code)
        line = lines[0]
        line.scanned_qty += 1
        self.scan_code = False
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def action_shipped_out(self):
        self._require_state('ready')
        for epo in self:
            for line in epo.line_ids:
                if line.uom_id.compare(line.scanned_qty, line.picked_qty) != 0:
                    raise UserError(_('สแกนสินค้าให้ครบก่อนจัดส่ง: %s') % line.product_id.display_name)
            result = epo.picking_id.with_context(
                skip_backorder=True, tbf_shipping_approved=True,
            ).button_validate()
            if epo.picking_id.state != 'done':
                raise UserError(_('ยืนยันจัดส่งไม่สำเร็จ: %s') % result)
            epo.state = 'shipped'
            epo.activity_feedback(['mail.mail_activity_data_todo'])

    def action_view_sale(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'sale.order',
                'view_mode': 'form', 'res_id': self.sale_order_id.id}

    def action_view_transfer(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.picking',
                'view_mode': 'form', 'res_id': self.internal_picking_id.id}

    def action_view_shipment(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.picking',
                'view_mode': 'form', 'res_id': self.picking_id.id}

    @api.model
    def get_epo_dashboard_counts(self, base_domain=None):
        domain = list(base_domain or [])
        groups = self._read_group(domain, groupby=['state'], aggregates=['__count'])
        counts = {'new': 0, 'confirmed': 0, 'verified': 0, 'ready': 0, 'shipped': 0}
        for state, count in groups:
            if state in counts:
                counts[state] = count
        counts['all'] = sum(counts.values())
        return counts


class TbfEpoLine(models.Model):
    _name = 'tbf.epo.line'
    _description = 'TBF E-PO Product Line'

    epo_id = fields.Many2one('tbf.epo', required=True, ondelete='cascade')
    move_id = fields.Many2one('stock.move', required=True, readonly=True)
    product_id = fields.Many2one(related='move_id.product_id', store=True)
    product_image = fields.Image(related='product_id.image_128', string='รูปสินค้า', readonly=True)
    uom_id = fields.Many2one(related='move_id.uom_id', store=True)
    requested_qty = fields.Float(related='move_id.product_uom_qty', store=True)
    source_location_id = fields.Many2one('stock.location', required=True, string='ตำแหน่งหยิบ')
    picked_qty = fields.Float(string='จำนวนที่ QC ตรวจผ่าน')
    scanned_qty = fields.Float(string='จำนวนที่สแกนโหลด', readonly=True)


class ResCompany(models.Model):
    _inherit = 'res.company'

    tbf_warehouse_officer_id = fields.Many2one(
        'res.users', string='Aung-Lay / ผู้รับแจ้ง E-PO',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    tbf_warehouse_officer_id = fields.Many2one(
        related='company_id.tbf_warehouse_officer_id', readonly=False,
        string='Aung-Lay / ผู้รับแจ้ง E-PO',
    )


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    tbf_epo_ids = fields.One2many('tbf.epo', 'sale_order_id', string='Picking Order (E-PO)')

    def action_confirm(self):
        result = super().action_confirm()
        if self.env.context.get('tbf_skip_epo'):
            return result
        for sale in self:
            for picking in sale.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing' and p.state != 'cancel'):
                picking._tbf_ensure_epo()
        return result


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    tbf_epo_id = fields.Many2one('tbf.epo', string='TBF E-PO', readonly=True, copy=False)

    def button_validate(self):
        if not self.env.context.get('tbf_shipping_approved'):
            protected = self.filtered(lambda p: p.tbf_epo_id and p.picking_type_id.code == 'outgoing')
            if protected:
                raise UserError(_('กรุณาสแกนและกด SHIPPED OUT ผ่าน E-PO ก่อนยืนยันใบจัดส่ง'))
        return super().button_validate()

    def _tbf_ensure_epo(self, parent=None):
        self.ensure_one()
        if self.tbf_epo_id or self.picking_type_id.code != 'outgoing':
            return self.tbf_epo_id
        sale = self.sale_id
        if not sale:
            return self.env['tbf.epo']
        name = False
        if parent:
            root = parent.parent_id or parent
            number = len(root.child_ids) + 1
            name = '%s-%s' % (root.name, number)
        epo = self.env['tbf.epo'].create({
            'name': name or '/', 'sale_order_id': sale.id, 'picking_id': self.id,
            'parent_id': (parent.parent_id or parent).id if parent else False,
            'officer_id': (self.company_id.tbf_warehouse_officer_id or self.env.ref('base.user_admin')).id,
            'line_ids': [Command.create({
                'move_id': move.id,
                'source_location_id': move.location_id.id,
            }) for move in self.move_ids.filtered(lambda m: m.state != 'cancel')],
        })
        self.tbf_epo_id = epo.id
        epo._notify_officer()
        return epo

    def _create_backorder(self, backorder_moves=None, from_manual_backorder=False):
        backorders = super()._create_backorder(backorder_moves, from_manual_backorder)
        for backorder in backorders:
            parent = backorder.backorder_id.tbf_epo_id
            if parent:
                for move in backorder.move_ids:
                    original = parent.line_ids.filtered(lambda l: l.product_id == move.product_id)[:1]
                    if original:
                        move.location_id = original.source_location_id.id
                if backorder.move_ids:
                    backorder.location_id = backorder.move_ids[0].location_id.id
                backorder._tbf_ensure_epo(parent=parent)
        return backorders
