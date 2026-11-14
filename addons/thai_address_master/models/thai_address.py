from odoo import fields, models


class Province(models.Model):
    _name = "province"
    _description = "Thai Province"
    _order = "name"

    name = fields.Char(string="ชื่อจังหวัด", required=True, index=True, translate=True)
    name_eng = fields.Char(string="ชื่อภาษาอังกฤษ", index=True)
    code = fields.Char(string="รหัสจังหวัด", required=True, index=True)
    amphur_ids = fields.One2many("amphur", "province_id", string="อำเภอ / เขต")

    _code_unique = models.Constraint("unique(code)", "รหัสจังหวัดต้องไม่ซ้ำกัน")


class Amphur(models.Model):
    _name = "amphur"
    _description = "Thai District"
    _order = "province_id, name"

    name = fields.Char(string="ชื่ออำเภอ / เขต", required=True, index=True, translate=True)
    name_eng = fields.Char(string="ชื่อภาษาอังกฤษ", index=True)
    code = fields.Char(string="รหัสอำเภอ", index=True)
    province_id = fields.Many2one("province", string="จังหวัด", required=True, ondelete="cascade", index=True)
    tambon_ids = fields.One2many("tambon", "amphur_id", string="ตำบล / แขวง")


class Tambon(models.Model):
    _name = "tambon"
    _description = "Thai Subdistrict"
    _order = "amphur_id, name"

    name = fields.Char(string="ชื่อตำบล / แขวง", required=True, index=True, translate=True)
    name_eng = fields.Char(string="ชื่อภาษาอังกฤษ", index=True)
    amphur_id = fields.Many2one("amphur", string="อำเภอ / เขต", required=True, ondelete="cascade", index=True)
    province_id = fields.Many2one(related="amphur_id.province_id", string="จังหวัด", store=True, index=True)
    zip_ids = fields.One2many("zip", "tambon_id", string="รหัสไปรษณีย์")


class Zip(models.Model):
    _name = "zip"
    _description = "Thai Postcode"
    _order = "name, tambon_id"
    _rec_name = "name"

    name = fields.Char(string="รหัสไปรษณีย์", required=True, index=True)
    tambon_id = fields.Many2one("tambon", string="ตำบล / แขวง", required=True, ondelete="cascade", index=True)
    amphur_id = fields.Many2one(related="tambon_id.amphur_id", string="อำเภอ / เขต", store=True, index=True)
    province_id = fields.Many2one(related="tambon_id.province_id", string="จังหวัด", store=True, index=True)
