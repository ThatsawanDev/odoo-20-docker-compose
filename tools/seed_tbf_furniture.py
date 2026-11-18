"""Idempotent furniture demo data for tbf_furniture_demo_20261117 only."""

from pathlib import Path

from odoo import Command, fields
from odoo.orm.fields_binary import BinaryBytes

assert env.cr.dbname == 'tbf_furniture_demo_20261117', 'Refusing to seed another database'

warehouse = env['stock.warehouse'].search([], limit=1)
company = warehouse.company_id
admin = env.ref('base.user_admin')
Product = env['product.product'].sudo()
Partner = env['res.partner'].sudo()

products = {}
for code, name, price, weight in (
    ('TBF-TABLE-120', 'โต๊ะอาหารไม้ 120 ซม.', 4500, 22.0),
    ('TBF-CHAIR-OAK', 'เก้าอี้ไม้โอ๊ค', 1450, 6.5),
    ('TBF-DESK-140', 'โต๊ะทำงาน 140 ซม.', 6200, 31.0),
    ('TBF-SHELF-4', 'ชั้นวางของ 4 ชั้น', 2900, 18.0),
    ('TBF-TOP-WHITE', 'หน้าโต๊ะสีขาว', 1800, 10.0),
    ('TBF-LEG-A', 'ขาโต๊ะแบบ A', 900, 5.0),
    ('TBF-FRAME', 'โครงโต๊ะ', 1200, 7.0),
):
    product = Product.search([('default_code', '=', code)], limit=1)
    if not product:
        product = Product.create({
            'name': name, 'default_code': code, 'barcode': 'TBF-BAR-' + code,
            'is_storable': True, 'tracking': False, 'list_price': price,
            'weight': weight, 'sale_ok': True, 'purchase_ok': True,
        })
        env['stock.quant'].sudo()._update_available_quantity(product, warehouse.lot_stock_id, 80)
    products[code] = product

demo_photos = {
    'TBF-TABLE-120': {
        'main': '/mnt/extra-addons/tbf_demo_images/TBF-DM-TABLE.png',
        'extras': [
            ('มุมด้านข้าง', '/mnt/extra-addons/tbf_navigation/demo_images/TBF-TABLE-120-side.png'),
            ('มุมมองด้านบน', '/mnt/extra-addons/tbf_navigation/demo_images/TBF-TABLE-120-top.png'),
            ('ชุดจัดวาง 4 ที่นั่ง', '/mnt/extra-addons/tbf_demo_images/TBF-DM-SET4.png'),
        ],
    },
    'TBF-CHAIR-OAK': {
        'main': '/mnt/extra-addons/tbf_demo_images/TBF-DM-CHAIR.png',
        'extras': [
            ('มุมเบาะนั่ง', '/mnt/extra-addons/tbf_demo_images/TBF-DM-SEAT.png'),
            ('มุมสีเบาะทางเลือก', '/mnt/extra-addons/tbf_demo_images/TBF-DM-SEAT-ALT.png'),
        ],
    },
    'TBF-DESK-140': {
        'main': '/mnt/extra-addons/tbf_navigation/demo_images/TBF-DESK-140-main.png',
        'extras': [
            ('มุมด้านข้าง', '/mnt/extra-addons/tbf_navigation/demo_images/TBF-TABLE-120-side.png'),
            ('มุมมองด้านบน', '/mnt/extra-addons/tbf_navigation/demo_images/TBF-TABLE-120-top.png'),
        ],
    },
    'TBF-SHELF-4': {
        'main': '/mnt/extra-addons/tbf_demo_images/TBF-DM-CABINET.png',
        'extras': [
            ('ภาพจัดวางในห้องรับแขก', '/mnt/extra-addons/tbf_demo_images/TBF-DM-SOFA.png'),
        ],
    },
}
for code, photos in demo_photos.items():
    template = products[code].product_tmpl_id
    if not template.image_1920:
        template.image_1920 = BinaryBytes(Path(photos['main']).read_bytes(), Path(photos['main']).name)
    for sequence, (caption, path) in enumerate(photos['extras'], start=1):
        if not template.thai_image_ids.filtered(lambda photo: photo.name == caption):
            env['thai.product.image'].sudo().create({
                'product_tmpl_id': template.id,
                'sequence': sequence * 10,
                'name': caption,
                'image_1920': BinaryBytes(Path(path).read_bytes(), Path(path).name),
            })

vendors = {}
for key, name in (
    ('wood', 'TBF ตัวอย่าง — โรงงานไม้สยาม'),
    ('fittings', 'TBF ตัวอย่าง — อุปกรณ์เฟอร์นิเจอร์ไทย'),
):
    vendor = Partner.search([('name', '=', name)], limit=1)
    if not vendor:
        vendor = Partner.create({'name': name, 'supplier_rank': 1, 'is_company': True})
    vendors[key] = vendor

