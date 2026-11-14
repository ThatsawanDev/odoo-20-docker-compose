from odoo import api, models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    @api.model
    def thai_easy_fix_sale_report_filename(self):
        report = self.env.ref(
            "sale_pdf_quote_builder.action_report_saleorder_raw",
            raise_if_not_found=False,
        )
        if report:
            report.with_context(lang="th_TH").write({
                "print_report_name": (
                    "('ใบเสนอราคา - %s' if object.state in ('draft', 'sent') "
                    "else 'ใบสั่งขาย - %s') % object.name"
                ),
            })
