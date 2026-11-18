"""Configure the TBF Furniture navigation in a cloned Odoo database.

Run with: odoo shell -d DATABASE --no-http, then exec this file.
The script is idempotent and changes only menu records.
"""

Menu = env['ir.ui.menu'].sudo()
Data = env['ir.model.data'].sudo()


def menu(key, name, parent=None, action=None, sequence=10, source=None):
    xmlid = f'tbf_navigation.{key}'
    record = env.ref(xmlid, raise_if_not_found=False)
    values = {
        'name': name,
        'parent_id': parent.id if parent else False,
        'action': action or False,
        'sequence': sequence,
        'active': True,
    }
    if record:
        record.sudo().write(values)
    else:
        record = Menu.create(values)
        Data.create({
            'module': 'tbf_navigation', 'name': key,
            'model': 'ir.ui.menu', 'res_id': record.id,
            'noupdate': True,
        })
    if source:
        record.group_ids = [(6, 0, Menu.browse(source).group_ids.ids)]
    return record


# Keep installed modules intact. Only remove unrelated apps from navigation.
for root_id in (76, 265, 302, 315, 190, 123, 131, 66):
    Menu.browse(root_id).active = False

root = menu('root', 'TBF Furniture ERP', sequence=1)

sales = menu('sales', 'ฝ่ายขาย', sequence=10)
overview_action = env.ref('tbf_navigation.action_tbf_overview')
menu('overview', 'ภาพรวมงานขาย', sales, f'ir.actions.client,{overview_action.id}', 5, 244)
menu('quotation', 'ใบเสนอราคา', sales, 'ir.actions.act_window,470', 10, 244)
menu('sales_order', 'คำสั่งขาย', sales, 'ir.actions.act_window,468', 20, 245)
menu('sales_stock', 'ตรวจสอบสินค้าคงเหลือ', sales, 'ir.actions.act_window,417', 30, 228)
menu('customers', 'ลูกค้า', sales, 'ir.actions.act_window,321', 40, 247)
menu('pricelists', 'ราคาขายตามประเภทลูกค้า', sales, 'ir.actions.act_window,216', 50, 251)
env['ir.actions.act_window'].browse(216).with_context(lang='th_TH').write({
    'name': 'ราคาขายตามประเภทลูกค้า',
})

planning = menu('planning', 'ฝ่ายวางแผนและจัดซื้อ', sequence=20)
menu('replenishment', 'วางแผนเติมสินค้า', planning, 'ir.actions.server,428', 10, 231)
menu('rfq', 'ใบขอราคา', planning, 'ir.actions.act_window,541', 20, 340)
menu('purchase_order', 'ใบสั่งซื้อ', planning, 'ir.actions.act_window,542', 30, 341)
menu('receipt', 'รับสินค้าเข้า', planning, 'ir.actions.server,394', 40, 221)
menu('vendors', 'ผู้ขาย', planning, 'ir.actions.act_window,322', 50, 331)

warehouse = menu('warehouse', 'ฝ่ายคลังสินค้า', sequence=30)
menu('warehouse_overview', 'ภาพรวมคลังสินค้า', warehouse, 'ir.actions.act_window,411', 10, 226)
menu('deliveries', 'ตรวจสอบ หยิบ และจัดส่ง', warehouse, 'ir.actions.server,395', 20, 222)
menu('transfers', 'โอนย้ายสินค้า', warehouse, 'ir.actions.server,396', 30, 223)
menu('packages', 'บรรจุภัณฑ์', warehouse, 'ir.actions.act_window,437', 40, 238)
menu('stock_issue', 'เบิกสินค้าด่วน', warehouse, 'ir.actions.act_window,626', 50, 387)

inventory = menu('inventory', 'ฝ่ายควบคุมสินค้า', sequence=40)
menu('products', 'สินค้า', inventory, 'ir.actions.act_window,418', 10, 227)
menu('stock', 'ติดตามสต็อก', inventory, 'ir.actions.act_window,417', 20, 228)
menu('stock_count', 'ตรวจนับสต็อก', inventory, 'ir.actions.server,368', 30, 215)
menu('stock_by_location', 'สต็อกตามตำแหน่ง', inventory, 'ir.actions.server,369', 40, 216)
menu('moves_history', 'ประวัติการเคลื่อนไหว', inventory, 'ir.actions.act_window,379', 50, 218)

