# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Lazada Connector by Thatsawan",
    'summary': "Import Lazada orders and sync deliveries for Odoo Community",
    'description': """
Import your Lazada orders in Odoo Community and synchronize deliveries
======================================================================
Developed & Customized by Thatsawan

Key Features
------------
* Import orders from multiple shops
* Orders are matched with Odoo products based on their internal reference (SKU in Lazada)
* Support for both Fulfillment by Lazada (FBL), Fulfillment by Merchant (FBM):
* FBL: Importing the completed orders
* FBM: Delivery information is fetched from Lazada, track and synchronize the stock level to Lazada.
""",
    'category': 'Sales/Sales',
    'application': True,
    'depends': ['sale_management', 'stock_delivery'],
    'data': [
        'data/mail_template_data.xml',
        'data/data.xml',
        'data/ir_cron.xml',
        'security/ir.access.csv',
        'wizard/lazada_shop_create_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/lazada_shop_views.xml',
        'views/lazada_item_views.xml',
        'views/stock_picking_views.xml',
        'views/menus.xml',
    ],
    'author': 'Thatsawan',
    'license': 'LGPL-3',
}
