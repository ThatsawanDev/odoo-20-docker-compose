from . import models


def post_init_hook(env):
    """Link existing sale orders to the seeded channel configuration."""
    env.cr.execute("""
        UPDATE sale_order AS so
           SET hub_channel_id = ch.id
          FROM thai_sales_stock_channel AS ch
         WHERE so.hub_channel = ch.code
           AND so.hub_channel_id IS NULL
    """)
    enabled = env["ir.config_parameter"].sudo().get_bool(
        "thai_sales_stock_hub.marketplace_enabled"
    )
    env["res.config.settings"]._sync_marketplace_visibility(enabled)