finance = menu('finance', 'ฝ่ายการเงินและบัญชี', sequence=60)
menu('invoices', 'ใบแจ้งหนี้ลูกค้า', finance, 'ir.actions.act_window,282', 10, 141)
menu('customer_payments', 'รับชำระเงิน', finance, 'ir.actions.act_window,255', 20, 143)
menu('vendor_bills', 'ใบแจ้งหนี้ผู้ขาย', finance, 'ir.actions.act_window,285', 30, 147)
menu('journal_entries', 'รายการบัญชี', finance, 'ir.actions.act_window,279', 40, 154)

reports = menu('reports', 'ฝ่ายบริหารและรายงาน', sequence=70)
menu('sales_report', 'ยอดขาย', reports, 'ir.actions.act_window,454', 10, 254)
menu('customer_report', 'ยอดขายตามลูกค้า', reports, 'ir.actions.act_window,457', 20, 257)
menu('purchase_report', 'การจัดซื้อ', reports, 'ir.actions.act_window,555', 30, 344)
menu('stock_report', 'การเคลื่อนไหวสินค้า', reports, 'ir.actions.act_window,380', 40, 219)
menu('invoice_report', 'วิเคราะห์ใบแจ้งหนี้', reports, 'ir.actions.act_window,314', 50, 164)

# The primary apps follow the actors in the TBF E-PO process. Purchasing,
# accounting and stock analysis remain available as supporting work.
planning.name = 'ฝ่ายคลังสินค้า'
warehouse.name = 'ฝ่ายควบคุมคุณภาพ'
inventory.name = 'ฝ่ายจัดส่งสินค้า'
for key in (
    'replenishment', 'rfq', 'purchase_order', 'receipt', 'vendors',
    'warehouse_overview', 'deliveries', 'transfers', 'packages', 'stock_issue',
    'stock_count', 'moves_history', 'vendor_bills', 'journal_entries',
):
    env.ref(f'tbf_navigation.{key}').sudo().active = False

epo_action = env.ref('tbf_navigation.action_tbf_epo')
qc_action = env.ref('tbf_navigation.action_tbf_epo_qc')
loading_action = env.ref('tbf_navigation.action_tbf_epo_loading')
menu('epo_all', 'ใบสั่งหยิบสินค้า (E-PO)', planning,
     f'ir.actions.act_window,{epo_action.id}', 10, 222)
env.ref('tbf_navigation.loading_work').sudo().active = False
menu('wh_receipt', 'รับสินค้าเข้า', planning, 'ir.actions.server,394', 20, 221)
menu('shipment_history', 'ประวัติใบจัดส่ง', planning, 'ir.actions.server,395', 40, 222)
menu('stock_moves', 'ย้ายสต็อก', planning, 'ir.actions.server,396', 50, 223)
menu('wh_products', 'สินค้า', planning, 'ir.actions.act_window,418', 60, 227)
menu('wh_stock', 'ติดตามสต็อก', planning, 'ir.actions.act_window,417', 70, 228)
menu('wh_stock_by_location', 'สต็อกตามตำแหน่ง', planning, 'ir.actions.server,369', 80, 216)
menu('qc_work', 'รับงานและตรวจสอบสินค้า', warehouse,
     f'ir.actions.act_window,{qc_action.id}', 10, 222)
inventory.active = False
purchase = menu('purchasing', 'ฝ่ายวางแผนและจัดซื้อ', sequence=50)
menu('replenishment', 'วางแผนเติมสินค้า', purchase, 'ir.actions.server,428', 10, 231)
menu('rfq', 'ใบขอราคา', purchase, 'ir.actions.act_window,541', 20, 340)
menu('purchase_support', 'ใบสั่งซื้อ', purchase, 'ir.actions.act_window,542', 30, 341)
menu('receipt_support', 'รับสินค้าเข้า', purchase, 'ir.actions.server,394', 40, 221)
menu('vendors', 'ผู้ขาย', purchase, 'ir.actions.act_window,322', 50, 331)
menu('vendor_bills_support', 'ใบแจ้งหนี้ผู้ขาย', finance, 'ir.actions.act_window,285', 50, 147)
for app, icon_module in (
    (sales, 'sale_management'),
    (planning, 'stock'),
    (warehouse, 'product'),
    (purchase, 'purchase'),
    (finance, 'account'),
    (reports, 'spreadsheet_dashboard'),
):
    app.web_icon = f'{icon_module},static/description/icon.png'

# Each function is a home-screen app; remove the now-empty wrapper and
# the standard Sales app so there are no duplicate entry points.
root.active = False
Menu.browse(242).active = False

env.cr.commit()
print('TBF navigation configured:', root.id)
