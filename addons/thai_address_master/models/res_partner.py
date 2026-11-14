from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    province_id = fields.Many2one("province", string="จังหวัด", index=True)
    amphur_id = fields.Many2one(
        "amphur", string="อำเภอ / เขต", index=True,
        domain="[('province_id', '=', province_id)]",
    )
    tambon_id = fields.Many2one(
        "tambon", string="ตำบล / แขวง", index=True,
        domain="[('amphur_id', '=', amphur_id)]",
    )
    thai_postcode_id = fields.Many2one(
        "zip", string="รหัสไปรษณีย์", index=True,
        domain="[('tambon_id', '=', tambon_id)]",
    )

    @api.onchange("province_id")
    def _onchange_thai_province(self):
        if self.amphur_id.province_id != self.province_id:
            self.amphur_id = False
            self.tambon_id = False
            self.thai_postcode_id = False
        if self.province_id:
            self.state_id = False
            self.country_id = self.env["res.country"].search([("code", "=", "TH")], limit=1)

    @api.onchange("amphur_id")
    def _onchange_thai_amphur(self):
        if self.amphur_id:
            self.province_id = self.amphur_id.province_id
        if self.tambon_id.amphur_id != self.amphur_id:
            self.tambon_id = False
            self.thai_postcode_id = False
        self.city = self.amphur_id.name or False

    @api.onchange("tambon_id")
    def _onchange_thai_tambon(self):
        if self.tambon_id:
            self.amphur_id = self.tambon_id.amphur_id
            self.province_id = self.tambon_id.province_id
            postcode = self.tambon_id.zip_ids[:1]
            self.thai_postcode_id = postcode
            self.zip = postcode.name or False

    @api.onchange("thai_postcode_id")
    def _onchange_thai_postcode(self):
        if self.thai_postcode_id:
            self.tambon_id = self.thai_postcode_id.tambon_id
            self.amphur_id = self.thai_postcode_id.amphur_id
            self.province_id = self.thai_postcode_id.province_id
            self.zip = self.thai_postcode_id.name

    @api.constrains("province_id", "amphur_id", "tambon_id", "thai_postcode_id")
    def _check_thai_address_hierarchy(self):
        for partner in self:
            if partner.amphur_id and partner.amphur_id.province_id != partner.province_id:
                raise ValidationError("อำเภอ / เขต ไม่ได้อยู่ในจังหวัดที่เลือก")
            if partner.tambon_id and partner.tambon_id.amphur_id != partner.amphur_id:
                raise ValidationError("ตำบล / แขวง ไม่ได้อยู่ในอำเภอที่เลือก")
            if partner.thai_postcode_id and partner.thai_postcode_id.tambon_id != partner.tambon_id:
                raise ValidationError("รหัสไปรษณีย์ไม่ตรงกับตำบล / แขวงที่เลือก")
