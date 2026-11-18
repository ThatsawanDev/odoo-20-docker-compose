{
    'name': 'Unified QWeb Report Layout (Odoo 20)',
    'version': '20.0.1.0.0',
    'category': 'Reporting',
    'summary': 'Centralized QWeb Report Layout for Quotation, Sales Order, Purchase Order, Delivery Note, Invoice, Receipt, and Credit Note',
    'description': """
Unified QWeb Report Layout for Odoo 20
======================================
Overrides standard print reports with a single centralized QWeb Report Layout inherited from web.external_layout:
- ใบเสนอราคา (Quotation)
- ใบสั่งขาย (Sales Order)
- ใบสั่งซื้อ (Purchase Order)
- ใบส่งสินค้า (Delivery Note)
- ใบแจ้งหนี้ (Invoice)
- ใบเสร็จรับเงิน (Receipt)
- ใบลดหนี้ (Credit Note)
    """,
    'author': 'Antigravity',
    'depends': [
        'web',
        'sale',
        'purchase',
        'stock',
        'account',
        'thai_sales_stock_easy',
    ],
    'data': [
        'report/unified_layout_templates.xml',
        'report/report_overrides.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
