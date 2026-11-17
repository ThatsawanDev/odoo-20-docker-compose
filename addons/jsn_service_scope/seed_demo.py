"""One-time seed for the isolated demonstration database."""
from pathlib import Path
from odoo.orm.fields_binary import BinaryBytes

images = {
    'machine_e860tp_demo.png': ['machine_e860_demo_1', 'machine_e860_demo_2'],
    'machine_e850t_demo.png': ['machine_e850_demo'],
}
for filename, xmlids in images.items():
    data = BinaryBytes((Path('/mnt/extra-addons/jsn_service_scope/static/src/img') / filename).read_bytes(), filename)
    for xmlid in xmlids:
        env.ref('jsn_service_scope.' + xmlid).image_1920 = data

labor = env.ref('jsn_service_scope.product_service_labor', raise_if_not_found=False)
if not labor:
    labor = env['product.product'].search([('default_code', '=', 'SVC-LABOR')], limit=1)
if not labor:
    labor = env['product.product'].create({'name': 'ค่าแรงบริการช่าง (ตัวอย่าง)', 'default_code': 'SVC-LABOR', 'type': 'service', 'list_price': 500})

warehouse = env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1)
if warehouse:
    for xmlid, quantity in [('product_printhead', 8), ('product_filter', 24)]:
        product = env.ref('jsn_service_scope.' + xmlid)
        current = env['stock.quant']._get_available_quantity(product, warehouse.lot_stock_id)
        if current < quantity:
            env['stock.quant']._update_available_quantity(product, warehouse.lot_stock_id, quantity - current)

if not env['sale.order'].search([('client_order_ref', '=', 'JSN-DEMO-QUOTE')], limit=1):
    env['sale.order'].create({
        'partner_id': env.ref('jsn_service_scope.partner_food_demo').id,
        'client_order_ref': 'JSN-DEMO-QUOTE',
        'order_line': [(0, 0, {
            'product_id': env.ref('jsn_service_scope.product_e860tp').id,
            'product_uom_qty': 1,
            'price_unit': 185000,
        })],
    })

account_model = env['account.asset.asset']
existing_asset = account_model.search([('code', '=', 'FA-DEMO-001')], limit=1)
if existing_asset and not existing_asset.service_machine_id:
    existing_asset.service_machine_id = env.ref('jsn_service_scope.machine_e860_demo_1')
if not existing_asset:
    fixed = env['account.account'].search([('account_type', '=', 'asset_fixed')], limit=1)
    expense = env['account.account'].search([('account_type', '=', 'expense')], limit=1)
    journal = env['account.journal'].search([('type', '=', 'general')], limit=1)
    if fixed and expense and journal:
        account_model.create({
            'name': 'เครื่องพิมพ์สำรอง EMICO E860TP (ตัวอย่าง)',
            'code': 'FA-DEMO-001',
            'value': 185000,
            'salvage_value': 5000,
            'date': '2026-01-01',
            'method_number': 60,
            'method_period': 1,
            'account_asset_id': fixed.id,
            'account_depreciation_id': fixed.id,
            'account_depreciation_expense_id': expense.id,
            'journal_id': journal.id,
            'service_location': 'คลังเครื่องสำรอง',
            'service_machine_id': env.ref('jsn_service_scope.machine_e860_demo_1').id,
        })
env.cr.commit()
print('DEMO_SEEDED', account_model.search_count([('code', '=', 'FA-DEMO-001')]))
