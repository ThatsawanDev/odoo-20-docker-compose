import re
from html import unescape
from odoo import api, models
from odoo.tools.image import image_data_uri


DOCUMENT_CONFIG = {
    'quotation': {
        'title_th': 'ใบเสนอราคา',
        'title_en': 'Quotation',
        'date_label': 'วันที่เสนอราคา / Date',
        'ref_label': 'ยืนราคา / Validity',
        'partner_label': 'เรียน / To',
        'intro_th': 'บริษัทฯ มีความยินดีเสนอราคาสินค้าและบริการ ตามรายละเอียดดังนี้',
        'intro_en': 'We are pleased to submit the following quotation for your consideration.',
        'signature_label': 'ลูกค้า / ผู้อนุมัติ',
        'default_remarks': [
            'ราคานี้รวมภาษีมูลค่าเพิ่มแล้ว',
            'ยืนราคา 30 วัน นับจากวันที่เสนอราคา',
            'เงื่อนไขการชำระเงิน ตามที่ตกลงร่วมกัน',
        ],
    },
    'sales_order': {
        'title_th': 'ใบสั่งขาย',
        'title_en': 'Sales Order',
        'date_label': 'วันที่สั่งขาย / Date',
        'ref_label': 'อ้างอิง / Reference',
        'partner_label': 'เรียน / To',
        'intro_th': 'บริษัทฯ ขอขอบคุณที่ไว้วางใจสั่งซื้อสินค้าและบริการ ตามรายละเอียดดังนี้',
        'intro_en': 'Thank you for your order. Please find the sales order details below.',
        'signature_label': 'ผู้สั่งซื้อ / ผู้อนุมัติ',
        'default_remarks': [
            'โปรดตรวจสอบรายการสินค้าและเงื่อนไขการสั่งซื้อให้ถูกต้อง',
            'กำหนดส่งมอบสินค้าตามที่ตกลงร่วมกัน',
            'เงื่อนไขการชำระเงิน ตามที่ตกลงร่วมกัน',
        ],
    },
    'purchase_order': {
        'title_th': 'ใบสั่งซื้อ',
        'title_en': 'Purchase Order',
        'date_label': 'วันที่สั่งซื้อ / Date',
        'ref_label': 'กำหนดรับของ / Delivery',
        'partner_label': 'ผู้ขาย / Vendor',
        'intro_th': 'บริษัทฯ มีความประสงค์ขอสั่งซื้อสินค้าและบริการ ตามรายละเอียดดังนี้',
        'intro_en': 'We would like to place a purchase order for the following items.',
        'signature_label': 'ผู้สั่งซื้อ / ผู้อนุมัติ',
        'default_remarks': [
            'โปรดระบุเลขที่ใบสั่งซื้อในใบส่งของและใบแจ้งหนี้ทุกครั้ง',
            'ส่งมอบสินค้าตามกำหนดเวลาและสถานที่ที่ระบุ',
            'เงื่อนไขการชำระเงิน ตามที่ตกลงร่วมกัน',
        ],
    },
    'delivery_note': {
        'title_th': 'ใบส่งสินค้า',
        'title_en': 'Delivery Note',
        'date_label': 'วันที่ส่งสินค้า / Date',
        'ref_label': 'เอกสารอ้างอิง / Ref.',
        'partner_label': 'เรียน / To',
        'intro_th': 'บริษัทฯ ขอส่งมอบสินค้าตามรายการด้านล่างนี้ โปรดตรวจสอบความถูกต้อง',
        'intro_en': 'Please find the delivered items listed below and verify upon receipt.',
        'signature_label': 'ผู้รับสินค้า / ผู้ส่งสินค้า',
        'default_remarks': [
            'ได้รับสินค้าตามรายการข้างต้นในสภาพเรียบร้อยถูกต้องแล้ว',
            'กรณีสินค้าชำรุดหรือไม่ถูกต้อง โปรดแจ้งภายใน 7 วัน',
            'เอกสารฉบับนี้อ้างอิงตามรายการจัดส่งของบริษัทฯ',
        ],
    },
    'invoice': {
        'title_th': 'ใบแจ้งหนี้',
        'title_en': 'Invoice',
        'date_label': 'วันที่ใบแจ้งหนี้ / Date',
        'ref_label': 'ครบกำหนด / Due Date',
        'partner_label': 'เรียน / To',
        'intro_th': 'บริษัทฯ ขอแจ้งยอดชำระค่าสินค้าและบริการ ตามรายละเอียดดังนี้',
        'intro_en': 'Please find the invoice details for goods and services below.',
        'signature_label': 'ผู้รับวางบิล / ผู้อนุมัติ',
        'default_remarks': [
            'กรุณาชำระเงินภายในวันครบกำหนดที่ระบุในเอกสาร',
            'หากชำระด้วยเช็ค โปรดขีดคร่อมสั่งจ่ายในนามบริษัทฯ เท่านั้น',
            'ใบเสร็จรับเงินจะสมบูรณ์เมื่อบริษัทฯ ได้รับเงินเรียบร้อยแล้ว',
        ],
    },
    'receipt': {
        'title_th': 'ใบเสร็จรับเงิน',
        'title_en': 'Receipt',
        'date_label': 'วันที่รับเงิน / Date',
        'ref_label': 'อ้างอิง / Reference',
        'partner_label': 'เรียน / To',
        'intro_th': 'บริษัทฯ ได้รับชำระเงินค่าสินค้าและบริการเรียบร้อยแล้ว ตามรายละเอียดดังนี้',
        'intro_en': 'We acknowledge receipt of payment for the following details.',
        'signature_label': 'ผู้รับเงิน / ผู้อนุมัติ',
        'default_remarks': [
            'ใบเสร็จรับเงินฉบับนี้จะสมบูรณ์ต่อเมื่อบริษัทฯ เรียกเก็บเงินตามเช็คหรือเงินโอนได้เรียบร้อยแล้ว',
            'ขอบคุณที่ใช้บริการของบริษัทฯ',
        ],
    },
    'credit_note': {
        'title_th': 'ใบลดหนี้',
        'title_en': 'Credit Note',
        'date_label': 'วันที่ใบลดหนี้ / Date',
        'ref_label': 'อ้างอิงใบแจ้งหนี้ / Ref.',
        'partner_label': 'เรียน / To',
        'intro_th': 'บริษัทฯ ขอออกใบลดหนี้สำหรับรายการสินค้าและบริการ ตามรายละเอียดดังนี้',
        'intro_en': 'Please find the credit note details for your account adjustment below.',
        'signature_label': 'ผู้อนุมัติ / ผู้รับเอกสาร',
        'default_remarks': [
            'เอกสารใบลดหนี้ฉบับนี้ออกเพื่อปรับปรุงรายการตามเอกสารอ้างอิง',
            'โปรดเก็บเอกสารฉบับนี้ไว้เป็นหลักฐานทางบัญชีและภาษี',
        ],
    },
}


