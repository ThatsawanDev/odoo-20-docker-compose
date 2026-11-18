from markupsafe import Markup, escape

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    tbf_show_catalog_images = fields.Boolean(
        string='แนบแคตตาล็อกรูปสินค้าในใบเสนอราคา', default=True,
    )
    tbf_catalog_html = fields.Html(
        string='แคตตาล็อกรูปสินค้า', compute='_compute_tbf_catalog_html',
        sanitize=False,
    )

    @api.depends(
        'order_line.product_id',
        'order_line.product_uom_qty',
        'order_line.price_unit',
        'tbf_show_catalog_images',
    )
    def _compute_tbf_catalog_html(self):
        for order in self:
            if not order.tbf_show_catalog_images:
                order.tbf_catalog_html = Markup(
                    '<div style="padding:16px;border:1px dashed #cbd5e1;border-radius:10px;color:#64748b">'
                    'ปิดการแนบแคตตาล็อกรูปสินค้าในใบเสนอราคา (เปิดสวิตช์ด้านบนเพื่อแสดงรูปสินค้าหลายมุมมอง)'
                    '</div>'
                )
                continue
            cards = []
            seen = set()
            for line in order.order_line.filtered(lambda item: item.product_id and not item.display_type):
                product = line.product_id
                template = product.product_tmpl_id
                if template.id in seen:
                    continue
                seen.add(template.id)
                photos = []
                if template.image_1920:
                    photos.append((
                        f'/web/image/product.template/{template.id}/image_512',
                        'รูปหลัก (มุมตรง)',
                    ))
                for extra in template.thai_image_ids.sorted('sequence'):
                    photos.append((
                        f'/web/image/thai.product.image/{extra.id}/image_1920',
                        extra.name or 'มุมเพิ่มเติม',
                    ))
                if not photos:
                    continue
                code_badge = (
                    f'<span style="display:inline-block;padding:2px 8px;border-radius:6px;'
                    f'background:#eff6ff;color:#1d4ed8;font-size:12px;font-weight:700;margin-right:8px">'
                    f'{escape(product.default_code)}</span>'
                    if product.default_code else ''
                )
                price_text = f'{line.price_unit:,.2f} ฿'
                qty_text = f'{line.product_uom_qty:g} {line.product_uom_id.name or ""}'
                photo_count_badge = (
                    f'<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
                    f'background:#f1f5f9;color:#475569;font-size:12px;font-weight:600">'
                    f'{len(photos)} มุมมอง</span>'
                )
                images = ''.join(
                    f'<div style="flex:0 0 210px;border:1px solid #e2e8f0;border-radius:10px;'
                    f'padding:10px;background:#ffffff;text-align:center">'
                    f'<img src="{url}" alt="{escape(label)}" '
                    f'style="width:100%;height:155px;object-fit:contain;border-radius:6px;background:#f8fafc"/>'
                    f'<div style="margin-top:8px;font-size:12.5px;font-weight:600;color:#334155">'
                    f'{escape(label)}</div>'
                    f'</div>'
                    for url, label in photos
                )
                cards.append(
                    f'<section style="margin:0 0 18px;padding:16px;border:1px solid #dbe4f0;'
                    f'border-radius:12px;background:#f8fafc">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'flex-wrap:wrap;gap:8px;margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid #e2e8f0">'
                    f'<div>{code_badge}<strong style="font-size:15px;color:#0f172a">{escape(template.display_name)}</strong></div>'
                    f'<div style="display:flex;align-items:center;gap:10px">'
                    f'<span style="font-size:13px;color:#475569">จำนวน: <b>{escape(qty_text)}</b> | ราคา: <b>{escape(price_text)}</b></span>'
                    f'{photo_count_badge}'
                    f'</div>'
                    f'</div>'
                    f'<div style="display:flex;flex-wrap:wrap;gap:12px">{images}</div>'
                    f'</section>'
                )
            order.tbf_catalog_html = Markup(
                ''.join(cards)
                or '<div style="padding:16px;color:#64748b">สินค้าในใบเสนอราคายังไม่มีรูป กรุณาเพิ่มรูปที่หน้าสินค้า (แท็บรูปสินค้าเพิ่มเติม)</div>'
            )
