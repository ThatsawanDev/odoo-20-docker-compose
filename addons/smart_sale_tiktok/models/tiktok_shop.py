# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import secrets
from datetime import datetime, timedelta
from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.smart_sale_tiktok import utils

_logger = logging.getLogger(__name__)


class TikTokShop(models.Model):
    _name = 'tiktok.shop'
    _description = "TikTok Shop Seller Store"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string="Store Name", required=True, tracking=True)
    account_id = fields.Many2one('tiktok.account', string="Developer Account", required=True, ondelete='cascade')
    shop_identifier = fields.Char(string="Open Shop ID", help="Unique identifier assigned by TikTok Open API", copy=False)
    shop_cipher = fields.Char(string="Shop Cipher", help="Encrypted identifier used in API headers and queries", copy=False)

    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse", domain="[('company_id', '=', company_id)]")
    team_id = fields.Many2one('crm.team', string="Sales Team")
    
    # OAuth Tokens
    access_token = fields.Char(string="Access Token", copy=False, groups="base.group_system")
    refresh_token = fields.Char(string="Refresh Token", copy=False, groups="base.group_system")
    access_token_expiration_date = fields.Datetime(string="Token Expiration Date", copy=False)
    refresh_token_expiration_date = fields.Datetime(string="Refresh Expiration Date", copy=False)
    oauth_state = fields.Char(copy=False, groups="base.group_system")

    # Sync Configuration & Timestamps
    state = fields.Selection([
        ('draft', "Unauthorized"),
        ('active', "Active"),
        ('error', "Authentication Error"),
        ('inactive', "Inactive")
    ], string="Status", default='draft', tracking=True)
    
    sync_orders = fields.Boolean(string="Sync Orders", default=True, help="Automatically fetch and import new TikTok orders")
    sync_inventory = fields.Boolean(string="Sync Inventory", default=True, help="Automatically push stock level updates to TikTok")
    
    last_orders_sync_date = fields.Datetime(string="Last Orders Sync", copy=False)
    last_inventory_sync_date = fields.Datetime(string="Last Inventory Sync", copy=False)
    webhook_url = fields.Char(compute='_compute_webhook_url')

    item_ids = fields.One2many('tiktok.item', 'shop_id', string="Mapped Items")
    order_ids = fields.One2many('sale.order', 'tiktok_shop_id', string="Imported Orders")

    def _compute_webhook_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_str('web.base.url', '')
        for shop in self:
            shop.webhook_url = f"{base_url.rstrip('/')}/smart_sale_tiktok/webhook"

    def action_authorize(self):
        """Initiate OAuth authorization handshake for this shop."""
        self.ensure_one()
        self.oauth_state = secrets.token_urlsafe(32)
        url = (
            f"{utils.const.AUTH_URL}?service_id={self.account_id.app_key}"
            f"&state={self.oauth_state}"
        )
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': '_new',
        }

    def action_request_token(self):
        """Manually trigger access token generation if authorization code is supplied via wizard or context."""
        self.ensure_one()
        try:
            utils.request_access_token(self)
            self.state = 'active'
        except Exception as e:
            self.state = 'error'
            raise e

    def action_sync_orders_now(self):
        """Manual action to pull newest orders immediately."""
        self.ensure_one()
        self._sync_orders()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_sync_inventory_now(self):
        self.ensure_one()
        self.item_ids._sync_inventory()
        self.last_inventory_sync_date = fields.Datetime.now()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _sync_orders(self):
        """Core engine method to fetch order list and import as Odoo sale.order records."""
        for shop in self.filtered(lambda s: s.state == 'active' and s.sync_orders):
            _logger.info("Syncing TikTok orders for shop: %s", shop.name)
            try:
                since = shop.last_orders_sync_date or (fields.Datetime.now() - timedelta(days=7))
                params = {
                    'page_size': utils.const.ORDER_LIST_SIZE_LIMIT,
                }
                body = {
                    'create_time_ge': int(since.timestamp()),
                    'create_time_lt': int(fields.Datetime.now().timestamp()),
                }
                page_token = False
                while True:
                    page_params = dict(params)
                    if page_token:
                        page_params['page_token'] = page_token
                    res = utils.make_tiktok_api_request(
                        shop, 'search_orders', params=page_params, body=body,
                    )
                    for order_data in res.get('orders', []):
                        shop._import_single_order(shop, order_data)
                    page_token = res.get('next_page_token')
                    if not page_token:
                        break
                shop.last_orders_sync_date = fields.Datetime.now()
            except Exception as e:
                _logger.error("Error syncing TikTok orders for shop %s: %s", shop.name, str(e))

    def _import_single_order(self, shop, order_data):
        """Create or update sale.order from TikTok order dictionary."""
        order_sn = order_data.get('order_id')
        if not order_sn:
            return self.env['sale.order']
        order_sn = str(order_sn)
        existing = self.env['sale.order'].search([
            ('tiktok_order_id', '=', order_sn),
            ('company_id', '=', shop.company_id.id),
        ], limit=1)
        status = order_data.get('status') or order_data.get('order_status')
        package = next(iter(order_data.get('packages') or []), {})
        common_values = {
            'tiktok_order_status': status,
            'tiktok_package_id': package.get('id') or order_data.get('package_id'),
            'tiktok_delivery_option': (
                order_data.get('delivery_option_name')
                or order_data.get('delivery_option')
            ),
            'tiktok_last_update': fields.Datetime.now(),
        }
        if existing:
            existing.write(common_values)
            existing._apply_tiktok_status()
            return existing

        _logger.info("Importing new TikTok order: %s", order_sn)
        partner = self.env['res.partner']._get_or_create_tiktok_partner(shop, order_data)
        currency_code = (
            order_data.get('payment', {}).get('currency')
            or order_data.get('currency')
            or shop.company_id.currency_id.name
        )
        currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
        order_lines = []
        for line_data in order_data.get('line_items', []):
            line_values = shop._prepare_order_line(line_data, currency)
            if line_values:
                order_lines.append(Command.create(line_values))
        warehouse = shop.warehouse_id or self.env['stock.warehouse'].search([
            ('company_id', '=', shop.company_id.id),
        ], limit=1)
        order = self.env['sale.order'].with_company(shop.company_id).create({
                'name': f"TT-{order_sn}",
                'tiktok_order_id': order_sn,
                'tiktok_shop_id': shop.id,
                'partner_id': partner.id,
                'company_id': shop.company_id.id,
                'warehouse_id': warehouse.id,
                'team_id': shop.team_id.id,
                'currency_id': currency.id or shop.company_id.currency_id.id,
                'order_line': order_lines,
                'state': 'draft',
                **common_values,
            })
        order._apply_tiktok_status()
        return order

    def _prepare_order_line(self, line_data, currency):
        seller_sku = line_data.get('seller_sku') or line_data.get('sku_name')
        sku_id = str(line_data.get('sku_id') or '')
        item = self.env['tiktok.item'].search([
            ('shop_id', '=', self.id), ('tiktok_sku_id', '=', sku_id),
        ], limit=1)
        product = item.product_id
        if not product and seller_sku:
            product = self.env['product.product'].search([
                ('default_code', '=', seller_sku),
                ('company_id', 'in', [self.company_id.id, False]),
            ], limit=1)
        if not product:
            _logger.warning(
                "TikTok line %s skipped: no Odoo product for seller SKU %s",
                line_data.get('id'), seller_sku,
            )
            return False
        if not item and sku_id:
            item = self.env['tiktok.item'].create({
                'name': line_data.get('product_name') or product.display_name,
                'shop_id': self.id,
                'tiktok_product_id': str(line_data.get('product_id') or ''),
                'tiktok_sku_id': sku_id,
                'product_id': product.id,
            })
        quantity = float(line_data.get('quantity') or 1)
        amount = (
            line_data.get('sale_price')
            or line_data.get('original_price')
            or line_data.get('sku_sale_price')
            or {}
        )
        if isinstance(amount, dict):
            amount = amount.get('amount') or 0
        return {
            'product_id': product.id,
            'name': line_data.get('product_name') or product.display_name,
            'product_uom_qty': quantity,
            'price_unit': float(amount or 0),
            'tiktok_order_item_id': str(line_data.get('id') or ''),
            'tiktok_sku_id': sku_id,
            'tiktok_seller_sku': seller_sku,
        }

    @api.model
    def _cron_sync_tiktok_orders(self):
        """Cron endpoint for automated periodic order importation."""
        shops = self.search([('state', '=', 'active'), ('sync_orders', '=', True)])
        shops._sync_orders()

    @api.model
    def _cron_sync_tiktok_inventory(self):
        """Cron endpoint for automated sellable inventory updates."""
        shops = self.search([('state', '=', 'active'), ('sync_inventory', '=', True)])
        for shop in shops:
            _logger.info("Running scheduled inventory sync for shop: %s", shop.name)
            try:
                shop.item_ids._sync_inventory()
                shop.last_inventory_sync_date = fields.Datetime.now()
            except Exception:
                _logger.exception("TikTok inventory sync failed for %s", shop.display_name)
