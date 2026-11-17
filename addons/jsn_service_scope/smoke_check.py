order = env.ref('jsn_service_scope.service_demo_inhouse')
assert order.report_kind == 'in_house'
assert order.machine_id.serial_number.endswith('-DEMO')
result = order.action_create_spare_issue()
assert result['res_model'] == 'stock.picking'
assert order.issue_picking_id.move_ids
report = env.ref('jsn_service_scope.action_report_jsn_service')
pdf, output_type = env['ir.actions.report']._render_qweb_pdf(report.report_name, [order.id])
assert output_type == 'pdf' and pdf.startswith(b'%PDF')
asset = env['account.asset.asset'].search([('code', '=', 'FA-DEMO-001')], limit=1)
assert asset and asset.service_machine_id
assert env.ref('jsn_service_scope.action_jsn_service_all').view_mode.startswith('kanban')
assert env.ref('jsn_service_scope.action_jsn_assets').res_model == 'account.asset.asset'
assert order.machine_id.image_1920
view = env['service.order'].get_view(view_id=env.ref('jsn_service_scope.view_jsn_service_order_kanban').id, view_type='kanban')
assert 'o_jsn_service_card' in view['arch']
quote = order.action_create_quotation()
assert quote['res_model'] == 'sale.order'
assert order.sale_order_id.order_line
print('SMOKE_OK', order.name, order.issue_picking_id.name, len(pdf), asset.name, order.sale_order_id.name)