pricelists = {}
for key, label, factor in (
    ('wholesale', 'TBF ตัวอย่าง — ราคาขายส่ง', 0.80),
    ('retail', 'TBF ตัวอย่าง — ราคาขายปลีก', 1.00),
    ('government', 'TBF ตัวอย่าง — ราคาหน่วยงานรัฐ', 0.92),
):
    pricelist = env['product.pricelist'].sudo().search([('name', '=', label)], limit=1)
    if not pricelist:
        pricelist = env['product.pricelist'].sudo().create({
            'name': label, 'currency_id': company.currency_id.id,
        })
        for product in products.values():
            env['product.pricelist.item'].sudo().create({
                'pricelist_id': pricelist.id,
                'applied_on': '1_product',
                'product_tmpl_id': product.product_tmpl_id.id,
                'compute_price': 'fixed',
                'fixed_price': round(product.list_price * factor, 2),
            })
    pricelists[key] = pricelist

customers = {}
for key, name, level in (
    ('wholesale', 'TBF ตัวอย่าง — ร้านเฟอร์นิเจอร์ภาคใต้', 'wholesale'),
    ('retail', 'TBF ตัวอย่าง — คุณสุภาวดี', 'retail'),
    ('government', 'TBF ตัวอย่าง — สำนักงานจังหวัด', 'government'),
):
    customer = Partner.search([('name', '=', name)], limit=1)
    if not customer:
        customer = Partner.create({
            'name': name, 'customer_rank': 1,
            'property_product_pricelist': pricelists[level].id,
        })
    customers[key] = customer

other_location = env['stock.location'].sudo().search([
    ('name', '=', 'TBF ตัวอย่าง — โซนเฟอร์นิเจอร์'),
    ('location_id', '=', warehouse.view_location_id.id),
], limit=1)
if not other_location:
    other_location = env['stock.location'].sudo().create({
        'name': 'TBF ตัวอย่าง — โซนเฟอร์นิเจอร์',
        'location_id': warehouse.view_location_id.id,
        'usage': 'internal',
        'company_id': company.id,
    })
    for code in ('TBF-TOP-WHITE', 'TBF-LEG-A', 'TBF-FRAME'):
        product = products[code]
        env['stock.quant'].sudo()._update_available_quantity(product, warehouse.lot_stock_id, -20)
        env['stock.quant'].sudo()._update_available_quantity(product, other_location, 20)


def make_order(key, customer, code, qty):
    marker = 'TBF-DEMO-' + key
    sale = env['sale.order'].sudo().search([('client_order_ref', '=', marker)], limit=1)
    if not sale:
        level_factor = {
            customers['wholesale'].id: 0.80,
            customers['retail'].id: 1.00,
            customers['government'].id: 0.92,
        }[customer.id]
        sale = env['sale.order'].sudo().create({
            'partner_id': customer.id,
            'user_id': admin.id,
            'warehouse_id': warehouse.id,
            'pricelist_id': customer.property_product_pricelist.id,
            'client_order_ref': marker,
            'order_line': [Command.create({
                'product_id': products[code].id,
                'name': products[code].name,
                'product_uom_qty': qty,
                'price_unit': round(products[code].list_price * level_factor, 2),
            })],
        })
        sale.action_confirm()
    elif sale.user_id != admin:
        sale.user_id = admin.id
    return sale.tbf_epo_ids.filtered(lambda e: not e.parent_id)[:1]


def advance(epo, target, picked=None):
    if epo.state == 'new' and target != 'new':
        epo.action_qc_confirm()
    if epo.state == 'confirmed' and target in ('verified', 'ready', 'shipped'):
        epo.line_ids.picked_qty = picked or epo.line_ids.requested_qty
        epo.action_product_verified()
    if epo.state == 'verified' and target in ('ready', 'shipped'):
        epo.action_picking_completed()
    if epo.state == 'ready' and target == 'shipped':
        for line in epo.line_ids:
            while line.uom_id.compare(line.scanned_qty, line.picked_qty) < 0:
                epo.scan_code = line.product_id.barcode
                epo.action_scan()
        epo.action_shipped_out()


examples = (
    ('NEW', customers['wholesale'], 'TBF-TABLE-120', 3, 'new', None),
    ('QC-RECEIVED', customers['retail'], 'TBF-CHAIR-OAK', 4, 'confirmed', None),
    ('QC-VERIFIED', customers['government'], 'TBF-DESK-140', 2, 'verified', None),
    ('READY', customers['wholesale'], 'TBF-SHELF-4', 3, 'ready', None),
    ('SHIPPED', customers['retail'], 'TBF-TABLE-120', 2, 'shipped', None),
    ('PARTIAL', customers['government'], 'TBF-CHAIR-OAK', 5, 'shipped', 2),
)
for key, customer, code, qty, target, picked in examples:
    epo = make_order(key, customer, code, qty)
    advance(epo, target, picked)
    print(key, epo.name, epo.state)

