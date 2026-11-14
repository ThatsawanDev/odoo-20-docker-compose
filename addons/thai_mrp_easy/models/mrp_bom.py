from odoo import api, fields, models, _

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    @api.model
    def get_visual_bom_examples(self):
        boms = self.search([('active', '=', True)], order='id desc', limit=12)
        return [{
            'id': bom.id,
            'name': bom.product_tmpl_id.name,
            'code': bom.code or bom.product_tmpl_id.default_code or '',
            'line_count': len(bom.bom_line_ids),
            'image_url': f'/web/image/product.template/{bom.product_tmpl_id.id}/image_128',
        } for bom in boms]

    @api.model
    def get_visual_bom_data(self, bom_id):
        if not bom_id:
            return {'lines': []}
        bom = self.browse(bom_id)
        if not bom.exists():
            return {'lines': []}
        return self._get_bom_hierarchy(bom)

    def _get_bom_hierarchy(self, bom):
        bom.ensure_one()
        result = {
            'id': bom.id,
            'product_id': bom.product_tmpl_id.product_variant_id.id or bom.product_id.id,
            'product_tmpl_id': bom.product_tmpl_id.id,
            'product_name': bom.product_tmpl_id.name,
            'product_qty': bom.product_qty,
            'product_uom_id': bom.uom_id.id,
            'product_uom_name': bom.uom_id.name,
            'code': bom.code or '',
            'image_url': f'/web/image/product.template/{bom.product_tmpl_id.id}/image_128',
            'lines': []
        }
        for line in bom.bom_line_ids:
            line_data = {
                'id': line.id,
                'product_id': line.product_id.id,
                'product_name': line.product_id.name,
                'product_qty': line.product_qty,
                'product_uom_id': line.uom_id.id,
                'product_uom_name': line.uom_id.name,
                'image_url': f'/web/image/product.product/{line.product_id.id}/image_128',
                'has_bom': False,
                'sub_bom': None,
            }
            # Check if this product has a BOM
            sub_boms = self.env['mrp.bom'].search([
                '|', ('product_id', '=', line.product_id.id),
                '&', ('product_tmpl_id', '=', line.product_id.product_tmpl_id.id),
                     ('product_id', '=', False),
                ('company_id', 'in', (False, self.env.company.id))
            ], limit=1)
            if sub_boms:
                line_data['has_bom'] = True
                line_data['sub_bom'] = self._get_bom_hierarchy(sub_boms[0])
            
            result['lines'].append(line_data)
        return result

    @api.model
    def search_materials(self, query):
        domain = [('is_storable', '=', True)]
        if query:
            domain.append(('name', 'ilike', query))
        
        products = self.env['product.product'].search(domain, limit=20)
        res = []
        for p in products:
            qty_available = p.qty_available
            has_bom = self.env['mrp.bom'].search_count([
                '|', ('product_id', '=', p.id),
                '&', ('product_tmpl_id', '=', p.product_tmpl_id.id),
                     ('product_id', '=', False),
                ('company_id', 'in', (False, self.env.company.id))
            ]) > 0
            res.append({
                'id': p.id,
                'product_tmpl_id': p.product_tmpl_id.id,
                'name': p.name,
                'code': p.default_code or '',
                'qty_available': qty_available,
                'uom_name': p.uom_id.name,
                'has_bom': has_bom,
                'image_url': f'/web/image/product.product/{p.id}/image_128',
                'uom_id': p.uom_id.id,
            })
        return res

    @api.model
    def save_visual_bom(self, bom_data):
        bom_id = bom_data.get('id')
        vals = {
            'product_tmpl_id': bom_data.get('product_tmpl_id'),
            'product_qty': bom_data.get('product_qty', 1.0),
            'uom_id': bom_data.get('product_uom_id'),
        }
        if bom_id:
            bom = self.browse(bom_id)
            bom.write(vals)
        else:
            bom = self.create(vals)
        
        existing_lines = bom.bom_line_ids.mapped('id')
        new_lines_ids = []
        
        for line in bom_data.get('lines', []):
            line_vals = {
                'bom_id': bom.id,
                'product_id': line['product_id'],
                'product_qty': line['product_qty'],
            }
            if 'product_uom_id' in line:
                line_vals['uom_id'] = line['product_uom_id']
                
            if line.get('id') and line['id'] in existing_lines:
                self.env['mrp.bom.line'].browse(line['id']).write(line_vals)
                new_lines_ids.append(line['id'])
            else:
                new_line = self.env['mrp.bom.line'].create(line_vals)
                new_lines_ids.append(new_line.id)
                
        lines_to_unlink = set(existing_lines) - set(new_lines_ids)
        if lines_to_unlink:
            self.env['mrp.bom.line'].browse(list(lines_to_unlink)).unlink()
            
        return bom.id
