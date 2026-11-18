"""Transactional Odoo shell smoke test for the TBF E-PO workflow."""

from odoo import Command

try:
    warehouse = env['stock.warehouse'].search([], limit=1)
    partner = env['res.partner'].create({'name': 'TBF Workflow Smoke Customer'})
    product = env['product.product'].create({
        'name': 'TBF Workflow Smoke Product',
        'is_storable': True,
        'tracking': False,
        'barcode': 'TBF-SMOKE-001',
        'list_price': 100,
    })
    env['stock.quant']._update_available_quantity(product, warehouse.lot_stock_id, 12)

    def make_sale(qty):
        sale = env['sale.order'].create({
            'partner_id': partner.id,
            'warehouse_id': warehouse.id,
            'order_line': [Command.create({
                'product_id': product.id,
                'name': product.name,
                'product_uom_qty': qty,
                'price_unit': 100,
            })],
        })
        sale.action_confirm()
        epo = sale.tbf_epo_ids[:1]
        assert epo and epo.picking_id.sale_id == sale
        return epo

    epo = make_sale(2)
    epo.action_qc_confirm()
    epo.line_ids.picked_qty = 2
    epo.action_product_verified()
    epo.action_picking_completed()
    assert epo.internal_picking_id.state == 'done'
    assert epo.picking_id.location_id == epo.awaiting_location_id
    assert sum(env['stock.quant'].search([
        ('product_id', '=', product.id), ('location_id', '=', epo.awaiting_location_id.id),
    ]).mapped('quantity')) == 2
    for _ in range(2):
        epo.scan_code = product.barcode
        epo.action_scan()
    epo.action_shipped_out()
    assert epo.state == 'shipped' and epo.picking_id.state == 'done'
    assert env['stock.quant']._get_available_quantity(product, epo.awaiting_location_id) == 0
    print('FULL OK', epo.name)

    partial = make_sale(5)
    partial.action_qc_confirm()
    partial.line_ids.picked_qty = 2
    partial.action_product_verified()
    partial.action_picking_completed()
    for _ in range(2):
        partial.scan_code = product.barcode
        partial.action_scan()
    partial.action_shipped_out()
    children = partial.child_ids
    assert len(children) == 1 and children[0].name == partial.name + '-1'
    assert children[0].state == 'new'
    assert children[0].picking_id.location_id == warehouse.lot_stock_id
    assert sum(env['stock.quant'].search([
        ('product_id', '=', product.id), ('location_id', '=', warehouse.lot_stock_id.id),
    ]).mapped('quantity')) == 8
    print('PARTIAL OK', partial.name, children[0].name)

    tight_product = env['product.product'].create({
        'name': 'TBF Exact Stock Smoke Product', 'is_storable': True,
        'tracking': False, 'barcode': 'TBF-SMOKE-EXACT',
    })
    env['stock.quant']._update_available_quantity(tight_product, warehouse.lot_stock_id, 1)
    tight_sale = env['sale.order'].create({
        'partner_id': partner.id, 'warehouse_id': warehouse.id,
        'order_line': [Command.create({
            'product_id': tight_product.id, 'product_uom_qty': 1,
            'name': tight_product.name, 'price_unit': 100,
        })],
    })
    tight_sale.action_confirm()
    tight_epo = tight_sale.tbf_epo_ids[:1]
    tight_epo.action_qc_confirm()
    tight_epo.line_ids.picked_qty = 1
    tight_epo.action_product_verified()
    tight_epo.action_picking_completed()
    assert tight_epo.state == 'ready'
    print('EXACT STOCK OK', tight_epo.name)
finally:
    env.cr.rollback()