for key, customer, code, qty in (
    ('QUOTE-WHOLESALE', customers['wholesale'], 'TBF-TABLE-120', 4),
    ('QUOTE-RETAIL', customers['retail'], 'TBF-CHAIR-OAK', 2),
    ('QUOTE-GOVERNMENT', customers['government'], 'TBF-DESK-140', 3),
):
    marker = 'TBF-DEMO-' + key
    quotation = env['sale.order'].sudo().search([('client_order_ref', '=', marker)], limit=1)
    if not quotation:
        level_factor = {
            customers['wholesale'].id: 0.80,
            customers['retail'].id: 1.00,
            customers['government'].id: 0.92,
        }[customer.id]
        quotation = env['sale.order'].sudo().create({
            'partner_id': customer.id, 'user_id': admin.id,
            'warehouse_id': warehouse.id,
            'pricelist_id': customer.property_product_pricelist.id,
            'client_order_ref': marker,
            'order_line': [Command.create({
                'product_id': products[code].id,
                'name': products[code].name,
                'product_uom_qty': qty,
                'price_unit': round(products[code].list_price * level_factor, 2),
            })],
        })
    elif quotation.user_id != admin:
        quotation.user_id = admin.id
    quotation.tbf_show_catalog_images = True
    quotation.note = (
        '<p><strong>ตัวอย่างเงื่อนไขและข้อกำหนด</strong></p>'
        '<ul><li>ราคานี้ใช้กับสินค้าและจำนวนตามใบเสนอราคาฉบับนี้</li>'
        '<li>ยืนราคา 30 วันนับจากวันที่ออกใบเสนอราคา</li>'
        '<li>กำหนดส่งมอบและค่าขนส่งให้ยืนยันก่อนออกคำสั่งขาย</li></ul>'
    )

rfq = env['purchase.order'].sudo().search([('partner_ref', '=', 'TBF-DEMO-RFQ')], limit=1)
if not rfq:
    rfq = env['purchase.order'].sudo().create({
        'partner_id': vendors['wood'].id,
        'partner_ref': 'TBF-DEMO-RFQ',
        'order_line': [Command.create({
            'product_id': products['TBF-TOP-WHITE'].id,
            'name': products['TBF-TOP-WHITE'].name,
            'product_qty': 10,
            'price_unit': 1100,
            'date_planned': fields.Datetime.now(),
        })],
    })

po = env['purchase.order'].sudo().search([('partner_ref', '=', 'TBF-DEMO-PO')], limit=1)
if not po:
    po = env['purchase.order'].sudo().create({
        'partner_id': vendors['fittings'].id,
        'partner_ref': 'TBF-DEMO-PO',
        'order_line': [Command.create({
            'product_id': products['TBF-LEG-A'].id,
            'name': products['TBF-LEG-A'].name,
            'product_qty': 12,
            'price_unit': 650,
            'date_planned': fields.Datetime.now(),
        })],
    })
    po.button_confirm()

invoice = env['account.move'].sudo().search([('ref', '=', 'TBF-DEMO-INVOICE')], limit=1)
if not invoice:
    invoice = env['account.move'].sudo().create({
        'move_type': 'out_invoice', 'partner_id': customers['retail'].id,
        'invoice_date': fields.Date.today(), 'ref': 'TBF-DEMO-INVOICE',
        'invoice_line_ids': [Command.create({
            'product_id': products['TBF-TABLE-120'].id,
            'quantity': 1, 'price_unit': products['TBF-TABLE-120'].list_price,
        })],
    })

vendor_bill = env['account.move'].sudo().search([('ref', '=', 'TBF-DEMO-VENDOR-BILL')], limit=1)
if not vendor_bill:
    vendor_bill = env['account.move'].sudo().create({
        'move_type': 'in_invoice', 'partner_id': vendors['wood'].id,
        'invoice_date': fields.Date.today(), 'ref': 'TBF-DEMO-VENDOR-BILL',
        'invoice_line_ids': [Command.create({
            'product_id': products['TBF-TOP-WHITE'].id,
            'quantity': 2, 'price_unit': 1100,
        })],
    })

payment = env['account.payment'].sudo().search([('memo', '=', 'TBF-DEMO-PAYMENT')], limit=1)
if not payment:
    bank = env['account.journal'].sudo().search([
        ('company_id', '=', company.id), ('type', '=', 'bank'),
    ], limit=1)
    payment = env['account.payment'].sudo().create({
        'partner_id': customers['retail'].id,
        'partner_type': 'customer', 'payment_type': 'inbound',
        'journal_id': bank.id, 'date': fields.Date.today(),
        'amount': 500, 'memo': 'TBF-DEMO-PAYMENT',
    })

env.cr.commit()
print('TBF furniture demo data ready')
