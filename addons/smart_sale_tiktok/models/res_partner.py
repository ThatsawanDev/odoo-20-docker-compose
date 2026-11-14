# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _get_or_create_tiktok_partner(self, shop, order_data):
        """Find or create standard customer record for imported TikTok orders."""
        recipient = order_data.get('recipient_address', {})
        name = recipient.get('name') or f"TikTok Customer ({order_data.get('buyer_email', 'Anonymous')})"
        email = order_data.get('buyer_email') or False
        phone = recipient.get('phone_number') or False
        district_info = recipient.get('district_info') or recipient.get('district_info_list') or {}
        if isinstance(district_info, list):
            district_values = {
                str(row.get('address_level_name') or row.get('address_level') or ''):
                row.get('address_name')
                for row in district_info
            }
            city = (
                district_values.get('L2')
                or district_values.get('LEVEL_2')
                or next(iter(district_values.values()), '')
            )
        else:
            city = district_info.get('address_level_2', '')
        
        domain = [('name', '=', name)]
        if email:
            domain = [('email', '=', email)]
            
        partner = self.search(domain + [('company_id', 'in', [shop.company_id.id, False])], limit=1)
        if not partner:
            partner = self.create({
                'name': name,
                'email': email,
                'phone': phone,
                'street': recipient.get('full_address', ''),
                'city': city,
                'company_id': shop.company_id.id,
                'customer_rank': 1,
            })
        return partner
