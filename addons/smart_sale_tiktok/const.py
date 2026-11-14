# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""TikTok Shop Open API integration constants.

Contains API endpoints, operation mappings, status mappings, and API limits.
"""

AUTH_URL = 'https://services.tiktokshop.com/open/authorize'

# API Paths by region
API_ENDPOINTS = {
    'SEA': 'https://open-api.tiktokglobalshop.com',
    'US': 'https://open-api.tiktokglobalshop.com',
    'UK': 'https://open-api.tiktokglobalshop.com',
    'GLOBAL': 'https://open-api.tiktokglobalshop.com',
}

# Mapping of TikTok Shop API operations to their URL path, HTTP method, and API type
API_OPERATIONS_MAPPING = {
    'get_token': {'url_path': '/api/v2/token/get', 'api_type': 'public'},
    'refresh_token': {'url_path': '/api/v2/token/refresh', 'api_type': 'public'},
    'get_authorized_shops': {
        'url_path': '/authorization/202309/shops', 'api_type': 'shop', 'method': 'GET',
    },
    'search_orders': {
        'url_path': '/order/202309/orders/search', 'api_type': 'order', 'method': 'POST',
    },
    'get_order_detail': {
        'url_path': '/order/202309/orders/{order_id}', 'api_type': 'order', 'method': 'GET',
    },
    'get_shipping_providers': {
        'url_path': '/fulfillment/202309/shipping_providers',
        'api_type': 'logistics',
        'method': 'GET',
    },
    'ship_package': {
        'url_path': '/fulfillment/202309/packages/{package_id}/ship',
        'api_type': 'logistics',
        'method': 'POST',
    },
    'get_shipping_document': {
        'url_path': '/fulfillment/202309/packages/{package_id}/shipping_documents',
        'api_type': 'logistics',
        'method': 'GET',
    },
    'search_products': {
        'url_path': '/product/202309/products/search', 'api_type': 'product', 'method': 'POST',
    },
    'update_stock': {
        'url_path': '/product/202309/products/{product_id}/inventory/update',
        'api_type': 'product',
        'method': 'POST',
    },
}

# Mapping of TikTok order statuses to Odoo picking statuses
ORDER_STATUS_MAPPING = {
    'UNPAID': 'draft',
    'AWAITING_SHIPMENT': 'confirmed',
    'AWAITING_COLLECTION': 'processing',
    'IN_TRANSIT': 'processing',
    'DELIVERED': 'delivered',
    'COMPLETED': 'delivered',
    'CANCEL': 'canceled',
    'CANCELLED': 'canceled',
}

# Mapping of TikTok shop statuses
SHOP_STATUS_MAPPING = {
    'ACTIVE': 'active',
    'INACTIVE': 'inactive',
    'FROZEN': 'error',
}

# API rate limits & batch thresholds
ACCESS_TOKEN_EXPIRATION_THRESHOLD = 5
ORDER_LIST_DAYS_LIMIT = 15
ORDER_LIST_SIZE_LIMIT = 50
ORDER_DETAIL_SIZE_LIMIT = 50
SYNC_INVENTORY_SIZE_LIMIT = 50
MAX_API_RETRIES = 3
