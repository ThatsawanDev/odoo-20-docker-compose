from odoo import api, fields, models, _
from odoo.exceptions import UserError

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

    def _get_bom_hierarchy(self, bom, visited=None):
        bom.ensure_one()
        visited = set(visited or ())
        visited.add(bom.id)
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
                'selected_bom_id': line.visual_sub_bom_id.id or False,
            }
            # Check if this product has a BOM
            sub_boms = line.visual_sub_bom_id or self.env['mrp.bom'].search([
                '|', ('product_id', '=', line.product_id.id),
                '&', ('product_tmpl_id', '=', line.product_id.product_tmpl_id.id),
                     ('product_id', '=', False),
                ('company_id', 'in', (False, self.env.company.id))
            ], limit=1)
            if sub_boms:
                line_data['has_bom'] = True
                if sub_boms[0].id not in visited:
                    line_data['sub_bom'] = self._get_bom_hierarchy(sub_boms[0], visited)
            
            result['lines'].append(line_data)
        return result

    @api.model
    def search_materials(self, query):
        domain = [('type', '!=', 'service')]
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
    def search_existing_boms(self, query='', exclude_bom_id=False, exclude_product_tmpl_id=False):
        domain = [('active', '=', True), ('company_id', 'in', (False, self.env.company.id))]
        if exclude_bom_id:
            domain.append(('id', '!=', exclude_bom_id))
        if exclude_product_tmpl_id:
            domain.append(('product_tmpl_id', '!=', exclude_product_tmpl_id))
        if query:
            domain += ['|', '|', ('product_tmpl_id.name', 'ilike', query),
                       ('product_tmpl_id.default_code', 'ilike', query), ('code', 'ilike', query)]
        boms = self.search(domain, order='id desc', limit=30)
        return [{
            'id': bom.product_id.id or bom.product_tmpl_id.product_variant_id.id,
            'bom_id': bom.id,
            'product_tmpl_id': bom.product_tmpl_id.id,
            'name': bom.product_tmpl_id.name,
            'code': bom.code or bom.product_tmpl_id.default_code or '',
            'qty_available': bom.product_id.qty_available if bom.product_id else bom.product_tmpl_id.product_variant_id.qty_available,
            'uom_name': bom.uom_id.name,
            'uom_id': bom.uom_id.id,
            'image_url': f'/web/image/product.template/{bom.product_tmpl_id.id}/image_128',
            'has_bom': True,
        } for bom in boms if bom.product_id or bom.product_tmpl_id.product_variant_id]

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
            selected_bom_id = line.get('selected_bom_id') or False
            if selected_bom_id:
                selected = self.browse(selected_bom_id).exists()
                if not selected or selected.id == bom.id or selected.product_tmpl_id.id == bom.product_tmpl_id.id:
                    raise UserError(_('The selected sub-BOM is invalid for this product.'))
                if selected.product_tmpl_id.id != self.env['product.product'].browse(line['product_id']).product_tmpl_id.id:
                    raise UserError(_('The selected sub-BOM does not match the material product.'))
            line_vals['visual_sub_bom_id'] = selected_bom_id
                
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


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    visual_sub_bom_id = fields.Many2one('mrp.bom', string='Visual Sub-BOM', ondelete='set null')