def _clean_html_to_lines(raw_html):
    if not raw_html:
        return []
    text = str(raw_html)
    text = re.sub(r'<\s*br\s*/?\s*>', '\n', text, flags=re.I)
    text = re.sub(r'</\s*(p|li|div|tr)\s*>', '\n', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    lines = [line.strip(' \t\r•-*') for line in text.splitlines()]
    return [line for line in lines if line]


def _format_address(partner, fallback=''):
    if not partner:
        return fallback
    parts = [
        partner.street or '',
        partner.street2 or '',
        partner.city or '',
        partner.state_id.name if partner.state_id else '',
        partner.zip or '',
    ]
    joined = ' '.join(p.strip() for p in parts if p and p.strip())
    return joined or fallback


def _get_company_payload(company):
    partner = company.partner_id
    address = _format_address(
        partner,
        fallback='999 ถนนสุขุมวิท แขวงบางนา เขตบางนา กรุงเทพฯ 10260',
    )
    name = company.name or 'Your Company'
    if name in ('My Company', 'Your Company'):
        display_name = 'Your Company'
        sub_name = 'บริษัท ตัวอย่าง จำกัด'
    else:
        display_name = name
        sub_name = company.company_registry or 'สำนักงานใหญ่'

    logo_uri = False
    if company.logo and name not in ('My Company', 'Your Company'):
        try:
            logo_uri = image_data_uri(company.logo)
        except Exception:
            logo_uri = False

    return {
        'name': display_name,
        'sub_name': sub_name,
        'footer_name': sub_name if name in ('My Company', 'Your Company') else display_name,
        'address': address,
        'phone': company.phone or partner.phone or '02-123-4567',
        'email': company.email or partner.email or 'sales@yourcompany.co.th',
        'website': (company.website or partner.website or 'www.yourcompany.co.th').replace('https://', '').replace('http://', '').rstrip('/'),
        'vat': company.vat or partner.vat or '0123456789012',
        'logo_uri': logo_uri,
    }


def _get_partner_and_contact_payload(record, user, partner, doc_key):
    cfg = DOCUMENT_CONFIG.get(doc_key, DOCUMENT_CONFIG['quotation'])
    partner_address = _format_address(
        partner,
        fallback='123 ถนนตัวอย่าง แขวงตัวอย่าง เขตตัวอย่าง กรุงเทพฯ 10260',
    )
    contact_name = (user and user.name) or record.env.user.name or 'Administrator'
    contact_phone = (
        (user and (user.phone or user.partner_id.phone))
        or record.company_id.phone
        or '02-000-0000'
    )
    contact_email = (
        (user and (user.email or user.partner_id.email))
        or record.company_id.email
        or 'admin@tbf-demo.co.th'
    )
    return {
        'partner_label': cfg['partner_label'],
        'partner_name': (partner and partner.display_name) or '-',
        'partner_address': partner_address,
        'partner_vat': (partner and partner.vat) or '',
        'contact_label': 'ผู้ติดต่อ / Contact',
        'contact_name': contact_name,
        'contact_phone': contact_phone,
        'contact_email': contact_email,
    }


def _get_product_image_uri(product):
    if not product:
        return False
    img = product.image_128 or product.image_256 or product.image_1920
    if not img and product.product_tmpl_id:
        img = (
            product.product_tmpl_id.image_128
            or product.product_tmpl_id.image_256
            or product.product_tmpl_id.image_1920
        )
    if not img:
        return False
    try:
        return image_data_uri(img)
    except Exception:
        return False


def _format_tax_str(taxes):
    if not taxes:
        return '-'
    labels = []
    for tax in taxes:
        if tax.amount_type == 'percent':
            amt = tax.amount
            if amt == int(amt):
                labels.append(f"{int(amt)}%")
            else:
                labels.append(f"{amt:.2f}%")
        else:
            labels.append(tax.name or '')
    return ', '.join(l for l in labels if l) or '-'


def _extract_product_titles(product, raw_name):
    raw_lines = [l.strip() for l in (raw_name or '').splitlines() if l.strip()]
    if product:
        title = product.display_name or (raw_lines[0] if raw_lines else '-')
        if len(raw_lines) > 1:
            subtitle = ' '.join(raw_lines[1:])
        elif raw_lines and raw_lines[0] != title:
            subtitle = raw_lines[0]
        else:
            subtitle = product.name or ''
    else:
        title = raw_lines[0] if raw_lines else '-'
        subtitle = ' '.join(raw_lines[1:]) if len(raw_lines) > 1 else ''
    return title, subtitle


class SaleOrderReportHelper(models.Model):
    _inherit = 'sale.order'

    def _get_unified_report_data(self, doc_type=None):
        self.ensure_one()
        if not doc_type:
            if self.env.context.get('unified_doc_type'):
                doc_type = self.env.context['unified_doc_type']
            elif self.state in ('draft', 'sent'):
                doc_type = 'quotation'
            else:
                doc_type = 'sales_order'

        cfg = DOCUMENT_CONFIG.get(doc_type, DOCUMENT_CONFIG['quotation'])
        company_info = _get_company_payload(self.company_id or self.env.company)
        partner_contact = _get_partner_and_contact_payload(
            self, self.user_id, self.partner_id, doc_type
        )

        date_str = self.date_order.strftime('%d/%m/%Y') if self.date_order else '-'
        if doc_type == 'quotation':
            if self.validity_date and self.date_order:
                days = (self.validity_date - self.date_order.date()).days
                ref_val = f"{days} วัน" if days > 0 else self.validity_date.strftime('%d/%m/%Y')
            elif self.validity_date:
                ref_val = self.validity_date.strftime('%d/%m/%Y')
            else:
                ref_val = '30 วัน'
        else:
            ref_val = (
                self.client_order_ref
                or (self.payment_term_id and self.payment_term_id.name)
                or '30 วัน'
            )

        currency_symbol = (self.currency_id and self.currency_id.symbol) or '฿'
        lines = []
        seq = 0
        has_discount = False
        discount_total = 0.0

        for line in self.order_line:
            if line.display_type:
                lines.append({
                    'display_type': line.display_type,
                    'name': line.name or '',
                })
                continue
            seq += 1
            disc = line.discount or 0.0
            if disc > 0:
                has_discount = True
                discount_total += (line.price_unit * line.product_uom_qty) * (disc / 100.0)
            title, subtitle = _extract_product_titles(line.product_id, line.name)
            lines.append({
                'display_type': False,
                'no': seq,
                'image_uri': _get_product_image_uri(line.product_id),
                'product_title': title,
                'description': subtitle,
                'qty': f"{line.product_uom_qty:,.2f}",
                'uom': (line.product_uom_id and line.product_uom_id.name) or 'หน่วย',
                'price_unit': f"{line.price_unit:,.2f}",
                'discount': f"{disc:g}%" if disc > 0 else '-',
                'vat': _format_tax_str(line.tax_ids),
                'amount': f"{line.price_subtotal:,.2f} {currency_symbol}",
            })

        remarks = _clean_html_to_lines(self.note) or cfg['default_remarks']

        return {
            'doc_type': doc_type,
            'title_th': cfg['title_th'],
            'title_en': cfg['title_en'],
            'doc_no': self.name if (self.name and self.name != '/') else 'DRAFT',
            'date_label': cfg['date_label'],
            'doc_date': date_str,
            'ref_label': cfg['ref_label'],
            'doc_ref': ref_val,
            'company': company_info,
            'partner_contact': partner_contact,
            'intro_th': cfg['intro_th'],
            'intro_en': cfg['intro_en'],
            'has_discount': has_discount,
            'lines': lines,
            'totals': {
                'subtotal': f"{self.amount_untaxed:,.2f} {currency_symbol}",
                'discount_total': f"{discount_total:,.2f} {currency_symbol}" if discount_total > 0 else False,
                'vat_label': 'ภาษีมูลค่าเพิ่ม 7% / VAT (7%)',
                'vat_amount': f"{self.amount_tax:,.2f} {currency_symbol}",
                'grand_total': f"{self.amount_total:,.2f} {currency_symbol}",
            },
            'remarks': remarks,
            'signature_label': cfg['signature_label'],
        }


class PurchaseOrderReportHelper(models.Model):
    _inherit = 'purchase.order'

    def _get_unified_report_data(self, doc_type='purchase_order'):
        self.ensure_one()
        cfg = DOCUMENT_CONFIG['purchase_order']
        company_info = _get_company_payload(self.company_id or self.env.company)
        partner_contact = _get_partner_and_contact_payload(
            self, self.user_id, self.partner_id, 'purchase_order'
        )

        date_str = self.date_order.strftime('%d/%m/%Y') if self.date_order else '-'
        if self.partner_ref:
            ref_val = self.partner_ref
        elif self.date_planned:
            ref_val = self.date_planned.strftime('%d/%m/%Y')
        else:
            ref_val = 'ตามตกลง'

        currency_symbol = (self.currency_id and self.currency_id.symbol) or '฿'
        lines = []
        seq = 0
        has_discount = False
        discount_total = 0.0

        for line in self.order_line:
            if line.display_type:
                lines.append({
                    'display_type': line.display_type,
                    'name': line.name or '',
                })
                continue
            seq += 1
            disc = line.discount or 0.0
            if disc > 0:
                has_discount = True
                discount_total += (line.price_unit * line.product_qty) * (disc / 100.0)
            title, subtitle = _extract_product_titles(line.product_id, line.name)
            lines.append({
                'display_type': False,
                'no': seq,
                'image_uri': _get_product_image_uri(line.product_id),
                'product_title': title,
                'description': subtitle,
                'qty': f"{line.product_qty:,.2f}",
                'uom': (line.uom_id and line.uom_id.name) or 'หน่วย',
                'price_unit': f"{line.price_unit:,.2f}",
                'discount': f"{disc:g}%" if disc > 0 else '-',
                'vat': _format_tax_str(line.tax_ids),
                'amount': f"{line.price_subtotal:,.2f} {currency_symbol}",
            })

        remarks = _clean_html_to_lines(self.note) or cfg['default_remarks']

        return {
            'doc_type': 'purchase_order',
            'title_th': cfg['title_th'],
            'title_en': cfg['title_en'],
            'doc_no': self.name or '-',
            'date_label': cfg['date_label'],
            'doc_date': date_str,
            'ref_label': cfg['ref_label'],
            'doc_ref': ref_val,
            'company': company_info,
            'partner_contact': partner_contact,
            'intro_th': cfg['intro_th'],
            'intro_en': cfg['intro_en'],
            'has_discount': has_discount,
            'lines': lines,
            'totals': {
                'subtotal': f"{self.amount_untaxed:,.2f} {currency_symbol}",
                'discount_total': f"{discount_total:,.2f} {currency_symbol}" if discount_total > 0 else False,
                'vat_label': 'ภาษีมูลค่าเพิ่ม 7% / VAT (7%)',
                'vat_amount': f"{self.amount_tax:,.2f} {currency_symbol}",
                'grand_total': f"{self.amount_total:,.2f} {currency_symbol}",
            },
            'remarks': remarks,
            'signature_label': cfg['signature_label'],
        }


class StockPickingReportHelper(models.Model):
    _inherit = 'stock.picking'

    def _get_unified_report_data(self, doc_type='delivery_note'):
        self.ensure_one()
        cfg = DOCUMENT_CONFIG['delivery_note']
        company = self.company_id or self.env.company
        company_info = _get_company_payload(company)
        partner_contact = _get_partner_and_contact_payload(
            self, self.user_id, self.partner_id, 'delivery_note'
        )

        dt = self.date_done or self.scheduled_date
        date_str = dt.strftime('%d/%m/%Y') if dt else '-'
        ref_val = self.origin or '-'

        currency = company.currency_id
        currency_symbol = (currency and currency.symbol) or '฿'

        lines = []
        seq = 0
        has_discount = False
        subtotal = 0.0
        tax_total = 0.0
        discount_total = 0.0

        moves = self.move_ids.filtered(lambda m: m.state != 'cancel')
        for move in moves:
            seq += 1
            qty = move.quantity if move.quantity else move.product_uom_qty
            sale_line = getattr(move, 'sale_line_id', False)
            purchase_line = getattr(move, 'purchase_line_id', False)

            if sale_line:
                price_unit = sale_line.price_unit or 0.0
                disc = sale_line.discount or 0.0
                taxes = sale_line.tax_ids
                line_sub = price_unit * qty * (1.0 - disc / 100.0)
                if sale_line.product_uom_qty:
                    ratio = qty / sale_line.product_uom_qty
                    line_tax = (sale_line.price_tax or 0.0) * ratio
                else:
                    line_tax = line_sub * 0.07 if taxes else 0.0
            elif purchase_line:
                price_unit = purchase_line.price_unit or 0.0
                disc = purchase_line.discount or 0.0
                taxes = purchase_line.tax_ids
                line_sub = price_unit * qty * (1.0 - disc / 100.0)
                if purchase_line.product_qty:
                    ratio = qty / purchase_line.product_qty
                    line_tax = (purchase_line.price_tax or 0.0) * ratio
                else:
                    line_tax = line_sub * 0.07 if taxes else 0.0
            else:
                price_unit = move.price_unit or (move.product_id.lst_price if move.product_id else 0.0)
                disc = 0.0
                taxes = move.product_id.taxes_id if move.product_id else False
                line_sub = price_unit * qty
                line_tax = line_sub * 0.07 if taxes else 0.0

            if disc > 0:
                has_discount = True
                discount_total += (price_unit * qty) * (disc / 100.0)

            subtotal += line_sub
            tax_total += line_tax

            raw_desc = move.description_picking or (move.product_id and move.product_id.name) or ''
            title, subtitle = _extract_product_titles(move.product_id, raw_desc)
            lines.append({
                'display_type': False,
                'no': seq,
                'image_uri': _get_product_image_uri(move.product_id),
                'product_title': title,
                'description': subtitle,
                'qty': f"{qty:,.2f}",
                'uom': (move.uom_id and move.uom_id.name) or 'หน่วย',
                'price_unit': f"{price_unit:,.2f}",
                'discount': f"{disc:g}%" if disc > 0 else '-',
                'vat': _format_tax_str(taxes),
                'amount': f"{line_sub:,.2f} {currency_symbol}",
            })

        grand_total = subtotal + tax_total
        remarks = _clean_html_to_lines(self.note) or cfg['default_remarks']

        return {
            'doc_type': 'delivery_note',
            'title_th': cfg['title_th'],
            'title_en': cfg['title_en'],
            'doc_no': self.name or '-',
            'date_label': cfg['date_label'],
            'doc_date': date_str,
            'ref_label': cfg['ref_label'],
            'doc_ref': ref_val,
            'company': company_info,
            'partner_contact': partner_contact,
            'intro_th': cfg['intro_th'],
            'intro_en': cfg['intro_en'],
            'has_discount': has_discount,
            'lines': lines,
            'totals': {
                'subtotal': f"{subtotal:,.2f} {currency_symbol}",
                'discount_total': f"{discount_total:,.2f} {currency_symbol}" if discount_total > 0 else False,
                'vat_label': 'ภาษีมูลค่าเพิ่ม 7% / VAT (7%)',
                'vat_amount': f"{tax_total:,.2f} {currency_symbol}",
                'grand_total': f"{grand_total:,.2f} {currency_symbol}",
            },
            'remarks': remarks,
            'signature_label': cfg['signature_label'],
        }


class AccountMoveReportHelper(models.Model):
    _inherit = 'account.move'

    def _get_unified_report_data(self, doc_type=None):
        self.ensure_one()
        if not doc_type:
            if self.env.context.get('unified_doc_type'):
                doc_type = self.env.context['unified_doc_type']
            elif self.move_type in ('out_refund', 'in_refund'):
                doc_type = 'credit_note'
            elif self.move_type in ('out_receipt', 'in_receipt'):
                doc_type = 'receipt'
            else:
                doc_type = 'invoice'

        cfg = DOCUMENT_CONFIG.get(doc_type, DOCUMENT_CONFIG['invoice'])
        company_info = _get_company_payload(self.company_id or self.env.company)
        user = self.invoice_user_id or self.user_id or self.env.user
        partner_contact = _get_partner_and_contact_payload(
            self, user, self.partner_id, doc_type
        )

        dt = self.invoice_date or self.date
        date_str = dt.strftime('%d/%m/%Y') if dt else '-'
        if doc_type == 'credit_note':
            ref_val = (
                (self.reversed_entry_id and self.reversed_entry_id.name)
                or self.invoice_origin
                or self.ref
                or '-'
            )
        elif doc_type == 'receipt':
            ref_val = self.invoice_origin or self.ref or 'ชำระแล้ว'
        else:
            if self.invoice_date_due:
                ref_val = self.invoice_date_due.strftime('%d/%m/%Y')
            else:
                ref_val = self.invoice_origin or self.ref or '-'

        currency_symbol = (self.currency_id and self.currency_id.symbol) or '฿'
        lines = []
        seq = 0
        has_discount = False
        discount_total = 0.0

        for line in self.invoice_line_ids:
            if line.display_type in ('line_section', 'line_note'):
                lines.append({
                    'display_type': line.display_type,
                    'name': line.name or '',
                })
                continue
            if line.display_type and line.display_type != 'product':
                continue
            seq += 1
            disc = line.discount or 0.0
            if disc > 0:
                has_discount = True
                discount_total += (line.price_unit * line.quantity) * (disc / 100.0)
            title, subtitle = _extract_product_titles(line.product_id, line.name)
            lines.append({
                'display_type': False,
                'no': seq,
                'image_uri': _get_product_image_uri(line.product_id),
                'product_title': title,
                'description': subtitle,
                'qty': f"{line.quantity:,.2f}",
                'uom': (line.product_uom_id and line.product_uom_id.name) or 'หน่วย',
                'price_unit': f"{line.price_unit:,.2f}",
                'discount': f"{disc:g}%" if disc > 0 else '-',
                'vat': _format_tax_str(line.tax_ids),
                'amount': f"{line.price_subtotal:,.2f} {currency_symbol}",
            })

        remarks = _clean_html_to_lines(self.narration) or cfg['default_remarks']

        return {
            'doc_type': doc_type,
            'title_th': cfg['title_th'],
            'title_en': cfg['title_en'],
            'doc_no': self.name if (self.name and self.name != '/') else 'DRAFT',
            'date_label': cfg['date_label'],
            'doc_date': date_str,
            'ref_label': cfg['ref_label'],
            'doc_ref': ref_val,
            'company': company_info,
            'partner_contact': partner_contact,
            'intro_th': cfg['intro_th'],
            'intro_en': cfg['intro_en'],
            'has_discount': has_discount,
            'lines': lines,
            'totals': {
                'subtotal': f"{self.amount_untaxed:,.2f} {currency_symbol}",
                'discount_total': f"{discount_total:,.2f} {currency_symbol}" if discount_total > 0 else False,
                'vat_label': 'ภาษีมูลค่าเพิ่ม 7% / VAT (7%)',
                'vat_amount': f"{self.amount_tax:,.2f} {currency_symbol}",
                'grand_total': f"{self.amount_total:,.2f} {currency_symbol}",
            },
            'remarks': remarks,
            'signature_label': cfg['signature_label'],
        }


class AccountPaymentReportHelper(models.Model):
    _inherit = 'account.payment'

    def _get_unified_report_data(self, doc_type='receipt'):
        self.ensure_one()
        cfg = DOCUMENT_CONFIG['receipt']
        company_info = _get_company_payload(self.company_id or self.env.company)
        partner_contact = _get_partner_and_contact_payload(
            self, self.env.user, self.partner_id, 'receipt'
        )

        date_str = self.date.strftime('%d/%m/%Y') if self.date else '-'
        invoices = self.reconciled_invoice_ids or self.invoice_ids
        if invoices:
            ref_val = ', '.join(invoices.mapped('name'))
        else:
            ref_val = self.memo or (self.journal_id and self.journal_id.name) or '-'

        currency_symbol = (self.currency_id and self.currency_id.symbol) or '฿'
        lines = []
        seq = 0
        has_discount = False
        discount_total = 0.0

        if invoices:
            for inv in invoices:
                for line in inv.invoice_line_ids:
                    if line.display_type and line.display_type != 'product':
                        continue
                    seq += 1
                    disc = line.discount or 0.0
                    if disc > 0:
                        has_discount = True
                        discount_total += (line.price_unit * line.quantity) * (disc / 100.0)
                    title, subtitle = _extract_product_titles(line.product_id, line.name)
                    lines.append({
                        'display_type': False,
                        'no': seq,
                        'image_uri': _get_product_image_uri(line.product_id),
                        'product_title': title,
                        'description': subtitle,
                        'qty': f"{line.quantity:,.2f}",
                        'uom': (line.product_uom_id and line.product_uom_id.name) or 'หน่วย',
                        'price_unit': f"{line.price_unit:,.2f}",
                        'discount': f"{disc:g}%" if disc > 0 else '-',
                        'vat': _format_tax_str(line.tax_ids),
                        'amount': f"{line.price_subtotal:,.2f} {currency_symbol}",
                    })
            subtotal_val = sum(invoices.mapped('amount_untaxed'))
            tax_val = sum(invoices.mapped('amount_tax'))
            total_val = self.amount or sum(invoices.mapped('amount_total'))
        else:
            subtotal_val = self.amount or 0.0
            tax_val = 0.0
            total_val = self.amount or 0.0
            lines.append({
                'display_type': False,
                'no': 1,
                'image_uri': False,
                'product_title': self.memo or f"รับชำระเงิน ({self.name or ''})",
                'description': (self.journal_id and self.journal_id.name) or '',
                'qty': '1.00',
                'uom': 'รายการ',
                'price_unit': f"{subtotal_val:,.2f}",
                'discount': '-',
                'vat': '-',
                'amount': f"{subtotal_val:,.2f} {currency_symbol}",
            })

        return {
            'doc_type': 'receipt',
            'title_th': cfg['title_th'],
            'title_en': cfg['title_en'],
            'doc_no': self.name or '-',
            'date_label': cfg['date_label'],
            'doc_date': date_str,
            'ref_label': cfg['ref_label'],
            'doc_ref': ref_val,
            'company': company_info,
            'partner_contact': partner_contact,
            'intro_th': cfg['intro_th'],
            'intro_en': cfg['intro_en'],
            'has_discount': has_discount,
            'lines': lines,
            'totals': {
                'subtotal': f"{subtotal_val:,.2f} {currency_symbol}",
                'discount_total': f"{discount_total:,.2f} {currency_symbol}" if discount_total > 0 else False,
                'vat_label': 'ภาษีมูลค่าเพิ่ม 7% / VAT (7%)',
                'vat_amount': f"{tax_val:,.2f} {currency_symbol}",
                'grand_total': f"{total_val:,.2f} {currency_symbol}",
            },
            'remarks': cfg['default_remarks'],
            'signature_label': cfg['signature_label'],
        }
