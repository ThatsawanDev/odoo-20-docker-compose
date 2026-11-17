"""Set the isolated JSN demonstration company and draft documents to THB."""
company = env.company
thb = env['res.currency'].with_context(active_test=False).search([('name', '=', 'THB')], limit=1)
assert thb, 'THB currency missing'
thb.active = True
company.currency_id = thb
for pricelist in env['product.pricelist'].search([('company_id', 'in', [False, company.id])]):
    pricelist.currency_id = thb
for order in env['sale.order'].search([('company_id', '=', company.id), ('state', 'in', ['draft', 'sent'])]):
    order.currency_id = thb
for asset in env['account.asset.asset'].search([('company_id', '=', company.id), ('state', '=', 'draft')]):
    asset.currency_id = thb
env.cr.commit()
print('CURRENCY_OK', company.currency_id.name, [(x.name, x.currency_id.name) for x in env['sale.order'].search([('company_id', '=', company.id)])])
