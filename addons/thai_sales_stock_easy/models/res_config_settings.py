from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    thai_easy_enable_pricelist = fields.Boolean(
        string="Use Pricelists on Quotations",
        related="company_id.thai_easy_enable_pricelist",
        readonly=False,
    )

    def action_thai_easy_create_sample_pricelists(self):
        """Create named examples only when an administrator requests them."""
        self.ensure_one()
        company = self.company_id
        Pricelist = self.env["product.pricelist"].sudo()
        names = (
            "Wholesale (ราคาส่ง)",
            "Retail (ราคาปลีก)",
            "Government (หน่วยงานราชการ)",
        )
        pricelists = Pricelist.browse()
        for name in names:
            pricelist = Pricelist.search([
                ("name", "=", name), ("company_id", "=", company.id),
            ], limit=1)
            if not pricelist:
                pricelist = Pricelist.create({
                    "name": name,
                    "company_id": company.id,
                    "currency_id": company.currency_id.id,
                })
            pricelists |= pricelist
        return {
            "type": "ir.actions.act_window",
            "name": "Sample Pricelists",
            "res_model": "product.pricelist",
            "view_mode": "list,form",
            "domain": [("id", "in", pricelists.ids)],
            "context": {"default_company_id": company.id},
        }

    thai_sale_flow_sequence = fields.Selection(
        selection=[
            ("delivery_first", "จัดส่งก่อน แล้วออกใบแจ้งหนี้"),
            ("invoice_first", "ออกใบแจ้งหนี้ก่อน แล้วจัดส่ง"),
        ],
        string="ลำดับการขายและจัดส่ง",
        required=True,
        default="invoice_first",
        config_parameter="thai_sales_stock_easy.sale_flow_sequence",
    )
