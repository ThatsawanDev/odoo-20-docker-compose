"""Idempotent TBF Furniture demo data for `odoo shell -d odoo_erp20`."""

tag = "TBF-DEMO"
company = env.company


def one(model, domain, values):
    rec = env[model].search(domain, limit=1)
    if not rec:
        rec = env[model].create(values)
    return rec


category = one("product.category", [("name", "=", "TBF-DEMO Furniture")], {"name": "TBF-DEMO Furniture"})
warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
assert warehouse, "No warehouse in current company"
stock = warehouse.lot_stock_id
for name in ("TBF-DEMO Showroom", "TBF-DEMO Bulk Storage", "TBF-DEMO Awaiting to Sell"):
    one("stock.location", [("name", "=", name), ("location_id", "=", stock.id)],
        {"name": name, "location_id": stock.id, "usage": "internal", "company_id": company.id})

catalog = [
    ("TBF-DM-CHAIR", "เก้าอี้ทานอาหารไม้โอ๊ค", 2590, 2, 0.18, 1250, 36),
    ("TBF-DM-TABLE", "โต๊ะอาหารไม้โอ๊ค 4 ที่นั่ง", 8990, 24, 0.62, 4700, 14),
    ("TBF-DM-SOFA", "โซฟาผ้า 3 ที่นั่ง สีเทา", 16900, 48, 1.45, 9300, 9),
    ("TBF-DM-CABINET", "ตู้เก็บของไม้ 2 บาน", 7290, 31, 0.78, 3900, 11),
    ("TBF-DM-SEAT", "เบาะเก้าอี้ทานอาหาร สีครีม", 590, 0.7, 0.025, 210, 52),
    ("TBF-DM-SEAT-ALT", "เบาะเก้าอี้ทานอาหาร สีเทา (ทดแทน)", 590, 0.7, 0.025, 210, 28),
]
products = {}
for code, name, price, weight, volume, cost, qty in catalog:
    vals = {"name": f"{tag} {name}", "default_code": code, "categ_id": category.id,
            "type": "consu", "is_storable": True, "list_price": price,
            "standard_price": cost, "weight": weight, "volume": volume}
    tmpl = one("product.template", [("default_code", "=", code)], vals)
    products[code] = tmpl.product_variant_id

bundle = one("product.template", [("default_code", "=", "TBF-DM-SET4")],
    {"name": f"{tag} ชุดโต๊ะอาหาร 4 ที่นั่ง", "default_code": "TBF-DM-SET4",
     "categ_id": category.id, "type": "consu", "is_storable": True,
     "list_price": 17900, "weight": 32, "volume": 1.34})
products["TBF-DM-SET4"] = bundle.product_variant_id
bom = one("mrp.bom", [("product_tmpl_id", "=", bundle.id), ("type", "=", "phantom")],
    {"product_tmpl_id": bundle.id, "product_qty": 1, "type": "phantom", "code": "TBF-DEMO-SET4"})
for code, qty in (("TBF-DM-TABLE", 1), ("TBF-DM-CHAIR", 4), ("TBF-DM-SEAT", 4)):
    one("mrp.bom.line", [("bom_id", "=", bom.id), ("product_id", "=", products[code].id)],
        {"bom_id": bom.id, "product_id": products[code].id, "product_qty": qty})

pricelists = {}
for name, factor in (("Retail", 1), ("Wholesale", .85), ("Government", .92)):
    pl = one("product.pricelist", [("name", "=", f"{tag} {name}")],
             {"name": f"{tag} {name}", "currency_id": company.currency_id.id, "company_id": company.id})
    pricelists[name] = pl
    for code, product in products.items():
        one("product.pricelist.item", [("pricelist_id", "=", pl.id), ("product_tmpl_id", "=", product.product_tmpl_id.id)],
            {"pricelist_id": pl.id, "applied_on": "1_product", "product_tmpl_id": product.product_tmpl_id.id,
             "compute_price": "fixed", "fixed_price": round(product.lst_price * factor, 2)})

customers = {}
for key, name in (("Retail", "ลูกค้าหน้าร้านตัวอย่าง"),
                  ("Wholesale", "ร้านเฟอร์นิเจอร์ตัวแทนจำหน่ายตัวอย่าง"),
                  ("Government", "หน่วยงานภาครัฐตัวอย่าง")):
    p = one("res.partner", [("ref", "=", f"TBF-DEMO-{key.upper()}")],
        {"name": f"{tag} {name}", "ref": f"TBF-DEMO-{key.upper()}",
         "customer_rank": 1, "is_company": True, "property_product_pricelist": pricelists[key].id})
    customers[key] = p

for key, lines in (("Retail", [("TBF-DM-SOFA", 1), ("TBF-DM-CABINET", 1)]),
                   ("Wholesale", [("TBF-DM-SET4", 3), ("TBF-DM-SOFA", 2)]),
                   ("Government", [("TBF-DM-TABLE", 2), ("TBF-DM-CHAIR", 8)])):
    ref = f"TBF-DEMO-SO-{key.upper()}"
    if not env["sale.order"].search([("client_order_ref", "=", ref)], limit=1):
        env["sale.order"].create({"partner_id": customers[key].id, "pricelist_id": pricelists[key].id,
            "warehouse_id": warehouse.id, "client_order_ref": ref,
            "note": "ข้อมูลตัวอย่าง TBF Furniture สำหรับสาธิตระบบ",
            "order_line": [(0, 0, {"product_id": products[code].id, "product_uom_qty": qty}) for code, qty in lines]})

showroom = env["stock.location"].search([("name", "=", "TBF-DEMO Showroom")], limit=1)
bulk = env["stock.location"].search([("name", "=", "TBF-DEMO Bulk Storage")], limit=1)
for code, _name, _price, _weight, _volume, _cost, qty in catalog:
    product = products[code]
    for location, amount in ((showroom, max(1, qty // 4)), (bulk, qty - max(1, qty // 4))):
        quants = env["stock.quant"].search([("product_id", "=", product.id), ("location_id", "=", location.id)])
        if not quants and amount:
            quant = env["stock.quant"].create({"product_id": product.id, "location_id": location.id,
                "inventory_quantity": amount})
            quant.action_apply_inventory()

env.cr.commit()
print("TBF-DEMO complete: products=7, customers=3, pricelists=3, sales=3, BOM=1, locations=3")
