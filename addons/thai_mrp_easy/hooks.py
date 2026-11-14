"""Small, clearly labelled guide records installed with Thai MRP Easy."""


def ensure_sample_bom(env):
    Product = env["product.template"].sudo()
    Bom = env["mrp.bom"].sudo()
    examples = (
        ("THAI-MRP-GUIDE-DESK", "[ตัวอย่าง] ชุดโต๊ะทำงาน"),
        ("THAI-MRP-GUIDE-TOP", "[ตัวอย่าง] แผ่นหน้าโต๊ะ"),
        ("THAI-MRP-GUIDE-LEG", "[ตัวอย่าง] ขาโต๊ะ"),
    )
    products = {}
    for code, name in examples:
        product = Product.search([("default_code", "=", code)], limit=1)
        if not product:
            product = Product.create({
                "name": name,
                "default_code": code,
                "type": "consu",
                "is_storable": True,
                "sale_ok": False,
                "purchase_ok": False,
                "company_id": False,
            })
        products[code] = product

    bom = Bom.search([("code", "=", "THAI-MRP-GUIDE-BOM")], limit=1)
    if not bom:
        finished = products["THAI-MRP-GUIDE-DESK"]
        top = products["THAI-MRP-GUIDE-TOP"].product_variant_id
        leg = products["THAI-MRP-GUIDE-LEG"].product_variant_id
        bom = Bom.create({
            "code": "THAI-MRP-GUIDE-BOM",
            "product_tmpl_id": finished.id,
            "product_qty": 1,
            "uom_id": finished.uom_id.id,
            "type": "normal",
            "company_id": False,
            "note": "<p><b>ตัวอย่างสำหรับทดลองใช้งาน</b></p>"
                    "<p>ผลิตชุดโต๊ะทำงาน 1 ชุด โดยใช้แผ่นหน้าโต๊ะ 1 แผ่นและขาโต๊ะ 4 ขา "
                    "เลือกสินค้านี้ในใบงานผลิตเพื่อดูการคำนวณวัตถุดิบ</p>",
            "bom_line_ids": [
                (0, 0, {"product_id": top.id, "product_qty": 1, "uom_id": top.uom_id.id}),
                (0, 0, {"product_id": leg.id, "product_qty": 4, "uom_id": leg.uom_id.id}),
            ],
        })
    # A small multilevel chair example makes the visual tree useful immediately.
    chair_parts = (
        ("THAI-MRP-CHAIR", "[ตัวอย่าง] เก้าอี้สำเร็จรูป"),
        ("THAI-MRP-SEAT", "[ตัวอย่าง] เบาะนั่ง"),
        ("THAI-MRP-BACK", "[ตัวอย่าง] พนักพิง"),
        ("THAI-MRP-FRONT", "[ตัวอย่าง] ขาหน้า"),
        ("THAI-MRP-CROSS", "[ตัวอย่าง] คานขวาง"),
        ("THAI-MRP-RAIL", "[ตัวอย่าง] รางด้านข้าง"),
        ("THAI-MRP-WOOD", "[ตัวอย่าง] แผ่นไม้"),
        ("THAI-MRP-SCREW", "[ตัวอย่าง] สกรู"),
    )
    for code, name in chair_parts:
        product = Product.search([("default_code", "=", code)], limit=1)
        if not product:
            product = Product.create({
                "name": name, "default_code": code, "type": "consu",
                "is_storable": True, "sale_ok": False, "purchase_ok": False,
                "company_id": False,
            })
        products[code] = product

    chair_boms = (
        ("THAI-MRP-BOM-FRONT", "THAI-MRP-FRONT", (("THAI-MRP-WOOD", 1), ("THAI-MRP-SCREW", 2))),
        ("THAI-MRP-BOM-CROSS", "THAI-MRP-CROSS", (("THAI-MRP-WOOD", 1),)),
        ("THAI-MRP-BOM-BACK", "THAI-MRP-BACK", (("THAI-MRP-CROSS", 2), ("THAI-MRP-RAIL", 2))),
        ("THAI-MRP-BOM-SEAT", "THAI-MRP-SEAT", (("THAI-MRP-WOOD", 1),)),
        ("THAI-MRP-BOM-CHAIR", "THAI-MRP-CHAIR", (("THAI-MRP-FRONT", 2), ("THAI-MRP-BACK", 1), ("THAI-MRP-SEAT", 1))),
    )
    for code, finished_code, components in chair_boms:
        if Bom.search([("code", "=", code)], limit=1):
            continue
        finished = products[finished_code]
        Bom.create({
            "code": code, "product_tmpl_id": finished.id,
            "product_qty": 1, "uom_id": finished.uom_id.id,
            "type": "normal", "company_id": False,
            "note": "<p>ตัวอย่างสำหรับเรียนรู้ BOM แบบหลายระดับ</p>",
            "bom_line_ids": [(0, 0, {
                "product_id": products[part_code].product_variant_id.id,
                "product_qty": qty,
                "uom_id": products[part_code].uom_id.id,
            }) for part_code, qty in components],
        })
    return bom


def post_init_hook(env):
    ensure_sample_bom(env)
