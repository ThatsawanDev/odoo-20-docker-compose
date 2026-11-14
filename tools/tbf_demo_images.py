"""Attach generated product photos to TBF demo products in Odoo shell."""
from pathlib import Path
from odoo.orm.fields_binary import BinaryBytes

base = Path('/mnt/extra-addons/tbf_demo_images')
codes = ('TBF-DM-CHAIR', 'TBF-DM-TABLE', 'TBF-DM-SOFA', 'TBF-DM-CABINET',
         'TBF-DM-SEAT', 'TBF-DM-SEAT-ALT', 'TBF-DM-SET4')
for code in codes:
    product = env['product.template'].search([('default_code', '=', code)], limit=1)
    assert product, f'Missing product: {code}'
    product.write({'image_1920': BinaryBytes((base / f'{code}.png').read_bytes(), f'{code}.png')})
env.cr.commit()
print(f'Attached images to {len(codes)} TBF demo products')
