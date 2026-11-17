from odoo.exceptions import UserError

order = env.ref('jsn_service_scope.service_demo_inhouse')
product = env.ref('jsn_service_scope.product_filter')
warehouse = env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1)
assert warehouse
vendor = env['res.partner'].create({'name': 'ผู้ขายอะไหล่ทดสอบ', 'supplier_rank': 1})
order.part_line_ids.write({'quantity': 30})
order.warehouse_id = warehouse
try:
    order.action_create_spare_issue()
    raise AssertionError('shortage was not blocked')
except UserError:
    pass
wizard = env['jsn.service.purchase.wizard'].create({
    'service_order_id': order.id, 'vendor_id': vendor.id, 'warehouse_id': warehouse.id,
})
purchase_action = wizard.action_create_purchase()
assert purchase_action['res_model'] == 'purchase.order'
purchase = order.purchase_order_id
assert purchase.order_line and purchase.order_line.product_id == product
assert purchase.order_line.product_qty > 0
try:
    order.action_done()
    raise AssertionError('work order closed before issue')
except UserError:
    pass
print('FLOW_SHORTAGE_OK', purchase.name, purchase.order_line.product_qty)

purchase.button_confirm()
receipt = purchase.picking_ids[:1]
assert receipt
receipt.action_assign()
for move in receipt.move_ids:
    move.quantity = move.product_uom_qty
receipt.button_validate()
assert receipt.state == 'done'
issue_action = order.action_create_spare_issue()
assert issue_action['res_model'] == 'stock.picking'
issue = order.issue_picking_id
for move in issue.move_ids:
    move.quantity = move.product_uom_qty
issue_result = issue.button_validate()
if isinstance(issue_result, dict) and issue_result.get('res_model') == 'confirm.stock.sms':
    env['confirm.stock.sms'].browse(issue_result['res_id']).with_context(**issue_result['context']).dont_send_sms()
assert issue.state == 'done'
order.action_done()
assert order.state == 'done'
print('FLOW_STOCK_OK', receipt.name, issue.name, order.state)

sale = env['sale.order'].create({
    'partner_id': order.partner_id.id,
    'order_line': [(0, 0, {'product_id': env.ref('jsn_service_scope.product_e860tp').id, 'product_uom_qty': 1, 'price_unit': 185000})],
})
wizard2 = env['jsn.sale.machine.wizard'].create({
    'sale_order_id': sale.id,
    'product_id': env.ref('jsn_service_scope.product_e860tp').id,
    'model_id': env.ref('jsn_service_scope.model_e860tp').id,
    'serial_number': 'TEST-NEW-001',
})
try:
    wizard2.action_register()
    raise AssertionError('draft sale registration was not blocked')
except UserError:
    pass
print('FLOW_SALE_GUARD_OK', sale.name)

machine_product = env.ref('jsn_service_scope.product_e860tp')
lot = env['stock.lot'].create({'name': 'TEST-NEW-001', 'product_id': machine_product.id, 'company_id': env.company.id})
env['stock.quant']._update_available_quantity(machine_product, warehouse.lot_stock_id, 1, lot_id=lot)
sale.action_confirm()
delivery = sale.picking_ids[:1]
assert delivery
delivery.action_assign()
for move in delivery.move_ids:
    move.quantity = move.product_uom_qty
    for move_line in move.move_line_ids:
        move_line.lot_id = lot
delivery_result = delivery.button_validate()
if isinstance(delivery_result, dict) and delivery_result.get('res_model') == 'confirm.stock.sms':
    env['confirm.stock.sms'].browse(delivery_result['res_id']).with_context(**delivery_result['context']).dont_send_sms()
assert delivery.state == 'done'
wizard2.lot_id = lot
wizard2.serial_number = lot.name
machine_action = wizard2.action_register()
assert machine_action['res_model'] == 'service.machine.asset'
machine = env['service.machine.asset'].browse(machine_action['res_id'])
assert machine.sale_order_id == sale and machine.delivery_picking_id == delivery
print('FLOW_MACHINE_OK', sale.name, machine.serial_number)
