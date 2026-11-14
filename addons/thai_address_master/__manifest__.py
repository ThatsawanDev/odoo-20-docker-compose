{
    "name": "Thai Address Master & Contact Form",
    "version": "20.0.1.1.0",
    "category": "Contacts",
    "summary": "Thai province, district, subdistrict and postcode masters for contacts",
    "author": "thatsawan.dev@gmail.com",
    "license": "LGPL-3",
    "depends": ["contacts"],
    "data": [
        "security/ir.access.csv",
        "data/province.csv",
        "data/amphur.csv",
        "data/tambon.csv",
        "data/zip.csv",
        "views/thai_address_views.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "thai_address_master/static/src/scss/partner_form.scss",
        ],
    },
    "installable": True,
    "application": True,
}
