{
    "name": "ระบบจัดการการผลิตแบบง่าย (Thai MRP Easy)",
    "version": "20.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "summary": "Visual BOM Builder และระบบผลิตสำหรับโรงงานที่เข้าใจง่าย",
    "author": "thatsawan.dev@gmail.com",
    "license": "LGPL-3",
    "post_init_hook": "post_init_hook",
    "depends": [
        "mrp",
        "purchase",
        "stock",
    ],
    "data": [
        "views/mrp_production_views.xml",
        "views/mrp_bom_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "thai_mrp_easy/static/src/scss/visual_bom.scss",
            "thai_mrp_easy/static/src/xml/visual_bom_builder.xml",
            "thai_mrp_easy/static/src/js/visual_bom_builder.js",
            "thai_mrp_easy/static/src/scss/mrp_production.scss",
            "thai_mrp_easy/static/src/scss/production_plan.scss",
            "thai_mrp_easy/static/src/xml/production_plan.xml",
            "thai_mrp_easy/static/src/js/production_plan.js",
        ],
    },
    "application": False,
    "installable": True,
}
