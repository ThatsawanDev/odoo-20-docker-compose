from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    hub_shopee_enabled = fields.Boolean(string="เปิดใช้ Shopee")
    hub_lazada_enabled = fields.Boolean(string="เปิดใช้ Lazada")
    hub_tiktok_enabled = fields.Boolean(string="เปิดใช้ TikTok Shop")


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    hub_marketplace_enabled = fields.Boolean(
        string="เปิดใช้งาน Marketplace",
        config_parameter="thai_sales_stock_hub.marketplace_enabled",
    )
    hub_shopee_enabled = fields.Boolean(related="company_id.hub_shopee_enabled", readonly=False)
    hub_lazada_enabled = fields.Boolean(related="company_id.hub_lazada_enabled", readonly=False)
    hub_tiktok_enabled = fields.Boolean(related="company_id.hub_tiktok_enabled", readonly=False)

    def _sync_marketplace_visibility(self, enabled):
        """Keep the menu and connector jobs in step with the single switch."""
        menu = self.env.ref("thai_sales_stock_hub.menu_hub", raise_if_not_found=False)
        if menu:
            menu.active = enabled
        cron_ids = (
            "sale_shopee.ir_cron_sync_shopee_orders",
            "sale_shopee.ir_cron_sync_shopee_pickings",
            "sale_shopee.ir_cron_sync_shopee_inventory",
            "sale_shopee.ir_cron_sync_shopee_pickings_retry",
            "sale_lazada.ir_cron_sync_lazada_orders",
            "sale_lazada.ir_cron_sync_lazada_inventory",
            "smart_sale_tiktok.ir_cron_sync_tiktok_orders",
            "smart_sale_tiktok.ir_cron_sync_tiktok_inventory",
            "smart_sale_tiktok.ir_cron_retry_tiktok_webhooks",
        )
        for xmlid in cron_ids:
            cron = self.env.ref(xmlid, raise_if_not_found=False)
            if cron:
                cron.active = enabled

    def set_values(self):
        super().set_values()
        self._sync_marketplace_visibility(bool(self.hub_marketplace_enabled))
