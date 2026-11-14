"""Run inside `odoo shell -d thai_sales_stock` to add clearly marked demo quotations.

This file is intentionally outside the manifest: installing the module never creates
sample business records in another database.
"""

from datetime import timedelta

from odoo import fields


def seed(env):
    sale = env["sale.order"]
    partners = env["res.partner"]
    curry = env.ref("thai_sales_stock_easy.product_sour_curry_pouch")
    dog_food = env.ref("thai_sales_stock_easy.product_az_dog_food")
    northern = env.ref("thai_sales_stock_easy.partner_customer_northern_food")
    grandma = env.ref("thai_sales_stock_easy.partner_customer_grandma_kitchen")

    demo_customers = [
        ("[ตัวอย่าง] คุณณัฐพล ใจดี", "081-234-0101", "เชียงใหม่"),
        ("[ตัวอย่าง] คุณศิริพร แก้วใส", "081-234-0102", "กรุงเทพมหานคร"),
        ("[ตัวอย่าง] ร้านเพื่อนสัตว์เลี้ยง", "081-234-0103", "ลำพูน"),
    ]
    created_customers = []
    for name, phone, city in demo_customers:
        partner = partners.search([("name", "=", name)], limit=1)
        if not partner:
            partner = partners.create({"name": name, "phone": phone, "city": city,
                                       "country_id": env.ref("base.th").id,
                                       "customer_rank": 1})
        created_customers.append(partner)

    examples = [
        ("DEMO-SP-001", "shopee", created_customers[0], [(curry, 2), (dog_food, 1)]),
        ("DEMO-LA-001", "lazada", created_customers[1], [(dog_food, 1)]),
        ("DEMO-TT-001", "tiktok", created_customers[2], [(curry, 4)]),
        ("DEMO-WEB-001", "website", grandma, [(curry, 3), (dog_food, 1)]),
        ("DEMO-POS-001", "store", created_customers[0], [(curry, 1)]),
        ("DEMO-DIRECT-001", "direct", northern, [(dog_food, 2)]),
    ]
    created = 0
    for index, (reference, channel, partner, products) in enumerate(examples):
        if sale.search_count([("hub_external_ref", "=", reference), ("hub_is_demo", "=", True)]):
            continue
        lines = [(0, 0, {"product_id": product.id, "product_uom_qty": quantity,
                         "product_uom_id": product.uom_id.id, "price_unit": product.lst_price})
                 for product, quantity in products]
        sale.create({"partner_id": partner.id, "hub_channel": channel,
                     "hub_external_ref": reference, "hub_is_demo": True,
                     "date_order": fields.Datetime.now() - timedelta(minutes=index * 7),
                     "order_line": lines})
        created += 1
    return created


print("DEMO_ORDERS_CREATED", seed(env))
env.cr.commit()
