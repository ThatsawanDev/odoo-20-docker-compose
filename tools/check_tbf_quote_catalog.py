quote = env['sale.order'].search([('client_order_ref', '=', 'TBF-DEMO-QUOTE-WHOLESALE')], limit=1)
assert quote and quote.state == 'draft'
assert 'ตัวอย่างเงื่อนไขและข้อกำหนด' in quote.note
assert quote.tbf_show_catalog_images
assert str(quote.tbf_catalog_html).count('<img ') == 3
print('CATALOG FORM OK', quote.name, '3 images')

for xmlid in ('sale.action_report_saleorder', 'thai_sales_stock_easy.action_report_saleorder_clean'):
    report = env.ref(xmlid)
    pdf, mime = report._render_qweb_pdf(report.report_name, res_ids=quote.ids)
    assert pdf.startswith(b'%PDF') and len(pdf) > 20000
    if xmlid == 'sale.action_report_saleorder':
        with open('/tmp/tbf_quote_catalog_sample.pdf', 'wb') as stream:
            stream.write(pdf)
    print('CATALOG PDF OK', xmlid, len(pdf), mime)
env.cr.rollback()
