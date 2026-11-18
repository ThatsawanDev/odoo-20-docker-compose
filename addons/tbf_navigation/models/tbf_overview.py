from datetime import timedelta

from odoo import api, fields, models

THAI_MONTHS = (
    '', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
    'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.',
)

STAGE_TO_INDEX = {
    'so': 0,
    'epo': 1,
    'qc': 2,
    'picking': 3,
    'awaiting': 4,
    'shipped': 6,
}

EPO_STATE_META = {
    'new': ('epo', 'รอส่ง QC', 'blue'),
    'confirmed': ('qc', 'รอ QC', 'orange'),
    'verified': ('picking', 'กำลังหยิบสินค้า', 'blue'),
    'ready': ('awaiting', 'รอจัดส่ง', 'blue'),
}


def _format_thai_date(dt):
    if not dt:
        return ''
    local_dt = fields.Datetime.context_timestamp(dt) if hasattr(dt, 'tzinfo') else dt
    return f'{local_dt.day} {THAI_MONTHS[local_dt.month]} {local_dt.year + 543}'


class TbfOverviewDashboard(models.AbstractModel):
    _name = 'tbf.overview.dashboard'
    _description = 'TBF Furniture Overview Dashboard'

    @api.model
    def _period_domain(self, period):
        now = fields.Datetime.now()
        if period == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return [('date_order', '>=', start)]
        if period == 'week':
            start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            return [('date_order', '>=', start)]
        if period == 'month':
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return [('date_order', '>=', start)]
        if period == 'year':
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return [('date_order', '>=', start)]
        return []

    @api.model
    def _build_steps(self, stage_key, active_tone='blue'):
        items = [
            ('so', 'SO'),
            ('epo', 'E-PO'),
            ('qc', 'QC'),
            ('picking', 'Picking'),
            ('awaiting', 'รอจัดส่ง'),
            ('shipped', 'จัดส่ง'),
        ]
        active_idx = STAGE_TO_INDEX.get(stage_key, 0)
        steps = []
        for idx, (key, label) in enumerate(items):
            if idx < active_idx:
                state = 'done'
            elif idx == active_idx:
                state = 'active'
            else:
                state = 'pending'
            steps.append({
                'key': key,
                'label': label,
                'state': state,
                'tone': active_tone if state == 'active' else '',
            })
        return steps

    @api.model
    def _classify_order(self, order):
        epos = order.tbf_epo_ids
        is_partial = len(epos) > 1 or any(epo.parent_id or epo.child_ids for epo in epos)
        if order.state in ('draft', 'sent') or not epos:
            stage_key = 'so' if order.state in ('draft', 'sent') else 'epo'
            status_label = 'ใบเสนอราคา' if order.state in ('draft', 'sent') else 'รอสร้าง E-PO'
            tone = 'slate' if stage_key == 'so' else 'blue'
            return {
                'stage_key': stage_key,
                'tab_key': 'in_progress',
                'is_partial': False,
                'status_label': status_label,
                'status_tone': tone,
                'active_epo_id': False,
                'active_epo_name': '',
                'steps': self._build_steps(stage_key, tone),
            }

        open_epos = epos.filtered(lambda e: e.state != 'shipped').sorted('id')
        if not open_epos:
            return {
                'stage_key': 'shipped',
                'tab_key': 'shipped',
                'is_partial': is_partial,
                'status_label': 'จัดส่งแล้ว',
                'status_tone': 'green',
                'active_epo_id': epos.sorted('id')[-1].id,
                'active_epo_name': epos.sorted('id')[-1].name,
                'steps': self._build_steps('shipped', 'green'),
            }

        # Use the most advanced or earliest open E-PO to reflect current bottleneck
        priority = {'ready': 4, 'verified': 3, 'confirmed': 2, 'new': 1}
        current_epo = max(open_epos, key=lambda e: (priority.get(e.state, 0), e.id))
        stage_key, status_label, tone = EPO_STATE_META.get(
            current_epo.state, ('epo', 'รอส่ง QC', 'blue')
        )
        return {
            'stage_key': stage_key,
            'tab_key': 'in_progress',
            'is_partial': is_partial,
            'status_label': status_label,
            'status_tone': tone,
            'active_epo_id': current_epo.id,
            'active_epo_name': current_epo.name,
            'steps': self._build_steps(stage_key, tone),
        }

    @api.model
    def get_overview_data(self, period='month', search=''):
        domain = [('state', '!=', 'cancel')] + self._period_domain(period)
        keyword = (search or '').strip()
        if keyword:
            domain += [
                '|', '|', '|',
                ('name', 'ilike', keyword),
                ('partner_id.name', 'ilike', keyword),
                ('order_line.product_id.name', 'ilike', keyword),
                ('order_line.product_id.default_code', 'ilike', keyword),
            ]

        orders = self.env['sale.order'].search(domain, order='date_order desc, id desc')
        stage_counts = {
            'so': len(orders),
            'epo': 0,
            'qc': 0,
            'picking': 0,
            'awaiting': 0,
            'shipped': 0,
        }
        tab_counts = {
            'all': len(orders),
            'in_progress': 0,
            'shipped': 0,
            'partial': 0,
        }

        rows = []
        for order in orders:
            info = self._classify_order(order)
            if info['stage_key'] != 'so':
                stage_counts[info['stage_key']] += 1
            tab_counts[info['tab_key']] += 1
            if info['is_partial']:
                tab_counts['partial'] += 1

            line_count = len(order.order_line.filtered(lambda l: not l.display_type))
            local_dt = fields.Datetime.context_timestamp(self, order.date_order) if order.date_order else False
            date_str = f'{local_dt.day} {THAI_MONTHS[local_dt.month]} {local_dt.year + 543}' if local_dt else ''
            active_epo = self.env['tbf.epo'].browse(info['active_epo_id']) if info['active_epo_id'] else self.env['tbf.epo']
            internal_picking = active_epo.internal_picking_id or order.tbf_epo_ids.mapped('internal_picking_id')[:1]
            shipment_picking = active_epo.picking_id or order.picking_ids.filtered(
                lambda p: p.picking_type_id.code == 'outgoing'
            )[:1]
            rows.append({
                'id': order.id,
                'name': order.name,
                'partner_name': order.partner_id.display_name or '-',
                'date_display': date_str,
                'line_count': line_count,
                'amount_display': f'{order.amount_total:,.2f} ฿',
                'stage_key': info['stage_key'],
                'tab_key': info['tab_key'],
                'is_partial': info['is_partial'],
                'status_label': info['status_label'],
                'status_tone': info['status_tone'],
                'active_epo_id': info['active_epo_id'],
                'active_epo_name': info['active_epo_name'],
                'internal_picking_id': internal_picking.id if internal_picking else False,
                'shipment_picking_id': shipment_picking.id if shipment_picking else False,
                'steps': info['steps'],
            })

        return {
            'stages': [
                {'key': 'so', 'title': 'Sales Order (SO)', 'subtitle': '', 'count': stage_counts['so'], 'tone': 'blue', 'icon': 'fa-file-text-o'},
                {'key': 'epo', 'title': 'E-PO', 'subtitle': '(ใบสั่งหยิบสินค้า)', 'count': stage_counts['epo'], 'tone': 'sky', 'icon': 'fa-truck'},
                {'key': 'qc', 'title': 'QC', 'subtitle': '(ตรวจสอบสินค้า)', 'count': stage_counts['qc'], 'tone': 'amber', 'icon': 'fa-cube'},
                {'key': 'picking', 'title': 'Picking', 'subtitle': '(หยิบและเตรียมสินค้า)', 'count': stage_counts['picking'], 'tone': 'violet', 'icon': 'fa-shopping-cart'},
                {'key': 'awaiting', 'title': 'Awaiting to Sell', 'subtitle': '(รอจัดส่ง)', 'count': stage_counts['awaiting'], 'tone': 'indigo', 'icon': 'fa-clock-o'},
                {'key': 'shipped', 'title': 'Shipped Out', 'subtitle': '(จัดส่งแล้ว)', 'count': stage_counts['shipped'], 'tone': 'emerald', 'icon': 'fa-check-circle-o'},
            ],
            'tab_counts': tab_counts,
            'orders': rows,
        }
