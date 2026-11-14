from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    thai_easy_enable_pricelist = fields.Boolean(
        string="Use Pricelists on Quotations",
        help="Show the Pricelist selector on the simplified quotation form for this company.",
    )
