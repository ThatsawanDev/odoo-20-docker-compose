# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TikTokAccount(models.Model):
    _name = 'tiktok.account'
    _description = "TikTok Shop Developer Account"
    _order = 'name'

    name = fields.Char(string="Account Name", required=True, help="Developer application label in Odoo")
    app_key = fields.Char(string="App Key (Client ID)", required=True, copy=False)
    app_secret = fields.Char(string="App Secret (Client Secret)", required=True, copy=False, groups="base.group_system")
    region = fields.Selection([
        ('SEA', "Southeast Asia (TH/VN/MY/PH/SG/ID)"),
        ('US', "United States"),
        ('UK', "United Kingdom"),
        ('GLOBAL', "Global"),
    ], string="Endpoint Region", default='SEA', required=True)

    shop_ids = fields.One2many('tiktok.shop', 'account_id', string="TikTok Shops")
    company_ids = fields.Many2many('res.company', string="Allowed Companies", default=lambda self: self.env.companies)
    active = fields.Boolean(default=True)
    
    shop_count = fields.Integer(compute='_compute_shop_count', string="Shop Count")

    @api.depends('shop_ids')
    def _compute_shop_count(self):
        for record in self:
            record.shop_count = len(record.shop_ids)

    def action_view_shops(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('TikTok Shops'),
            'res_model': 'tiktok.shop',
            'view_mode': 'list,form',
            'domain': [('account_id', '=', self.id)],
            'context': {'default_account_id': self.id},
        }

    def action_sync_shops(self):
        """Fetch authorized seller stores associated with this developer App Key."""
        self.ensure_one()
        return True
