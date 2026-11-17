{
    "name": "JSN Service ERP ภาษาไทย",
    "version": "20.0.1.0.0",
    "category": "Services/Field Service",
    "summary": "งานบริการ เครื่องจักร อะไหล่ และสินทรัพย์ตามขอบเขต JSN",
    "license": "LGPL-3",
    "author": "JSN Solution",
    "depends": ["thai_sales_stock_easy", "machine_service_management", "purchase_stock", "spiffy_theme_backend"],
    "data": [
        "security/security.xml",
        "security/ir.access.csv",
        "views/service_workflow_views.xml",
        "views/service_scope_views.xml",
        "report/service_scope_report.xml",
        "data/demo_scope.xml",
    ],
    "application": True,
    "installable": True,
    "assets": {"web.assets_backend": [
        "jsn_service_scope/static/src/scss/service_kanban.scss",
        "jsn_service_scope/static/src/scss/sale_form_compact.scss",
        "jsn_service_scope/static/src/scss/outbound_redesign.scss",
    ]},
}
