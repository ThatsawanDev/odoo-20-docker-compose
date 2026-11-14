# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "TikTok Shop Connector (Smart)",
    'summary': "Import TikTok Shop orders and sync deliveries for Odoo Community",
    'description': """
Import your TikTok Shop orders in Odoo Community and synchronize deliveries
===========================================================================
Developed & Customized by Thatsawan

Key Features
------------
* Import orders from multiple TikTok Shop accounts and seller stores
* Orders are matched with Odoo products based on their SKU or product identifier
* Automated token lifecycle management (OAuth 2.0 Access/Refresh Token)
* Automated inventory synchronization and order delivery tracking
""",
    'category': 'Sales/Sales',
    'sequence': 326,
    'application': True,
    'depends': [
        'sale_management',
        'stock_delivery',
    ],
    'data': [
        'data/tiktok_cron.xml',
        'security/ir.access.csv',
        'views/sale_order_views.xml',
        'views/tiktok_shop_views.xml',
        'views/tiktok_account_views.xml',
        'views/tiktok_item_views.xml',
        'views/tiktok_webhook_event_views.xml',
        'views/stock_picking_views.xml',
        'views/menus.xml',
    ],
    'author': 'Thatsawan',
    'license': 'LGPL-3',
}
