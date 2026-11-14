"""Seed clearly labelled, playable packing video examples for thai_sales_stock.

Run inside Odoo shell: exec(open(__file__).read()); seed(env, video_path)
"""

import base64
from datetime import timedelta

from odoo import fields


def seed(env, video_path):
    video_bytes = open(video_path, "rb").read()
    if not video_bytes.startswith(b"\x1a\x45\xdf\xa3"):
        raise ValueError("Expected a WebM video")
    video_data = base64.b64encode(video_bytes).decode()
    sources = [
        ("shopee", "DEMO-PACK-SP-001"),
        ("lazada", "DEMO-PACK-LA-001"),
        ("tiktok", "DEMO-PACK-TT-001"),
        ("website", "DEMO-PACK-WEB-001"),
        ("store", "DEMO-PACK-POS-001"),
    ]
    Sale = env["sale.order"]
    Video = env["thai.sales.stock.packing.video"]
    Scan = env["thai.sales.stock.packing.scan"]
    station = env["thai.sales.stock.packing.station"].search([], limit=1)
    if not station:
        raise ValueError("Create a packing station before seeding videos")
    created = []
    for index, (channel, external_ref) in enumerate(sources):
        order = Sale.search([("hub_external_ref", "=", external_ref), ("hub_is_demo", "=", True)], limit=1)
        if not order:
            source = Sale.search([("hub_is_demo", "=", True), ("hub_channel", "=", channel),
                                  ("state", "in", ("draft", "sent"))], limit=1)
            if not source:
                raise ValueError(f"Missing demo sale order for {channel}")
            order = source.copy({"hub_is_demo": True, "hub_external_ref": external_ref,
                                 "client_order_ref": f"[ตัวอย่าง] {external_ref}"})
        if order.state in ("draft", "sent"):
            order.action_confirm()
        picking = order.picking_ids.filtered(lambda p: p.picking_type_code == "outgoing" and p.state != "cancel")[:1]
        if not picking:
            raise ValueError(f"No outgoing picking for {external_ref}")
        if Video.search_count([("picking_id", "=", picking.id), ("is_demo", "=", True)]):
            continue
        recorded_at = fields.Datetime.now() - timedelta(minutes=15 * index)
        required = picking._hub_required_products()
        for product_id, quantity in required.items():
            Scan.create({"picking_id": picking.id, "product_id": product_id, "qty_scanned": quantity})
        attachment = env["ir.attachment"].create({
            "name": f"DEMO-{channel}-{picking.name.replace('/', '-')}.webm",
            "res_model": "stock.picking", "res_id": picking.id,
            "type": "binary", "datas": video_data, "mimetype": "video/webm",
        })
        picking.write({"hub_packing_state": "packed", "hub_packing_station_id": station.id,
                       "hub_packer_id": env.user.id, "hub_packed_at": recorded_at,
                       "hub_pack_video_id": attachment.id})
        Video.create({"name": attachment.name, "picking_id": picking.id, "attachment_id": attachment.id,
                      "recorded_at": recorded_at, "packer_id": env.user.id, "station_id": station.id})
        created.append((order.name, picking.name, channel))
    return created
