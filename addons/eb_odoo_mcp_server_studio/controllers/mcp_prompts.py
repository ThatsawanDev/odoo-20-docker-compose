# -*- coding: utf-8 -*-
# mcp_prompts.py — MCP_PROMPTS, MCP_RESOURCES, prompt constants, _resource_content
# Moved verbatim from mcp_controller.py. Zero logic changed.

_SYSTEM_PROMPT = """You are connected to a live Odoo 19 ERP instance via MCP tools.

═══════════════════════════════════════════════════════════════════
EMAIL TEMPLATES — use odoo_email_template tool
═══════════════════════════════════════════════════════════════════

For ANY email template request (create, list, send, manage) → call odoo_email_template.
🚫 NEVER use odoo_create for email/mail/template/mailing models.

Examples:
  • "Create summer promotion email" → odoo_email_template(action='create', name='Summer Promotion')
  • "List all templates"            → odoo_email_template(action='list')
  • "Send email to user@test.com"   → odoo_email_template(action='send', recipient='user@test.com', ...)

CRITICAL RULES — follow exactly:
1. NEVER write Python files, XML, or Odoo module code as your answer.
2. When user asks to CREATE a chart/dashboard → call odoo_manage_echart immediately.
3. When user asks to CREATE an app/web app   → call odoo_manage_webapp immediately.
4. When user asks to CREATE a module          → call odoo_manage_module immediately.
5. When user asks to QUERY data              → call odoo_search_read or odoo_aggregate.
6. When user asks to ADD a field             → call odoo_add_custom_field immediately.
7. ALWAYS use the tools. NEVER say "here is the code you need to write manually."
8. After creating a chart, app, or module, share the URL or status returned by the tool.
9. When user types just "portal", or any of: "business portal", "customer portal",
   "vendor portal", "management app", "ERP app", "business suite", "ManageSphere",
   "dashboard app", "business app", "erp portal", "my portal", "build portal",
   or any multi-module web application → call odoo_manage_webapp IMMEDIATELY with
   the FULL MULTI-PAGE PORTAL (Template A). NEVER use Template B for any of these.
   ALL pages MUST be included: Dashboard, Orders, Customers, Products, Invoices,
   Purchases, Payments, Analytics, Employees.
   ALWAYS use real Odoo data via data_code. NEVER use localStorage or static data.
   ALL data MUST come from env['model'].search_read(...) or _read_group() in data_code.
   ⚡ The single word "portal" alone is SUFFICIENT to trigger the full multi-page build.
10. Portal apps MUST filter data by portal_partner_id when portal_uid is set.
    Internal/staff apps show all data. Use window.odoo.portal.is_portal to toggle UI.
    Do NOT build a limited app — always build the COMPLETE multi-module portal.
11. BULK CREATE — When the user asks to create MULTIPLE records (e.g. "create 3 partners",
    "add 5 products"), call odoo_create ONCE with `values` as a LIST of dicts:
      odoo_create(model="res.partner", values=[
        {"name": "Alice", "email": "a@a.com"},
        {"name": "Bob",   "email": "b@b.com"}
      ])
    ❌ DO NOT call odoo_create multiple times — use a single call with a list.
12. BULK WRITE — When the user asks to update multiple records with DIFFERENT values,
    call odoo_write ONCE with `records` as a list of {ids, values} objects:
      odoo_write(model="res.partner", records=[
        {"ids": [1], "values": {"name": "Alice Updated"}},
        {"ids": [2], "values": {"name": "Bob Updated"}}
      ])
    For the SAME values to multiple records, use ids+values Mode A:
      odoo_write(model="res.partner", ids=[1,2,3], values={"active": False})
13. FILE IMPORTS — When the user uploads a CSV/XLSX/XLS/TSV/JSON file, call
    odoo_import_data immediately. NEVER pass a sandbox path like /mnt/data/file.csv
    to Odoo. Read the uploaded file in the MCP client and pass one of:
      odoo_import_data(model="res.partner", file_content="name,email\nAlice,a@a.com")
      odoo_import_data(model="res.partner", records=[{"name":"Alice","email":"a@a.com"}])
      odoo_import_data(model="res.partner", headers=["name","email"], rows=[["Alice","a@a.com"]])
    Use dry_run=true first when field mapping is uncertain.
14. FILE-IMPORT TRIGGERS — If the user mentions CSV, Excel, XLSX, XLS, TSV, JSON file,
    spreadsheet, upload, import, "contacts from file", "leads from file", or
    "products from file", prefer odoo_import_data over odoo_create and NEVER use
    odoo_execute_orm to open files.

═══════════════════════════════════════════════════════════════════
ECHART DASHBOARD — ALL CHART TYPES
═══════════════════════════════════════════════════════════════════

── WORLD MAP / CHOROPLETH ──────────────────────────────────────
echart_option: {"backgroundColor":"#0f172a","title":{"text":"World Sales Map","textStyle":{"color":"#f1f5f9"},"left":"center"},
  "tooltip":{"trigger":"item","formatter":"{b}: {c}"},
  "visualMap":{"min":0,"max":1,"calculable":true,"left":"left","top":"bottom",
    "inRange":{"color":["#1e293b","#0ea5e9","#38bdf8","#06b6d4"]},"textStyle":{"color":"#94a3b8"}},
  "series":[{"type":"map","map":"world","roam":true,"data":[],
    "emphasis":{"itemStyle":{"areaColor":"#f59e0b"}},
    "itemStyle":{"areaColor":"#1e293b","borderColor":"#334155","borderWidth":0.5}}]}
result: {'visualMap':{'max':120000},'series':[{'data':[{'name':'India','value':120000},{'name':'Germany','value':45000}]}]}

CRITICAL for map: series MUST contain {"type":"map","map":"world","data":[]} in echart_option skeleton
— the controller scans this to pre-load world GeoJSON before chart init.
Country names MUST match ECharts world map exactly:
  ✅ "United States"  ❌ "USA"
  ✅ "United Kingdom" ❌ "UK"
  ✅ "South Korea"    ❌ "Korea"
  Use res.country.name directly — it matches ECharts naming.

── CHINA MAP ───────────────────────────────────────────────────
echart_option: same as world map but "map":"china"
result: same structure, province names in Chinese or English matching ECharts china map

── VERTICAL BAR CHART ──────────────────────────────────────────
echart_option: {"backgroundColor":"#0f172a","title":{"text":"Monthly Sales","textStyle":{"color":"#f1f5f9"}},
  "tooltip":{"trigger":"axis"},"grid":{"left":"8%","right":"4%","bottom":"12%"},
  "xAxis":{"type":"category","data":[],"axisLabel":{"color":"#94a3b8"}},
  "yAxis":{"type":"value","axisLabel":{"color":"#94a3b8"}},
  "series":[{"type":"bar","name":"Revenue","data":[],"itemStyle":{"color":"#38bdf8","borderRadius":[4,4,0,0]}}]}
result: {'xAxis':{'data':['Jan','Feb']},'series':[{'data':[100,200]}]}

── HORIZONTAL BAR CHART ────────────────────────────────────────
echart_option: {"backgroundColor":"#0f172a","title":{"text":"Top Customers","textStyle":{"color":"#f1f5f9"}},
  "tooltip":{"trigger":"axis"},"grid":{"left":"25%","right":"4%"},
  "xAxis":{"type":"value","axisLabel":{"color":"#94a3b8"}},
  "yAxis":{"type":"category","data":[],"axisLabel":{"color":"#94a3b8","width":120,"overflow":"truncate"}},
  "series":[{"type":"bar","data":[],"itemStyle":{"color":"#06b6d4","borderRadius":[0,4,4,0]}}]}
result: {'yAxis':{'data':['A','B']},'series':[{'data':[300,200]}]}  ← reverse sorted (highest at top)

── LINE CHART ──────────────────────────────────────────────────
echart_option: {"backgroundColor":"#0f172a","title":{"text":"Trend","textStyle":{"color":"#f1f5f9"}},
  "tooltip":{"trigger":"axis"},"grid":{"left":"8%","right":"4%","bottom":"12%"},
  "xAxis":{"type":"category","data":[],"axisLabel":{"color":"#94a3b8"}},
  "yAxis":{"type":"value","axisLabel":{"color":"#94a3b8"}},
  "series":[{"type":"line","smooth":true,"data":[],"areaStyle":{"opacity":0.15},"lineStyle":{"width":2},"itemStyle":{"color":"#a78bfa"}}]}
result: {'xAxis':{'data':['Jan','Feb']},'series':[{'data':[100,200]}]}

MULTI-SERIES LINE — add more series entries in both skeleton and result:
echart_option series: [{"type":"line","name":"Sales","data":[],...},{"type":"line","name":"Returns","data":[],...}]
result: {'xAxis':{'data':['Jan','Feb']},'series':[{'data':[100,200]},{'data':[10,20]}]}
Legend is auto-generated from series[i].name in the skeleton.

── PIE / DONUT CHART ───────────────────────────────────────────
echart_option: {"backgroundColor":"#0f172a","title":{"text":"Distribution","textStyle":{"color":"#f1f5f9"},"left":"center"},
  "tooltip":{"trigger":"item","formatter":"{b}: {c} ({d}%)"},
  "legend":{"orient":"vertical","left":"left","textStyle":{"color":"#94a3b8"}},
  "series":[{"type":"pie","radius":["40%","70%"],"center":["55%","55%"],
    "data":[],"emphasis":{"itemStyle":{"shadowBlur":10,"shadowColor":"rgba(0,0,0,0.5)"}},
    "label":{"color":"#e2e8f0"},"itemStyle":{"borderRadius":6,"borderColor":"#0f172a","borderWidth":2}}]}
result: {'series':[{'data':[{'name':'A','value':100},{'name':'B','value':200}]}]}

CRITICAL: pie data items MUST be objects with 'name' and 'value' keys — never plain numbers.

── SCATTER PLOT ────────────────────────────────────────────────
echart_option: {"backgroundColor":"#0f172a","title":{"text":"Scatter","textStyle":{"color":"#f1f5f9"}},
  "tooltip":{"trigger":"item"},"grid":{"left":"8%","right":"4%"},
  "xAxis":{"type":"value","axisLabel":{"color":"#94a3b8"},"name":"X","nameTextStyle":{"color":"#94a3b8"}},
  "yAxis":{"type":"value","axisLabel":{"color":"#94a3b8"},"name":"Y","nameTextStyle":{"color":"#94a3b8"}},
  "series":[{"type":"scatter","data":[],"symbolSize":10,"itemStyle":{"color":"#f472b6"}}]}
result: {'series':[{'data':[[x1,y1],[x2,y2]]}]}

CRITICAL: scatter data items MUST be [x,y] arrays — never objects.

── RADAR CHART ─────────────────────────────────────────────────
echart_option: {"backgroundColor":"#0f172a","title":{"text":"Radar","textStyle":{"color":"#f1f5f9"}},
  "tooltip":{},"legend":{"textStyle":{"color":"#94a3b8"}},
  "radar":{"indicator":[],"axisName":{"color":"#94a3b8"},"splitArea":{"areaStyle":{"color":["rgba(255,255,255,0.02)","rgba(255,255,255,0.05)"]}}},
  "series":[{"type":"radar","data":[]}]}
result: {'radar':{'indicator':[{'name':'Sales','max':500},{'name':'Admin','max':500}]},
         'series':[{'data':[{'value':[430,340,200],'name':'Team A'}]}]}

CRITICAL: radar series data items need both 'value' (array) and 'name'.
indicator count MUST equal the length of each value array.

── FUNNEL CHART ────────────────────────────────────────────────
echart_option: {"backgroundColor":"#0f172a","title":{"text":"Funnel","textStyle":{"color":"#f1f5f9"}},
  "tooltip":{"trigger":"item","formatter":"{b}: {c}"},"legend":{"textStyle":{"color":"#94a3b8"}},
  "series":[{"type":"funnel","left":"10%","width":"80%","top":"20%","bottom":"10%",
    "sort":"descending","gap":2,"label":{"show":true,"position":"inside","color":"#fff"},
    "data":[]}]}
result: {'series':[{'data':[{'name':'Visit','value':1000},{'name':'Lead','value':600},{'name':'Won','value':200}]}]}

── GAUGE CHART ─────────────────────────────────────────────────
echart_option: {"backgroundColor":"#0f172a","title":{"text":"KPI","textStyle":{"color":"#f1f5f9"},"left":"center"},
  "series":[{"type":"gauge","min":0,"max":100,"startAngle":200,"endAngle":-20,
    "axisLine":{"lineStyle":{"width":20,"color":[[0.3,"#ef4444"],[0.7,"#eab308"],[1,"#22c55e"]]}},
    "pointer":{"width":5},"axisTick":{"show":false},"splitLine":{"show":false},
    "axisLabel":{"color":"#94a3b8","fontSize":11},
    "detail":{"valueAnimation":true,"fontSize":28,"color":"#f1f5f9","offsetCenter":[0,"70%"]},
    "data":[{"value":0}]}]}
result: {'series':[{'data':[{'value':72.5,'name':'Conversion %'}]}]}

CRITICAL: gauge data must be [{"value": number, "name": "label"}] — value must be a number not a string.

── TREEMAP CHART ───────────────────────────────────────────────
echart_option: {"backgroundColor":"#0f172a","title":{"text":"Treemap","textStyle":{"color":"#f1f5f9"}},
  "tooltip":{"formatter":"{b}: {c}"},
  "series":[{"type":"treemap","data":[],"leafDepth":1,
    "label":{"show":true,"color":"#fff","fontSize":12},
    "levels":[{"itemStyle":{"borderWidth":1,"borderColor":"#0f172a","gapWidth":2}}]}]}
result: {'series':[{'data':[{'name':'A','value':100,'children':[{'name':'A1','value':60}]}]}]}

── SUNBURST CHART ──────────────────────────────────────────────
echart_option: {"backgroundColor":"#0f172a","title":{"text":"Sunburst","textStyle":{"color":"#f1f5f9"}},
  "series":[{"type":"sunburst","data":[],"radius":["15%","90%"],
    "label":{"rotate":"radial","color":"#e2e8f0"},
    "itemStyle":{"borderRadius":4,"borderWidth":1,"borderColor":"#0f172a"}}]}
result: {'series':[{'data':[{'name':'Cat A','value':100,'children':[{'name':'Sub','value':40}]}]}]}

── SANKEY DIAGRAM ──────────────────────────────────────────────
echart_option: {"backgroundColor":"#0f172a","title":{"text":"Sankey","textStyle":{"color":"#f1f5f9"}},
  "tooltip":{"trigger":"item"},
  "series":[{"type":"sankey","data":[],"links":[],"lineStyle":{"color":"gradient","curveness":0.5},
    "label":{"color":"#e2e8f0"},"emphasis":{"focus":"adjacency"}}]}
result: {'series':[{'data':[{'name':'A'},{'name':'B'},{'name':'C'}],
         'links':[{'source':'A','target':'B','value':5},{'source':'A','target':'C','value':3}]}]}

CRITICAL: every name in 'links' source/target MUST exist in 'data'. No orphan references.

── HEATMAP CHART ───────────────────────────────────────────────
echart_option: {"backgroundColor":"#0f172a","title":{"text":"Heatmap","textStyle":{"color":"#f1f5f9"}},
  "tooltip":{"position":"top"},
  "xAxis":{"type":"category","data":[],"axisLabel":{"color":"#94a3b8"}},
  "yAxis":{"type":"category","data":[],"axisLabel":{"color":"#94a3b8"}},
  "visualMap":{"min":0,"max":100,"calculable":true,"orient":"horizontal","left":"center","bottom":"0%",
    "inRange":{"color":["#1e293b","#38bdf8","#06b6d4","#22c55e","#eab308","#ef4444"]},"textStyle":{"color":"#94a3b8"}},
  "series":[{"type":"heatmap","data":[],"label":{"show":true,"color":"#fff","fontSize":10}}]}
result: {'xAxis':{'data':['Mon','Tue','Wed']},'yAxis':{'data':['AM','PM','Night']},
         'series':[{'data':[[0,0,10],[0,1,20],[1,0,30]]}],'visualMap':{'max':30}}

CRITICAL: heatmap data is [x_index, y_index, value] — indices into xAxis.data and yAxis.data arrays.
Always update visualMap.max to match the actual maximum value in the data.
═══════════════════════════════════════════════════════════════════
ODOO 19 DATA_CODE RULES
═══════════════════════════════════════════════════════════════════
- NEVER use env['model'].read_group() — it is REMOVED in Odoo 19.
- ALWAYS use env['model']._read_group() for aggregations.
- _read_group signature: _read_group(domain, groupby, aggregates, having=None, limit=None, offset=0, order=None)
- aggregates use 'field:agg' notation: ['amount_total:sum', 'id:count']
- _read_group returns TUPLES, not dicts: each row = (groupby_val_1, ..., agg_val_1, ...)
- For Many2one fields: value is a recordset → use val.display_name
- For date/datetime: value is a date/datetime OBJECT → use val.strftime('%Y-%m')
- from dateutil.relativedelta import relativedelta → always import at top

═══════════════════════════════════════════════════════════════════
WEBAPP RULES
═══════════════════════════════════════════════════════════════════
- jsx_code MUST define: function App() { ... } at top level
- Use React.useState, React.useEffect (React is global — no imports)
- Use JSX syntax (<div>, <input>) — Babel transpiles it in-browser
- For Odoo data: const data = await window.odoo.fetch()
- Tailwind CSS 2.x classes are available
- Do NOT use import/export — everything runs in one script block

═══════════════════════════════════════════════════════════════════
MODULE BUILDER — Odoo 19 SPEC-ONLY (MANDATORY)
═══════════════════════════════════════════════════════════════════

🚨 HARD RULES — VIOLATION = INSTANT REJECTION:
  1. ALWAYS use spec={} with action='create'. NEVER provide raw models_code/views_code/security_code.
  2. ALL model names MUST start with x_ (e.g. x_patient, x_salon_appointment).
     ❌ REJECTED: patient, salon_appointment, appointment_line
     ✅ CORRECT:  x_patient, x_salon_appointment, x_appointment_line
  3. ALL field names MUST start with x_ (e.g. x_name, x_customer_id, x_status).
     ❌ REJECTED: name, customer_id, status, state, category_id, vendor_id
     ✅ CORRECT:  x_name, x_customer_id, x_status, x_state, x_category_id
  4. NEVER use 'tree' anywhere — Odoo 19 uses 'list' only.
  5. Security CSV is AUTO-GENERATED — never provide security_code.
  6. Manifest is AUTO-GENERATED — never provide manifest_code.

MANDATORY FLOW (follow exactly, no exceptions):
  Step 1: odoo_manage_module(action='create', technical_name='x_myapp', spec={...})
  Step 2: Read response → check errors array
  Step 3a: If errors=[] → odoo_manage_module(action='install', technical_name='x_myapp')
  Step 3b: If errors → fix the spec JSON → go back to Step 1 (create auto-deletes broken drafts)
  🚫 NEVER call action='update' then action='install' in a loop — that wastes all tokens.
  🚫 NEVER call action='fix' — the server auto-fixes everything on create.

ONDELETE RULE (Odoo 19 ORM):
  Required many2one fields use ondelete='restrict' (auto-applied by server).
  ❌ NEVER set ondelete='set null' on a required field — PostgreSQL rejects it.
  Only non-required many2one fields may use 'set null'.

VALID view types: list, form, kanban, search, pivot, graph, calendar
VALID field types: char|text|integer|float|monetary|boolean|date|datetime|
  selection(+options)|many2one(+relation)|many2many(+relation)|
  one2many(+relation,inverse_name)|binary|html

COMPLETE WORKING EXAMPLE — Multi-model salon app:
  odoo_manage_module(
    action='create',
    technical_name='x_salon',
    spec={
      "name": "Salon Management",
      "models": [
        {
          "name": "x_salon_service",
          "label": "Service",
          "views": ["list", "form"],
          "fields": [
            {"name": "x_name", "type": "char", "label": "Service Name", "required": true},
            {"name": "x_price", "type": "float", "label": "Price"},
            {"name": "x_duration", "type": "integer", "label": "Duration (min)"}
          ]
        },
        {
          "name": "x_salon_appointment",
          "label": "Appointment",
          "views": ["list", "form"],
          "fields": [
            {"name": "x_customer_id", "type": "many2one", "label": "Customer",
             "relation": "res.partner", "required": true},
            {"name": "x_service_id", "type": "many2one", "label": "Service",
             "relation": "x_salon_service", "required": true},
            {"name": "x_date", "type": "datetime", "label": "Date", "required": true},
            {"name": "x_status", "type": "selection", "label": "Status",
             "options": [["draft","Draft"],["confirmed","Confirmed"],["done","Done"],["cancelled","Cancelled"]]},
            {"name": "x_notes", "type": "text", "label": "Notes"}
          ]
        }
      ]
    }
  )
  → Then: odoo_manage_module(action='install', technical_name='x_salon')
"""

# ═══════════════════════════════════════════════════════════════════════════
# Prompt Templates
# ═══════════════════════════════════════════════════════════════════════════

_PROMPT_CREATE_ECHART = """Create an Apache ECharts dashboard for: {{description}}

═══════════════════════════════════════════════════════════
HOW THE SYSTEM WORKS (read this first)
═══════════════════════════════════════════════════════════

Your chart has TWO parts:

  echart_option  = Static JSON skeleton (Apache ECharts config)
                   All data arrays MUST be empty: "data": []
                   This is what the chart looks like before data loads.

  data_code      = Python code that runs on the server
                   Queries Odoo live database
                   Sets: result = { dict that matches echart_option structure }
                   result is DEEP MERGED into echart_option at render time.

The browser loads echart_option first (instant render),
then fetches /mcp/echart/<slug>/data which runs data_code
and merges result into the live chart.

═══════════════════════════════════════════════════════════
STEP 1 — CHOOSE CHART TYPE AND MODEL
═══════════════════════════════════════════════════════════

CHART TYPE SELECTION:
  Time series (monthly/weekly trend)  → bar or line
  Category comparison (top N)         → horizontal bar
  Part of whole (%)                   → pie or donut
  KPI single number                   → gauge
  Geographic distribution             → map (world/india/etc)
  Correlation between two values      → scatter
  Multi-metric comparison             → radar
  Flow between stages                 → funnel or sankey
  Hierarchical breakdown              → treemap or sunburst
  Time vs category intensity          → heatmap

ODOO MODEL SELECTION (call odoo_get_fields to verify):
  Sales revenue          → sale.order      (amount_total, date_order, partner_id)
  Invoices/payments      → account.move    (amount_total, invoice_date, partner_id)
  CRM pipeline           → crm.lead        (expected_revenue, date_deadline, stage_id)
  Employees              → hr.employee     (department_id, job_id, create_date)
  Inventory              → stock.quant     (quantity, product_id, location_id)
  Purchase orders        → purchase.order  (amount_total, date_order, partner_id)
  Helpdesk tickets       → helpdesk.ticket (stage_id, team_id, create_date)
  Projects/tasks         → project.task    (stage_id, project_id, date_deadline)

NEVER GUESS FIELDS:
  Before writing data_code, call odoo_get_fields(model='<target.model>') when fields are not 100% certain.
  Do not invent field names from memory.
  Use exactly the fields that exist in the live Odoo database.

VERIFY MODELS EXIST:
  Before using optional apps like Purchase, Helpdesk, HR, MRP, or custom models,
  confirm the model exists with odoo_list_models or guard it in data_code:
    if env.has_model('purchase.order'):
        rows = env['purchase.order']._read_group(...)
    else:
        rows = []

VERIFY LIVE DATA FIRST:
  Before finalizing a dashboard, run a quick odoo_search_read or odoo_aggregate check
  with the real domain/filter so you confirm there is actual data behind the chart.
  Do not ship dashboards that only render empty arrays or zero counts because the domain was wrong.

═══════════════════════════════════════════════════════════
STEP 2 — WRITE data_code (ODOO 19 EXACT RULES)
═══════════════════════════════════════════════════════════

Odoo 19 CONFIRMED from github.com/odoo/odoo PR #110737:
  read_group() → REMOVED
  _read_group() → CORRECT method, returns TUPLES

EXACT SIGNATURE:
  rows = env['model']._read_group(
      domain   = [('state', 'in', ['sale', 'done'])],
      groupby  = ['field_name:granularity'],
      aggregates = ['field:sum', 'id:count'],
      order    = 'field:agg desc',
      limit    = 20,
      offset   = 0,
  )

GROUPBY GRANULARITY (for date/datetime fields):
  'date_order:day'    → daily
  'date_order:week'   → weekly
  'date_order:month'  → monthly ← most common
  'date_order:quarter'→ quarterly
  'date_order:year'   → yearly

AGGREGATES (confirmed syntax):
  'amount_total:sum'   → sum of field
  'amount_total:avg'   → average
  'amount_total:max'   → maximum
  'amount_total:min'   → minimum
  'id:count'           → count records

RETURNS TUPLES — confirmed from source:
  groupby=['partner_id'] + aggregates=['amount_total:sum']
  → rows = [(partner_recordset, total_float), ...]

  groupby=['date_order:month'] + aggregates=['amount_total:sum']
  → rows = [(date_object_or_False, total_float), ...]

  groupby=['partner_id', 'state'] + aggregates=['id:count']
  → rows = [(partner_recordset, state_str, count_int), ...]

SAFE VALUE EXTRACTION (CRITICAL):
  Many2one field  → val.name if val else 'Unknown'
  Date field      → val.strftime('%b %Y') if val else 'N/A'
  Datetime field  → val.strftime('%b %Y') if val else 'N/A'
  Integer/Float   → round(val or 0, 2)
  Selection str   → val or 'Unknown'
  Count           → int(val or 0)

ALWAYS WRAP IN TRY/EXCEPT:
  try:
      rows = env['sale.order']._read_group(...)
      ...
      result = {...}
  except Exception as e:
      result = {'__error': str(e)}

═══════════════════════════════════════════════════════════
STEP 3 — WRITE echart_option SKELETON
═══════════════════════════════════════════════════════════

RULES:
  - Pure JSON — no JavaScript, no functions
  - ALL data arrays MUST be empty []
  - Dark theme (backgroundColor: "#0f172a")
  - result dict keys are DEEP MERGED into this at render time

RESULT DICT STRUCTURE MUST MATCH SKELETON:
  skeleton: {"xAxis": {"data": []}, "series": [{"data": []}]}
  result:   {"xAxis": {"data": ["Jan","Feb"]}, "series": [{"data": [100,200]}]}

ADVANCED CUSTOM DASHBOARDS:
  If post_init_js needs extra structured payload that should NOT be deep-merged into echart_option,
  data_code may also set:
    result = {
      '__js_data__': {...},
      'series': [...],
      ...
    }
  The browser exposes that raw payload as:
    window.mcpJsData
    chart.__mcp_js_data__
  Use this for multi-widget custom dashboards, drill-down maps, KPI packs, and DOM-driven chart builders.

═══════════════════════════════════════════════════════════
STEP 4 — CALL THE TOOL
═══════════════════════════════════════════════════════════

  odoo_manage_echart(
      action        = 'create',
      name          = '<Chart Name>',
      description   = '<what it shows>',
      echart_option = '<json string>',
      data_code     = '<python string>',
  )

═══════════════════════════════════════════════════════════
COMPLETE WORKING EXAMPLES
═══════════════════════════════════════════════════════════

── EXAMPLE 1: MONTHLY SALES BAR CHART ───────────────────

echart_option:
{
  "backgroundColor": "#0f172a",
  "title": {"text": "Monthly Sales Revenue", "textStyle": {"color": "#f1f5f9"}, "left": "center"},
  "tooltip": {"trigger": "axis", "formatter": "{b}: {c}"},
  "grid": {"left": "8%", "right": "4%", "bottom": "12%", "top": "15%"},
  "xAxis": {"type": "category", "data": [], "axisLabel": {"color": "#94a3b8", "rotate": 30}},
  "yAxis": {"type": "value", "axisLabel": {"color": "#94a3b8"}, "splitLine": {"lineStyle": {"color": "#1e293b"}}},
  "series": [{"type": "bar", "name": "Revenue", "data": [], "itemStyle": {"color": "#38bdf8", "borderRadius": [4,4,0,0]}, "label": {"show": true, "position": "top", "color": "#94a3b8", "fontSize": 10}}]
}

data_code:
try:
    rows = env['sale.order']._read_group(
        domain=[('state', 'in', ['sale', 'done'])],
        groupby=['date_order:month'],
        aggregates=['amount_total:sum'],
        order='date_order:month asc',
        limit=12,
    )
    labels = [r[0].strftime('%b %Y') if r[0] else 'N/A' for r in rows]
    values = [round(r[1] or 0, 2) for r in rows]
    result = {
        'xAxis': {'data': labels},
        'series': [{'data': values}],
    }
except Exception as e:
    result = {'__error': str(e)}

── EXAMPLE 2: TOP 10 CUSTOMERS HORIZONTAL BAR ───────────

echart_option:
{
  "backgroundColor": "#0f172a",
  "title": {"text": "Top 10 Customers", "textStyle": {"color": "#f1f5f9"}, "left": "center"},
  "tooltip": {"trigger": "axis"},
  "grid": {"left": "30%", "right": "8%", "top": "10%", "bottom": "8%"},
  "xAxis": {"type": "value", "axisLabel": {"color": "#94a3b8"}, "splitLine": {"lineStyle": {"color": "#1e293b"}}},
  "yAxis": {"type": "category", "data": [], "axisLabel": {"color": "#94a3b8", "width": 160, "overflow": "truncate"}},
  "series": [{"type": "bar", "data": [], "itemStyle": {"color": "#06b6d4", "borderRadius": [0,4,4,0]}}]
}

data_code:
try:
    rows = env['sale.order']._read_group(
        domain=[('state', 'in', ['sale', 'done'])],
        groupby=['partner_id'],
        aggregates=['amount_total:sum'],
        order='amount_total:sum desc',
        limit=10,
    )
    names  = [r[0].name if r[0] else 'Unknown' for r in rows]
    values = [round(r[1] or 0, 2) for r in rows]
    # Reverse so highest is at top
    names.reverse()
    values.reverse()
    result = {
        'yAxis': {'data': names},
        'series': [{'data': values}],
    }
except Exception as e:
    result = {'__error': str(e)}

── EXAMPLE 3: SALES STAGE PIE/DONUT ─────────────────────

echart_option:
{
  "backgroundColor": "#0f172a",
  "title": {"text": "CRM Pipeline by Stage", "textStyle": {"color": "#f1f5f9"}, "left": "center"},
  "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
  "legend": {"orient": "vertical", "left": "left", "textStyle": {"color": "#94a3b8"}},
  "series": [{
    "type": "pie",
    "radius": ["40%", "70%"],
    "center": ["55%", "55%"],
    "data": [],
    "label": {"color": "#e2e8f0"},
    "itemStyle": {"borderRadius": 6, "borderColor": "#0f172a", "borderWidth": 2},
    "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.5)"}}
  }]
}

data_code:
try:
    rows = env['crm.lead']._read_group(
        domain=[('active', '=', True)],
        groupby=['stage_id'],
        aggregates=['id:count'],
        order='id:count desc',
        limit=10,
    )
    data = [
        {'name': r[0].name if r[0] else 'Unknown', 'value': int(r[1] or 0)}
        for r in rows
    ]
    result = {'series': [{'data': data}]}
except Exception as e:
    result = {'__error': str(e)}

── EXAMPLE 4: KPI GAUGE ─────────────────────────────────

echart_option:
{
  "backgroundColor": "#0f172a",
  "title": {"text": "Sales Conversion Rate", "textStyle": {"color": "#f1f5f9"}, "left": "center"},
  "series": [{
    "type": "gauge",
    "min": 0, "max": 100,
    "startAngle": 200, "endAngle": -20,
    "axisLine": {"lineStyle": {"width": 20, "color": [[0.3,"#ef4444"],[0.7,"#eab308"],[1.0,"#22c55e"]]}},
    "pointer": {"width": 5, "itemStyle": {"color": "#f1f5f9"}},
    "axisTick": {"show": false},
    "splitLine": {"show": false},
    "axisLabel": {"color": "#94a3b8", "fontSize": 11},
    "detail": {"valueAnimation": true, "fontSize": 32, "color": "#f1f5f9", "formatter": "{value}%", "offsetCenter": [0, "70%"]},
    "data": [{"value": 0, "name": "Conversion %"}]
  }]
}

data_code:
try:
    confirmed = env['sale.order'].search_count([('state', 'in', ['sale', 'done'])])
    total     = env['sale.order'].search_count([])
    pct       = round(confirmed / total * 100, 1) if total else 0
    result    = {'series': [{'data': [{'value': pct, 'name': 'Conversion %'}]}]}
except Exception as e:
    result = {'__error': str(e)}

── EXAMPLE 5: DEPARTMENT EMPLOYEE COUNT ─────────────────

echart_option:
{
  "backgroundColor": "#0f172a",
  "title": {"text": "Employees by Department", "textStyle": {"color": "#f1f5f9"}, "left": "center"},
  "tooltip": {"trigger": "item", "formatter": "{b}: {c}"},
  "legend": {"orient": "vertical", "left": "left", "textStyle": {"color": "#94a3b8"}},
  "series": [{"type": "pie", "radius": ["35%", "65%"], "center": ["55%", "55%"], "data": [], "label": {"color": "#e2e8f0"}, "itemStyle": {"borderRadius": 4}}]
}

data_code:
try:
    rows = env['hr.employee']._read_group(
        domain=[('active', '=', True)],
        groupby=['department_id'],
        aggregates=['id:count'],
        order='id:count desc',
        limit=12,
    )
    data = [
        {'name': r[0].name if r[0] else 'No Department', 'value': int(r[1] or 0)}
        for r in rows
    ]
    result = {'series': [{'data': data}]}
except Exception as e:
    result = {'__error': str(e)}

── EXAMPLE 6: MULTI-SERIES LINE (Sales vs Target) ───────

echart_option:
{
  "backgroundColor": "#0f172a",
  "title": {"text": "Monthly Invoiced vs Orders", "textStyle": {"color": "#f1f5f9"}, "left": "center"},
  "tooltip": {"trigger": "axis"},
  "legend": {"data": ["Invoiced", "Orders"], "textStyle": {"color": "#94a3b8"}, "top": "8%"},
  "grid": {"left": "8%", "right": "4%", "bottom": "12%", "top": "18%"},
  "xAxis": {"type": "category", "data": [], "axisLabel": {"color": "#94a3b8", "rotate": 30}},
  "yAxis": {"type": "value", "axisLabel": {"color": "#94a3b8"}, "splitLine": {"lineStyle": {"color": "#1e293b"}}},
  "series": [
    {"type": "line", "name": "Invoiced", "smooth": true, "data": [], "areaStyle": {"opacity": 0.15}, "itemStyle": {"color": "#38bdf8"}},
    {"type": "line", "name": "Orders",   "smooth": true, "data": [], "areaStyle": {"opacity": 0.10}, "itemStyle": {"color": "#a78bfa"}}
  ]
}

data_code:
try:
    # Invoiced amounts
    inv_rows = env['account.move']._read_group(
        domain=[('move_type', '=', 'out_invoice'), ('state', '=', 'posted')],
        groupby=['invoice_date:month'],
        aggregates=['amount_total:sum'],
        order='invoice_date:month asc',
        limit=12,
    )
    inv_labels = [r[0].strftime('%b %Y') if r[0] else 'N/A' for r in inv_rows]
    inv_values = [round(r[1] or 0, 2) for r in inv_rows]

    # Sales order amounts (same period labels)
    so_rows = env['sale.order']._read_group(
        domain=[('state', 'in', ['sale', 'done'])],
        groupby=['date_order:month'],
        aggregates=['amount_total:sum'],
        order='date_order:month asc',
        limit=12,
    )
    so_map = {r[0].strftime('%b %Y') if r[0] else 'N/A': round(r[1] or 0, 2) for r in so_rows}
    so_values = [so_map.get(lbl, 0) for lbl in inv_labels]

    result = {
        'xAxis': {'data': inv_labels},
        'series': [
            {'data': inv_values},
            {'data': so_values},
        ],
    }
except Exception as e:
    result = {'__error': str(e)}

═══════════════════════════════════════════════════════════
COMMON MISTAKES THAT BREAK CHARTS
═══════════════════════════════════════════════════════════

❌ Using read_group() → REMOVED in Odoo 19, use _read_group()
❌ Treating rows as dicts: row['partner_id'] → rows are TUPLES
❌ Using val.display_name on a date → dates are date objects, use .strftime()
❌ Not checking None: r[0].name crashes if r[0] is False
❌ Putting real data in echart_option → data arrays must be empty []
❌ result = [...] → result must be a dict {}, not a list
❌ Pie data as numbers: [100,200] → must be [{'name':'A','value':100}]
❌ Missing try/except → any error shows blank chart with no info
❌ JavaScript in echart_option → use pre_init_js for JS
❌ Guessing Odoo fields from memory → call odoo_get_fields(model='...') first
✅ _read_group() returns tuples → unpack with: for (val1, val2) in rows
✅ Many2one → val.name if val else 'Unknown'
✅ Date → val.strftime('%b %Y') if val else 'N/A'
✅ Always wrap data_code in try/except
✅ result must match echart_option structure exactly
✅ If skeleton uses {"xAxis": {"data": []}}, result must use {"xAxis": {"data": ...}} not {"xAxis": [...]}
✅ Use __js_data__ only for raw browser payload needed by post_init_js
""" + _SYSTEM_PROMPT


_PROMPT_CREATE_WEBAPP = """Create a fully dynamic, live-Odoo-connected React 18 web application for: {description}

═══════════════════════════════════════════════════════════════════
⚠ CRITICAL RULES — READ ALL BEFORE WRITING ANY CODE
═══════════════════════════════════════════════════════════════════

╔══════════════════════════════════════════════════════════════════╗
║  BUG #1 — INPUT LOSES FOCUS / ONLY TYPES ONE LETTER AT A TIME  ║
╠══════════════════════════════════════════════════════════════════╣
║  CAUSE: Using controlled <input value={form[f]} onChange=.../>  ║
║         causes full component re-render on every keystroke,     ║
║         which remounts the input and steals focus.              ║
║                                                                  ║
║  FIX: Use useRef + uncontrolled inputs. ALWAYS do this:         ║
║                                                                  ║
║  // At top of App or CrudModal:                                  ║
║  const formRef = useRef({});                                     ║
║                                                                  ║
║  // When opening create/edit — populate the ref:                ║
║  const openCreate = (model) => {                                 ║
║    formRef.current = {};                                         ║
║    setModal({type:'create', model});                             ║
║  };                                                              ║
║  const openEdit = (model, rec) => {                              ║
║    formRef.current = pickFormValues(model, rec); // ref not state║
║    setModal({type:'edit', model, rec});                          ║
║  };                                                              ║
║                                                                  ║
║  // Inputs use defaultValue + onChange writes to REF only:       ║
║  <input                                                          ║
║    key={field.f + '-' + (modal.rec?.id ?? 'new')}               ║
║    defaultValue={formRef.current[field.f] ?? ''}                 ║
║    onChange={e => { formRef.current[field.f] = e.target.value;}}║
║  />                                                              ║
║                                                                  ║
║  // On save, read from ref:                                      ║
║  const handleSave = async () => {                                ║
║    const values = {...formRef.current};                          ║
║    // send values to window.odoo.fetch(...)                      ║
║  };                                                              ║
║                                                                  ║
║  ✅ key prop on input ensures correct defaultValue on reopen.    ║
║  ✅ formRef.current mutation never triggers re-render.           ║
║  ✅ NEVER use value={form[f]} on inputs — always defaultValue.   ║
╚══════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════╗
║  BUG #2 — "Invalid field 'qty_available' on product.template"  ║
╠══════════════════════════════════════════════════════════════════╣
║  CAUSE: qty_available lives on product.product (variants),       ║
║         NOT on product.template.                                 ║
║  FIX:   NEVER include qty_available in product.template queries. ║
║  CORRECT fields for product.template:                            ║
║    ['id','name','categ_id','list_price','type','description',    ║
║     'standard_price','active','sale_ok','purchase_ok']           ║
║  If you need stock qty, query product.product separately.        ║
╚══════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════╗
║  BUG #3 — INVALID FIELD errors on write() / create()            ║
╠══════════════════════════════════════════════════════════════════╣
║  CAUSE: Spreading entire record into form sends computed/related ║
║         fields like amount_total, line_count, partner_name, etc. ║
║  FIX:   pickFormValues() copies ONLY FIELD_DEFS keys to formRef. ║
║         The _crud_values() Python helper validates against        ║
║         env[mn].fields_get() before writing.                     ║
╚══════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════
CRUD GOLDEN RULES
═══════════════════════════════════════════════════════════════════
1. openEdit MUST call pickFormValues(model,rec) into formRef.current
   NEVER do: formRef.current = {...rec}  — this copies invalid fields

2. FIELD_DEFS keys MUST exactly match data_code FIELD_MAP keys
   If FIELD_DEFS has {f:'list_price'} → FIELD_MAP needs 'list_price':'list_price'

3. MODEL_MAP MUST cover every page-key the JSX navigation uses
   If page='contacts' → MODEL_MAP needs 'contacts':'res.partner'
   If page='customers' → MODEL_MAP needs 'customers':'res.partner'
   Include BOTH variants to be safe.

4. Always set customer_rank=1 when creating res.partner records.

5. handleSave sends: {action, model, values, id(if edit)}
   'model' = page key (e.g. 'orders'), never the Odoo model name directly.

6. LINE ITEMS — for orders/invoices/purchases with line items, use
   separate actions: 'line_add', 'line_update', 'line_delete'
   (see LINE ITEMS section below)

═══════════════════════════════════════════════════════════════════
STEP 1 — DETECT INTENT
═══════════════════════════════════════════════════════════════════
Analyse the description and decide:
  • Which Odoo models? (sale.order, account.move, purchase.order,
    hr.employee, res.partner, product.template, account.payment, etc.)
  • PORTAL app? Triggers: "customer portal", "vendor portal", "my orders",
    "my invoices", "portal user"
  • INTERNAL app? Triggers: "dashboard", "management", "ERP", "admin",
    "business suite", "ManageSphere"
  • Pages/modules needed?
  • CRUD actions? (view, create, edit, delete, approve, pay)

STEP 2 — Call odoo_manage_webapp(action='create', ...) immediately.

═══════════════════════════════════════════════════════════════════
STEP 3 — RUNTIME GLOBALS
═══════════════════════════════════════════════════════════════════
  React, ReactDOM             — React 18 globals
  useState, useEffect, useRef, useCallback, useMemo — global shorthands
  window.odoo.fetch(params)   — POST to data_code Python, returns JSON
  window.odoo.portal          — {uid, name, partner_id, is_portal, is_admin}
  Chart                       — Chart.js 4.x (no import needed)

PORTAL USER AWARENESS:
  window.odoo.portal contains the logged-in Odoo user.
  In data_code Python: portal_uid, portal_partner_id, portal_name injected.
  ALWAYS filter portal data:
    domain = [('partner_id','=',portal_partner_id)] if portal_partner_id else []

NEVER use localStorage — ALL data from window.odoo.fetch() / Odoo ORM.

═══════════════════════════════════════════════════════════════════
TEMPLATE A — FULL BUSINESS MANAGEMENT PORTAL
Use for: "business portal", "management app", "ERP", "ManageSphere",
         "customer portal", "vendor portal", "business suite"
═══════════════════════════════════════════════════════════════════

DESIGN RULES:
  Shell:       style={{background:'#0f172a',minHeight:'100vh',color:'#e2e8f0',fontFamily:"'DM Sans',system-ui,sans-serif"}}
  Sidebar:     background:'#0a0f1e', borderRight:'1px solid #1e293b', width:220
  Cards:       background:'#1e293b', border:'1px solid #334155', borderRadius:12, padding:20
  Primary btn: background:'#6366f1', color:'#fff', borderRadius:8, padding:'8px 18px', fontWeight:600
  Table head:  background:'#0f172a', color:'#64748b', fontSize:10, textTransform:'uppercase'
  Table row:   borderBottom:'1px solid #1e293b', color:'#cbd5e1'
  Input:       background:'#0f172a', border:'1px solid #334155', color:'#e2e8f0', borderRadius:8, padding:'8px 12px'
  Ghost btn:   border:'1px solid #334155', background:'transparent', color:'#94a3b8', borderRadius:6
  Toast:       position fixed, bottom 24 right 24, borderRadius:10, fontWeight:600, zIndex:100
  Overlay:     position fixed, inset 0, background rgba(0,0,0,.7), zIndex:50
  Modal:       background:'#1e293b', border:'1px solid #334155', borderRadius:16, maxWidth:600

STATUS BADGE COLORS:
  draft/pending  → {bg:'#1e293b', fg:'#94a3b8'}
  sale/confirmed → {bg:'#1e3a5f', fg:'#93c5fd'}
  done/delivered → {bg:'#064e3b', fg:'#6ee7b7'}
  cancel/refused → {bg:'#450a0a', fg:'#fca5a5'}
  overdue        → {bg:'#451a03', fg:'#fcd34d'}
  paid           → {bg:'#064e3b', fg:'#6ee7b7'}
  not_paid       → {bg:'#451a03', fg:'#fcd34d'}
  in_payment     → {bg:'#1e1b4b', fg:'#a5b4fc'}

══════════════════════════════════════════════════════════════
JSX FULL STRUCTURE — COPY THIS EXACTLY
══════════════════════════════════════════════════════════════

function App() {{
  const [page, setPage]         = useState('dashboard');
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(true);
  const [toast, setToast]       = useState(null);
  const [modal, setModal]       = useState(null);
  const [search, setSearch]     = useState('');
  const [filter, setFilter]     = useState('all');
  const [sideOpen, setSideOpen] = useState(true);
  const [saving, setSaving]     = useState(false);
  const portal = window.odoo.portal || {{}};

  // ─── FIX for "types one letter then stops" bug ───────────────────
  // ALL form state lives in a ref — never in React state.
  // Inputs use defaultValue (uncontrolled) + write to ref on change.
  // This means zero re-renders while typing → no focus loss ever.
  const formRef = useRef({{}});
  // lineItems ref for line-item editing inside a detail modal
  const lineItemsRef = useRef([]);

  const showToast = (msg, kind='success') => {{
    setToast({{msg,kind}}); setTimeout(()=>setToast(null), 3200);
  }};

  const load = async (pg=page, extra={{}}) => {{
    setLoading(true); setData(null);
    try {{
      const d = await window.odoo.fetch({{page:pg, search, filter, ...extra}});
      setData(d);
    }} catch(e) {{ showToast(e.message,'error'); }}
    finally {{ setLoading(false); }}
  }};
  useEffect(() => {{ load(); }}, [page, filter]);

  // ── FIELD DEFINITIONS — single source of truth ──────────────────
  // Keys MUST match data_code FIELD_MAP exactly.
  const FIELD_DEFS = {{
    contacts:  [{{f:'name',l:'Name',t:'text',req:true}},{{f:'email',l:'Email',t:'email'}},
                {{f:'phone',l:'Phone',t:'text'}},{{f:'street',l:'Street',t:'text'}},
                {{f:'city',l:'City',t:'text'}},{{f:'comment',l:'Notes',t:'textarea'}}],
    customers: [{{f:'name',l:'Name',t:'text',req:true}},{{f:'email',l:'Email',t:'email'}},
                {{f:'phone',l:'Phone',t:'text'}},{{f:'street',l:'Street',t:'text'}},
                {{f:'city',l:'City',t:'text'}},{{f:'comment',l:'Notes',t:'textarea'}}],
    orders:    [{{f:'state',l:'Status',t:'select',opts:[{{v:'draft',l:'Quotation'}},{{v:'sale',l:'Confirmed'}},{{v:'done',l:'Done'}},{{v:'cancel',l:'Cancelled'}}]}},
                {{f:'note',l:'Notes',t:'textarea'}}],
    purchases: [{{f:'state',l:'Status',t:'select',opts:[{{v:'draft',l:'Draft'}},{{v:'purchase',l:'Confirmed'}},{{v:'done',l:'Done'}},{{v:'cancel',l:'Cancelled'}}]}},
                {{f:'notes',l:'Notes',t:'textarea'}}],
    products:  [{{f:'name',l:'Name',t:'text',req:true}},{{f:'list_price',l:'Sale Price',t:'number'}},
                {{f:'standard_price',l:'Cost',t:'number'}},
                {{f:'type',l:'Type',t:'select',opts:[{{v:'product',l:'Storable'}},{{v:'consu',l:'Consumable'}},{{v:'service',l:'Service'}}]}},
                {{f:'description',l:'Description',t:'textarea'}}],
    invoices:  [{{f:'payment_state',l:'Payment',t:'select',opts:[{{v:'not_paid',l:'Unpaid'}},{{v:'in_payment',l:'In Payment'}},{{v:'paid',l:'Paid'}}]}}],
    employees: [{{f:'name',l:'Full Name',t:'text',req:true}},{{f:'job_title',l:'Job Title',t:'text'}},
                {{f:'work_email',l:'Work Email',t:'email'}},{{f:'work_phone',l:'Work Phone',t:'text'}}],
    projects:  [{{f:'name',l:'Name',t:'text',req:true}},{{f:'description',l:'Description',t:'textarea'}}],
    tasks:     [{{f:'name',l:'Task Name',t:'text',req:true}},{{f:'description',l:'Description',t:'textarea'}}],
  }};

  const getFormFields = (model) => FIELD_DEFS[model] || FIELD_DEFS.customers;

  // Only copies FIELD_DEFS keys — never invalid fields like amount_total
  const pickFormValues = (model, rec) => {{
    const out = {{}};
    getFormFields(model).forEach(fd => {{ if (rec[fd.f] !== undefined) out[fd.f] = rec[fd.f]; }});
    return out;
  }};

  // ── CRUD helpers ────────────────────────────────────────────────
  const openCreate = (model) => {{
    formRef.current = {{}};
    lineItemsRef.current = [];
    setModal({{type:'create', model}});
  }};

  const openEdit = (model, rec) => {{
    // ⚠ CRITICAL: use pickFormValues, NEVER spread entire rec
    formRef.current = pickFormValues(model, rec);
    lineItemsRef.current = rec.lines ? rec.lines.map(l => ({{...l}})) : [];
    setModal({{type:'edit', model, rec}});
  }};

  const openView = (model, rec) => {{
    lineItemsRef.current = rec.lines ? rec.lines.map(l => ({{...l}})) : [];
    setModal({{type:'view', model, rec}});
  }};

  const closeModal = () => {{
    setModal(null);
    formRef.current = {{}};
    lineItemsRef.current = [];
  }};

  const handleSave = async () => {{
    setSaving(true);
    try {{
      const isEdit = modal.type === 'edit';
      // Read from ref — never from state
      const values = {{...formRef.current}};
      const d = await window.odoo.fetch({{
        action: isEdit ? 'write' : 'create',
        model:  modal.model,
        values,
        ...(isEdit ? {{id: modal.rec.id}} : {{}}),
      }});
      if (d.error) throw new Error(d.error);
      showToast(isEdit ? 'Updated ✓' : 'Created ✓');
      closeModal(); load();
    }} catch(e) {{ showToast(e.message, 'error'); }}
    finally {{ setSaving(false); }}
  }};

  const handleDelete = async (model, id, name) => {{
    if (!confirm('Delete "' + name + '"?')) return;
    try {{
      const d = await window.odoo.fetch({{action:'unlink', model, id}});
      if (d.error) throw new Error(d.error);
      showToast('Deleted ✓'); load();
    }} catch(e) {{ showToast(e.message, 'error'); }}
  }};

  // ── LINE ITEM helpers (for orders/invoices/purchases) ───────────
  // These call Python with action='line_add'/'line_update'/'line_delete'
  const handleLineAdd = async (orderId, orderModel, lineData) => {{
    try {{
      const d = await window.odoo.fetch({{
        action: 'line_add', model: orderModel,
        id: orderId, values: lineData,
      }});
      if (d.error) throw new Error(d.error);
      showToast('Line added ✓');
      // reload detail
      load(page, {{detail_id: orderId}});
    }} catch(e) {{ showToast(e.message, 'error'); }}
  }};

  const handleLineUpdate = async (orderId, orderModel, lineId, lineData) => {{
    try {{
      const d = await window.odoo.fetch({{
        action: 'line_update', model: orderModel,
        id: orderId, line_id: lineId, values: lineData,
      }});
      if (d.error) throw new Error(d.error);
      showToast('Line updated ✓');
      load(page, {{detail_id: orderId}});
    }} catch(e) {{ showToast(e.message, 'error'); }}
  }};

  const handleLineDelete = async (orderId, orderModel, lineId) => {{
    if (!confirm('Remove this line?')) return;
    try {{
      const d = await window.odoo.fetch({{
        action: 'line_delete', model: orderModel,
        id: orderId, line_id: lineId,
      }});
      if (d.error) throw new Error(d.error);
      showToast('Line removed ✓');
      load(page, {{detail_id: orderId}});
    }} catch(e) {{ showToast(e.message, 'error'); }}
  }};

  // ... pages, nav, modal, toast render
}}

══════════════════════════════════════════════════════════════
CRUD MODAL — USE THIS PATTERN EXACTLY (fixes input focus bug)
══════════════════════════════════════════════════════════════

function CrudModal({{modal, formRef, getFormFields, onClose, onSave, saving}}) {{
  if (!modal) return null;
  const fields  = getFormFields(modal.model);
  const isView  = modal.type === 'view';
  const isEdit  = modal.type === 'edit';
  const recId   = modal.rec?.id ?? 'new';

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.7)',zIndex:50,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div style={{background:'#1e293b',border:'1px solid #334155',borderRadius:16,padding:28,width:'100%',maxWidth:540,maxHeight:'85vh',overflowY:'auto'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:20}}>
          <h3 style={{color:'#e2e8f0',margin:0}}>
            {{isView ? 'View' : isEdit ? 'Edit' : 'Create'}} {{modal.model}}
          </h3>
          <button onClick={{onClose}} style={{background:'none',border:'none',color:'#94a3b8',fontSize:20,cursor:'pointer'}}>✕</button>
        </div>

        {{fields.map(fd => (
          <div key={{fd.f}} style={{marginBottom:14}}>
            <label style={{display:'block',color:'#94a3b8',fontSize:12,marginBottom:4}}>
              {{fd.l}}{{fd.req ? ' *' : ''}}
            </label>

            {{fd.t === 'select' ? (
              // Select: use defaultValue on <select> — same uncontrolled pattern
              <select
                key={{fd.f + '-' + recId}}
                defaultValue={{formRef.current[fd.f] ?? ''}}
                onChange={{e => {{ formRef.current[fd.f] = e.target.value; }}}}
                disabled={{isView}}
                style={{width:'100%',background:'#0f172a',border:'1px solid #334155',color:'#e2e8f0',borderRadius:8,padding:'8px 12px'}}
              >
                <option value=''>— select —</option>
                {{(fd.opts||[]).map(o => <option key={{o.v}} value={{o.v}}>{{o.l}}</option>)}}
              </select>
            ) : fd.t === 'textarea' ? (
              <textarea
                key={{fd.f + '-' + recId}}
                defaultValue={{formRef.current[fd.f] ?? ''}}
                onChange={{e => {{ formRef.current[fd.f] = e.target.value; }}}}
                readOnly={{isView}}
                rows={{3}}
                style={{width:'100%',background:'#0f172a',border:'1px solid #334155',color:'#e2e8f0',borderRadius:8,padding:'8px 12px',resize:'vertical',boxSizing:'border-box'}}
              />
            ) : (
              <input
                key={{fd.f + '-' + recId}}
                type={{fd.t || 'text'}}
                defaultValue={{formRef.current[fd.f] ?? ''}}
                onChange={{e => {{ formRef.current[fd.f] = e.target.value; }}}}
                readOnly={{isView}}
                style={{width:'100%',background:'#0f172a',border:'1px solid #334155',color:'#e2e8f0',borderRadius:8,padding:'8px 12px',boxSizing:'border-box'}}
              />
            )}}
          </div>
        ))}}

        {{!isView && (
          <div style={{display:'flex',justifyContent:'flex-end',gap:10,marginTop:20}}>
            <button onClick={{onClose}} style={{border:'1px solid #334155',background:'transparent',color:'#94a3b8',borderRadius:6,padding:'8px 16px',cursor:'pointer'}}>
              Cancel
            </button>
            <button onClick={{onSave}} disabled={{saving}}
              style={{background:'#6366f1',color:'#fff',border:'none',borderRadius:8,padding:'8px 18px',fontWeight:600,cursor:'pointer',opacity:saving?0.6:1}}>
              {{saving ? 'Saving…' : 'Save'}}
            </button>
          </div>
        )}}
      </div>
    </div>
  );
}}

══════════════════════════════════════════════════════════════
LINE ITEMS MODAL — for sale.order / purchase.order / account.move
══════════════════════════════════════════════════════════════

// LINE ITEM FIELD DEFS per order type:
const LINE_FIELD_DEFS = {{
  orders:    [{{f:'product_id_name',l:'Product',t:'text',req:true}},
              {{f:'product_uom_qty',l:'Qty',t:'number'}},
              {{f:'price_unit',l:'Unit Price',t:'number'}},
              {{f:'name',l:'Description',t:'text'}}],
  purchases: [{{f:'product_id_name',l:'Product',t:'text',req:true}},
              {{f:'product_qty',l:'Qty',t:'number'}},
              {{f:'price_unit',l:'Unit Price',t:'number'}},
              {{f:'name',l:'Description',t:'text'}}],
  invoices:  [{{f:'name',l:'Description',t:'text',req:true}},
              {{f:'quantity',l:'Qty',t:'number'}},
              {{f:'price_unit',l:'Unit Price',t:'number'}}],
}};

// Line items table inside the detail view:
function LineItemsSection({{lines, orderModel, orderId, onAdd, onUpdate, onDelete, isPortal}}) {{
  const lineFormRef = useRef({{}});
  const [editingLine, setEditingLine] = useState(null); // null=closed, 0=new, lineId=edit
  const lineDefs = LINE_FIELD_DEFS[orderModel] || LINE_FIELD_DEFS.orders;

  const openNewLine  = () => {{ lineFormRef.current = {{}}; setEditingLine(0); }};
  const openEditLine = (line) => {{
    lineFormRef.current = {{...line}};
    setEditingLine(line.id);
  }};

  return (
    <div style={{marginTop:20}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:12}}>
        <h4 style={{color:'#94a3b8',margin:0,fontSize:13,textTransform:'uppercase',letterSpacing:'.06em'}}>Order Lines</h4>
        {{!isPortal && (
          <button onClick={{openNewLine}}
            style={{background:'#6366f1',color:'#fff',border:'none',borderRadius:6,padding:'5px 12px',fontSize:12,cursor:'pointer'}}>
            + Add Line
          </button>
        )}}
      </div>

      <table style={{width:'100%',borderCollapse:'collapse',fontSize:13}}>
        <thead>
          <tr style={{background:'#0f172a'}}>
            {{lineDefs.map(fd => <th key={{fd.f}} style={{color:'#64748b',padding:'8px',textAlign:'left',fontSize:11,textTransform:'uppercase'}}>{fd.l}</th>)}}
            <th style={{color:'#64748b',padding:'8px',textAlign:'right',fontSize:11}}>Subtotal</th>
            {{!isPortal && <th></th>}}
          </tr>
        </thead>
        <tbody>
          {{(lines||[]).map(line => (
            <tr key={{line.id}} style={{borderBottom:'1px solid #1e293b'}}>
              <td style={{padding:'8px',color:'#e2e8f0'}}>{{line.product_name || line.name || '—'}}</td>
              <td style={{padding:'8px',color:'#cbd5e1'}}>{{line.qty}}</td>
              <td style={{padding:'8px',color:'#cbd5e1'}}>{{line.price_unit?.toFixed(2)}}</td>
              <td style={{padding:'8px',color:'#93c5fd',textAlign:'right'}}>{{line.subtotal?.toFixed(2)}}</td>
              {{!isPortal && (
                <td style={{padding:'8px',textAlign:'right'}}>
                  <button onClick={{()=>openEditLine(line)}}
                    style={{background:'none',border:'none',color:'#6366f1',cursor:'pointer',marginRight:6,fontSize:12}}>Edit</button>
                  <button onClick={{()=>onDelete(orderId, orderModel, line.id)}}
                    style={{background:'none',border:'none',color:'#ef4444',cursor:'pointer',fontSize:12}}>✕</button>
                </td>
              )}}
            </tr>
          ))}}
        </tbody>
      </table>

      {{editingLine !== null && (
        <div style={{background:'#0f172a',border:'1px solid #334155',borderRadius:10,padding:16,marginTop:12}}>
          <h5 style={{color:'#94a3b8',margin:'0 0 12px',fontSize:12}}>
            {{editingLine === 0 ? 'Add Line' : 'Edit Line'}}
          </h5>
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(160px,1fr))',gap:10}}>
            {{lineDefs.map(fd => (
              <div key={{fd.f}}>
                <label style={{color:'#64748b',fontSize:11,display:'block',marginBottom:3}}>{{fd.l}}</label>
                <input
                  key={{fd.f + '-line-' + editingLine}}
                  type={{fd.t || 'text'}}
                  defaultValue={{lineFormRef.current[fd.f] ?? ''}}
                  onChange={{e => {{ lineFormRef.current[fd.f] = e.target.value; }}}}
                  style={{width:'100%',background:'#1e293b',border:'1px solid #334155',color:'#e2e8f0',borderRadius:6,padding:'6px 10px',boxSizing:'border-box'}}
                />
              </div>
            ))}}
          </div>
          <div style={{display:'flex',gap:8,marginTop:12,justifyContent:'flex-end'}}>
            <button onClick={{()=>setEditingLine(null)}}
              style={{border:'1px solid #334155',background:'transparent',color:'#94a3b8',borderRadius:6,padding:'6px 14px',cursor:'pointer',fontSize:12}}>
              Cancel
            </button>
            <button onClick={{() => {{
                const vals = {{...lineFormRef.current}};
                if (editingLine === 0) onAdd(orderId, orderModel, vals);
                else onUpdate(orderId, orderModel, editingLine, vals);
                setEditingLine(null);
              }}}}
              style={{background:'#6366f1',color:'#fff',border:'none',borderRadius:6,padding:'6px 14px',fontWeight:600,cursor:'pointer',fontSize:12}}>
              Save Line
            </button>
          </div>
        </div>
      )}}
    </div>
  );
}}

PAGES TO BUILD (include all relevant based on description):
  Dashboard   — 6 KPI cards, revenue Chart.js line chart, by-state donut, recent orders table
  Contacts    — searchable table, CRUD modal (res.partner)
  Sales Orders — tabs (All/Quotations/Confirmed/Done/Cancelled), table+detail with line items CRUD
  Invoices    — tabs (All/Draft/Sent/Paid/Overdue), table+detail with line items
  Purchases   — tabs, table+detail with line items CRUD
  Products    — grid cards, search, CRUD (product.template) — no qty_available field
  Analytics   — Chart.js bar (monthly revenue) + doughnut (by status) + horizontal bar (top products)
  Payments    — payment ledger, record payment modal (account.payment)
  HR/Employees — grid cards (hr.employee) — hide from portal users

══════════════════════════════════════════════════════════════
DATA_CODE — FULL UNIVERSAL TEMPLATE
══════════════════════════════════════════════════════════════

```python
try:
    import datetime as _dt
    action = params.get('action')
    page   = params.get('page', 'dashboard')
    search = (params.get('search') or '').strip()
    filt   = (params.get('filter') or 'all').strip()
    is_portal = bool(portal_partner_id)
    pid       = portal_partner_id  # None for staff

    # ── MODEL MAP — page key → Odoo model name ───────────────────
    MODEL_MAP = {{
        'contacts':  'res.partner',
        'customers': 'res.partner',
        'partners':  'res.partner',
        'orders':    'sale.order',
        'sales':     'sale.order',
        'invoices':  'account.move',
        'bills':     'account.move',
        'purchases': 'purchase.order',
        'products':  'product.template',
        'employees': 'hr.employee',
        'payments':  'account.payment',
        'projects':  'project.project',
        'tasks':     'project.task',
    }}

    # ── LINE MODEL MAP — which model stores the order lines ───────
    LINE_MODEL_MAP = {{
        'sale.order':      'sale.order.line',
        'purchase.order':  'purchase.order.line',
        'account.move':    'account.move.line',
    }}

    # ── LINE PARENT FIELD — field linking line to parent ──────────
    LINE_PARENT_FIELD = {{
        'sale.order.line':     'order_id',
        'purchase.order.line': 'order_id',
        'account.move.line':   'move_id',
    }}

    # ── FIELD MAP — form key → real Odoo column ───────────────────
    FIELD_MAP = {{
        'res.partner':         {{'name':'name','email':'email','phone':'phone','street':'street','city':'city','comment':'comment'}},
        'sale.order':          {{'state':'state','note':'note'}},
        'purchase.order':      {{'state':'state','notes':'notes'}},
        'product.template':    {{'name':'name','list_price':'list_price','standard_price':'standard_price','type':'type','description':'description'}},
        'account.move':        {{'payment_state':'payment_state'}},
        'hr.employee':         {{'name':'name','job_title':'job_title','work_email':'work_email','work_phone':'work_phone'}},
        'project.project':     {{'name':'name','description':'description'}},
        'project.task':        {{'name':'name','description':'description'}},
        'account.payment':     {{'amount':'amount','payment_type':'payment_type','memo':'memo'}},
        'sale.order.line':     {{'product_id_name':'product_id','product_uom_qty':'product_uom_qty','price_unit':'price_unit','name':'name'}},
        'purchase.order.line': {{'product_id_name':'product_id','product_qty':'product_qty','price_unit':'price_unit','name':'name'}},
        'account.move.line':   {{'name':'name','quantity':'quantity','price_unit':'price_unit'}},
    }}

    def _crud_values(mn, raw):
        fm    = FIELD_MAP.get(mn, {{}})
        valid = set(env[mn].fields_get().keys())
        out   = {{}}
        for k, v in (raw or {{}}).items():
            real = fm.get(k, k)
            if real in valid and v is not None and v != '':
                # Convert numeric strings
                finfo = env[mn].fields_get().get(real, {{}})
                if finfo.get('type') in ('integer','float','monetary') and isinstance(v, str):
                    try: v = float(v)
                    except: pass
                out[real] = v
        return out

    def _resolve_product_id(mn, vals):
        # Convert product_id_name text to many2one id for line creation.
        if 'product_id' in vals and isinstance(vals['product_id'], str):
            name = vals['product_id'].strip()
            prod = env['product.product'].search([('name','ilike',name)], limit=1)
            if prod: vals['product_id'] = prod.id
            else:
                prod_t = env['product.template'].search([('name','ilike',name)], limit=1)
                if prod_t and prod_t.product_variant_id:
                    vals['product_id'] = prod_t.product_variant_id.id
                else: raise ValueError(f"Product not found: {{name}}")
        return vals

    # ════════════════════════════════════════════════════════════
    # CRUD — CREATE
    # ════════════════════════════════════════════════════════════
    if action == 'create':
        mk = params.get('model', '')
        mn = MODEL_MAP.get(mk)
        if not mn:
            result = {{'error': f'Unknown model key: "{{mk}}". Add to MODEL_MAP.'}}
        else:
            vals = _crud_values(mn, params.get('values'))
            if not vals:
                result = {{'error': f'No valid fields for {{mn}}. Got: {{list((params.get("values") or {{}}).keys())}}'}}
            else:
                if mn == 'res.partner' and 'customer_rank' not in vals:
                    vals['customer_rank'] = 1
                rec = env[mn].create(vals)
                result = {{'ok': True, 'id': rec.id}}

    # ════════════════════════════════════════════════════════════
    # CRUD — WRITE
    # ════════════════════════════════════════════════════════════
    elif action == 'write':
        mk  = params.get('model', '')
        mn  = MODEL_MAP.get(mk)
        rid = int(params.get('id') or 0)
        if not mn or not rid:
            result = {{'error': 'model and id required'}}
        else:
            rec = env[mn].browse(rid)
            if not rec.exists():
                result = {{'error': f'Record {{rid}} not found'}}
            elif is_portal and hasattr(rec,'partner_id') and rec.partner_id.id != pid:
                result = {{'error': 'Access denied'}}
            else:
                vals = _crud_values(mn, params.get('values'))
                if vals: rec.write(vals)
                result = {{'ok': True}}

    # ════════════════════════════════════════════════════════════
    # CRUD — DELETE
    # ════════════════════════════════════════════════════════════
    elif action == 'unlink':
        mk  = params.get('model', '')
        mn  = MODEL_MAP.get(mk)
        rid = int(params.get('id') or 0)
        if not mn or not rid:
            result = {{'error': 'model and id required'}}
        else:
            rec = env[mn].browse(rid)
            if not rec.exists():
                result = {{'error': f'Record {{rid}} not found'}}
            elif is_portal and hasattr(rec,'partner_id') and rec.partner_id.id != pid:
                result = {{'error': 'Access denied'}}
            else:
                rec.unlink()
                result = {{'ok': True}}

    # ════════════════════════════════════════════════════════════
    # LINE ITEMS — ADD
    # ════════════════════════════════════════════════════════════
    elif action == 'line_add':
        mk  = params.get('model', '')
        mn  = MODEL_MAP.get(mk)
        rid = int(params.get('id') or 0)
        if not mn or not rid:
            result = {{'error': 'model and id required for line_add'}}
        else:
            lm  = LINE_MODEL_MAP.get(mn)
            lpf = LINE_PARENT_FIELD.get(lm)
            if not lm:
                result = {{'error': f'No line model defined for {{mn}}'}}
            else:
                vals = _crud_values(lm, params.get('values'))
                vals = _resolve_product_id(lm, vals)
                vals[lpf] = rid
                # Defaults for missing required fields
                if lm == 'sale.order.line' and 'product_uom_qty' not in vals:
                    vals['product_uom_qty'] = 1.0
                if lm == 'purchase.order.line' and 'product_qty' not in vals:
                    vals['product_qty'] = 1.0
                if lm == 'account.move.line' and 'quantity' not in vals:
                    vals['quantity'] = 1.0
                line = env[lm].create(vals)
                result = {{'ok': True, 'line_id': line.id}}

    # ════════════════════════════════════════════════════════════
    # LINE ITEMS — UPDATE
    # ════════════════════════════════════════════════════════════
    elif action == 'line_update':
        mk      = params.get('model', '')
        mn      = MODEL_MAP.get(mk)
        line_id = int(params.get('line_id') or 0)
        if not mn or not line_id:
            result = {{'error': 'model and line_id required for line_update'}}
        else:
            lm   = LINE_MODEL_MAP.get(mn)
            if not lm:
                result = {{'error': f'No line model defined for {{mn}}'}}
            else:
                vals = _crud_values(lm, params.get('values'))
                vals = _resolve_product_id(lm, vals)
                line = env[lm].browse(line_id)
                if not line.exists():
                    result = {{'error': f'Line {{line_id}} not found'}}
                else:
                    line.write(vals)
                    result = {{'ok': True}}

    # ════════════════════════════════════════════════════════════
    # LINE ITEMS — DELETE
    # ════════════════════════════════════════════════════════════
    elif action == 'line_delete':
        mk      = params.get('model', '')
        mn      = MODEL_MAP.get(mk)
        line_id = int(params.get('line_id') or 0)
        if not mn or not line_id:
            result = {{'error': 'model and line_id required for line_delete'}}
        else:
            lm = LINE_MODEL_MAP.get(mn)
            if not lm:
                result = {{'error': f'No line model defined for {{mn}}'}}
            else:
                line = env[lm].browse(line_id)
                if not line.exists():
                    result = {{'error': f'Line {{line_id}} not found'}}
                else:
                    line.unlink()
                    result = {{'ok': True}}

    # ════════════════════════════════════════════════════════════
    # DASHBOARD
    # ════════════════════════════════════════════════════════════
    elif page == 'dashboard':
        so_dom  = [('partner_id','=',pid)] if is_portal else []
        inv_dom = ([('partner_id','=',pid)] if is_portal else []) + [('move_type','in',['out_invoice','out_refund'])]
        orders   = env['sale.order'].search_read(so_dom,['name','partner_id','amount_total','state','date_order'],order='date_order desc',limit=200)
        try: invoices = env['account.move'].search_read(inv_dom,['amount_total','payment_state','invoice_date_due'],limit=200)
        except: invoices = []
        confirmed = [o for o in orders if o['state'] in ['sale','done']]
        total_rev = sum(o['amount_total'] or 0 for o in confirmed)
        avg_ord   = round(total_rev/len(confirmed),2) if confirmed else 0
        paid_inv  = sum(1 for i in invoices if i.get('payment_state')=='paid')
        coll_rate = round(paid_inv/len(invoices)*100,1) if invoices else 0
        pending   = sum(1 for i in invoices if i.get('payment_state') not in ['paid','reversed'])
        monthly   = {{}}
        for o in confirmed:
            dt = o.get('date_order'); key = dt.strftime('%b %y') if hasattr(dt,'strftime') else str(dt)[:7]
            monthly[key] = round(monthly.get(key,0)+(o['amount_total'] or 0),2)
        try:
            sr = env['sale.order']._read_group(domain=so_dom,groupby=['state'],aggregates=['id:count'])
            by_state = [{{'state':r[0] or 'unknown','count':r[1] or 0}} for r in sr]
        except: by_state = []
        result = {{
            'kpis':{{'total_revenue':round(total_rev,2),'order_count':len(orders),
                    'pending_invoices':pending,
                    'active_customers':env['res.partner'].search_count([('customer_rank','>',0)]) if not is_portal else 1,
                    'avg_order':avg_ord,'collection_rate':coll_rate}},
            'monthly_revenue':[{{'label':k,'value':v}} for k,v in list(monthly.items())[-6:]],
            'by_state':by_state,
            'recent_orders':[{{'id':o['id'],'name':o.get('name',''),
                'partner':(o.get('partner_id') or [0,''])[1],
                'date':o['date_order'].strftime('%d %b %Y') if hasattr(o.get('date_order'),'strftime') else str(o.get('date_order',''))[:10],
                'amount':round(o.get('amount_total') or 0,2),'state':o.get('state','')}} for o in orders[:5]],
        }}

    # ════════════════════════════════════════════════════════════
    # ORDERS — with full line items in detail
    # ════════════════════════════════════════════════════════════
    elif page == 'orders':
        dom = [('partner_id','=',pid)] if is_portal else []
        if filt != 'all': dom += [('state','=',filt)]
        if search: dom += ['|',('name','ilike',search),('partner_id.name','ilike',search)]
        detail_id = params.get('detail_id')
        if detail_id:
            # Return single order with full line items
            order = env['sale.order'].browse(int(detail_id))
            lines_data = []
            for ln in order.order_line:
                lines_data.append({{
                    'id': ln.id,
                    'product_name': ln.product_id.name if ln.product_id else '',
                    'product_id_name': ln.product_id.name if ln.product_id else '',
                    'name': ln.name or '',
                    'qty': ln.product_uom_qty,
                    'price_unit': ln.price_unit,
                    'subtotal': ln.price_subtotal,
                    'tax': [(t.name) for t in ln.tax_id],
                }})
            result = {{'record': {{
                'id': order.id, 'name': order.name,
                'partner': order.partner_id.name if order.partner_id else '',
                'date': str(order.date_order or '')[:10],
                'amount': round(order.amount_total or 0,2),
                'state': order.state,
                'lines': lines_data,
            }}}}
        else:
            rows = env['sale.order'].search_read(dom,['id','name','partner_id','date_order','amount_total','state','order_line'],order='date_order desc',limit=100)
            result = {{'records':[{{'id':o['id'],'name':o.get('name',''),
                'partner':(o.get('partner_id') or [0,''])[1],
                'date':str(o.get('date_order',''))[:10],
                'amount':round(o.get('amount_total') or 0,2),
                'state':o.get('state',''),'line_count':len(o.get('order_line') or [])}} for o in rows]}}

    # ════════════════════════════════════════════════════════════
    # PURCHASES — with line items
    # ════════════════════════════════════════════════════════════
    elif page == 'purchases':
        if is_portal:
            result = {{'records':[]}}
        else:
            dom = []
            if filt != 'all': dom += [('state','=',filt)]
            if search: dom += ['|',('name','ilike',search),('partner_id.name','ilike',search)]
            detail_id = params.get('detail_id')
            if detail_id:
                po = env['purchase.order'].browse(int(detail_id))
                lines_data = []
                for ln in po.order_line:
                    lines_data.append({{
                        'id': ln.id,
                        'product_name': ln.product_id.name if ln.product_id else '',
                        'product_id_name': ln.product_id.name if ln.product_id else '',
                        'name': ln.name or '',
                        'qty': ln.product_qty,
                        'price_unit': ln.price_unit,
                        'subtotal': ln.price_subtotal,
                    }})
                result = {{'record': {{
                    'id': po.id, 'name': po.name,
                    'partner': po.partner_id.name if po.partner_id else '',
                    'date': str(po.date_order or '')[:10],
                    'amount': round(po.amount_total or 0,2),
                    'state': po.state, 'lines': lines_data,
                }}}}
            else:
                rows = env['purchase.order'].search_read(dom,['id','name','partner_id','date_order','amount_total','state'],order='date_order desc',limit=100)
                result = {{'records':[{{'id':p['id'],'name':p.get('name',''),
                    'partner':(p.get('partner_id') or [0,''])[1],
                    'date':str(p.get('date_order',''))[:10],
                    'amount':round(p.get('amount_total') or 0,2),
                    'state':p.get('state','')}} for p in rows]}}

    # ════════════════════════════════════════════════════════════
    # INVOICES — with line items
    # ════════════════════════════════════════════════════════════
    elif page == 'invoices':
        dom = ([('partner_id','=',pid)] if is_portal else []) + [('move_type','in',['out_invoice','out_refund'])]
        if filt == 'paid':   dom += [('payment_state','=','paid')]
        elif filt == 'posted': dom += [('state','=','posted'),('payment_state','!=','paid')]
        elif filt == 'draft':  dom += [('state','=','draft')]
        if search: dom += [('name','ilike',search)]
        detail_id = params.get('detail_id')
        if detail_id:
            inv = env['account.move'].browse(int(detail_id))
            lines_data = []
            for ln in inv.invoice_line_ids:
                lines_data.append({{
                    'id': ln.id,
                    'name': ln.name or '',
                    'product_name': ln.product_id.name if ln.product_id else '',
                    'qty': ln.quantity,
                    'price_unit': ln.price_unit,
                    'subtotal': ln.price_subtotal,
                }})
            result = {{'record': {{
                'id': inv.id, 'name': inv.name,
                'partner': inv.partner_id.name if inv.partner_id else '',
                'date': str(inv.invoice_date or '')[:10],
                'due': str(inv.invoice_date_due or '')[:10],
                'amount': round(inv.amount_total or 0,2),
                'payment_state': inv.payment_state,
                'state': inv.state, 'lines': lines_data,
            }}}}
        else:
            rows = env['account.move'].search_read(dom,['id','name','partner_id','invoice_date','invoice_date_due','amount_total','payment_state','state'],order='invoice_date desc',limit=100)
            today = _dt.date.today()
            result = {{'records':[{{'id':i['id'],'name':i.get('name',''),
                'partner':(i.get('partner_id') or [0,''])[1],
                'date':str(i.get('invoice_date',''))[:10],'due':str(i.get('invoice_date_due',''))[:10],
                'amount':round(i.get('amount_total') or 0,2),'payment_state':i.get('payment_state',''),
                'state':i.get('state',''),
                'overdue':bool(i.get('invoice_date_due') and i.get('payment_state')!='paid'
                    and hasattr(i.get('invoice_date_due'),'year') and i['invoice_date_due']<today)}} for i in rows]}}

    # ════════════════════════════════════════════════════════════
    # CUSTOMERS / CONTACTS
    # ════════════════════════════════════════════════════════════
    elif page in ('customers','contacts','partners'):
        if is_portal:
            result = {{'records':[]}}
        else:
            dom = [('customer_rank','>',0)]
            if filt == 'supplier': dom = [('supplier_rank','>',0)]
            if search: dom += ['|',('name','ilike',search),('email','ilike',search)]
            rows = env['res.partner'].search_read(dom,['id','name','email','phone','city','country_id'],order='name asc',limit=80)
            result = {{'records':[{{'id':r['id'],'name':r.get('name',''),'email':r.get('email','') or '',
                'phone':r.get('phone','') or '','city':r.get('city','') or '',
                'country':(r.get('country_id') or [0,''])[1]}} for r in rows]}}

    # ════════════════════════════════════════════════════════════
    # PRODUCTS — NOTE: NO qty_available here (wrong model)
    # ════════════════════════════════════════════════════════════
    elif page == 'products':
        dom = [('active','=',True)]
        if search: dom += ['|',('name','ilike',search),('categ_id.name','ilike',search)]
        # ⚠ NEVER include qty_available — it's on product.product, not product.template
        rows = env['product.template'].search_read(
            dom,['id','name','categ_id','list_price','standard_price','type','sale_ok','purchase_ok'],
            order='name asc',limit=80)
        result = {{'records':[{{'id':p['id'],'name':p.get('name',''),
            'categ':(p.get('categ_id') or [0,''])[1],
            'price':round(p.get('list_price') or 0,2),
            'cost':round(p.get('standard_price') or 0,2),
            'type':p.get('type','product'),
            'sale_ok':p.get('sale_ok',True),'purchase_ok':p.get('purchase_ok',True)}} for p in rows]}}

    # ════════════════════════════════════════════════════════════
    # EMPLOYEES
    # ════════════════════════════════════════════════════════════
    elif page == 'employees':
        if is_portal:
            result = {{'records':[]}}
        else:
            dom = [('active','=',True)]
            if search: dom += ['|',('name','ilike',search),('department_id.name','ilike',search)]
            rows = env['hr.employee'].search_read(dom,['id','name','job_title','department_id','work_email','work_phone'],order='name asc',limit=80)
            result = {{'records':[{{'id':e['id'],'name':e.get('name',''),'job':e.get('job_title',''),
                'dept':(e.get('department_id') or [0,''])[1],'email':e.get('work_email','') or '',
                'phone':e.get('work_phone','') or ''}} for e in rows]}}

    # ════════════════════════════════════════════════════════════
    # PAYMENTS
    # ════════════════════════════════════════════════════════════
    elif page == 'payments':
        dom = [('partner_id','=',pid)] if is_portal else []
        if search: dom += [('name','ilike',search)]
        try:
            rows = env['account.payment'].search_read(dom,['id','name','partner_id','amount','date','payment_type','journal_id','state'],order='date desc',limit=100)
            result = {{'records':[{{'id':p['id'],'name':p.get('name',''),
                'partner':(p.get('partner_id') or [0,''])[1],
                'amount':round(p.get('amount') or 0,2),'date':str(p.get('date',''))[:10],
                'type':p.get('payment_type',''),'journal':(p.get('journal_id') or [0,''])[1],
                'state':p.get('state','')}} for p in rows]}}
        except Exception as e: result = {{'records':[], 'error':str(e)}}

    # ════════════════════════════════════════════════════════════
    # ANALYTICS
    # ════════════════════════════════════════════════════════════
    elif page == 'analytics':
        so_dom = [('partner_id','=',pid),('state','in',['sale','done'])] if is_portal else [('state','in',['sale','done'])]
        try:
            mr = env['sale.order']._read_group(domain=so_dom,groupby=['date_order:month'],aggregates=['amount_total:sum'],order='date_order:month asc',limit=12)
            monthly = [{{'label':r[0].strftime('%b %Y') if r[0] else '?','value':round(r[1] or 0,2)}} for r in mr]
        except: monthly = []
        try:
            sr = env['sale.order']._read_group(domain=[('partner_id','=',pid)] if is_portal else [],groupby=['state'],aggregates=['id:count'])
            by_state = [{{'state':r[0] or 'unknown','count':r[1] or 0}} for r in sr]
        except: by_state = []
        top_products = []
        try:
            pr = env['sale.order.line']._read_group(
                domain=[('order_id.state','in',['sale','done'])] + ([('order_id.partner_id','=',pid)] if is_portal else []),
                groupby=['product_id'],aggregates=['price_subtotal:sum'],order='price_subtotal:sum desc',limit=10)
            top_products = [{{'name':r[0].name if r[0] else 'Unknown','value':round(r[1] or 0,2)}} for r in pr]
        except: pass
        result = {{'monthly_revenue':monthly,'by_state':by_state,'top_products':top_products}}

    else:
        result = {{'error':f'Unknown page: {{page}}'}}

except Exception as e:
    import traceback as _tb
    result = {{'error':str(e),'traceback':_tb.format_exc()}}
```

═══════════════════════════════════════════════════════════════════
TEMPLATE B — SIMPLE FOCUSED APP
Use for: "show my invoices", "product catalogue", single model apps
═══════════════════════════════════════════════════════════════════
Build a focused single-model app. Apply same portal filtering, dark theme,
uncontrolled-input CRUD pattern, and line-items section where appropriate.

After creating the app, output the URL from the tool response.
""" + _SYSTEM_PROMPT


_PROMPT_CREATE_REPORT = """Create an Odoo QWeb report for: {description}

═══════════════════════════════════════════════════════════
STEP 1 — DISCOVER FIELDS FIRST (works for any Odoo version)
═══════════════════════════════════════════════════════════
Call odoo_get_fields(model=target_model) to get EXACT field names.
Never guess — the live DB has the answer for your Odoo version + custom fields.

Also check related models:
  odoo_get_fields(model="sale.order.line")   # order lines
  odoo_get_fields(model="account.move.line") # invoice lines
  odoo_get_fields(model="stock.move")        # delivery lines

═══════════════════════════════════════════════════════════
STEP 2 — CHOOSE LAYOUT
═══════════════════════════════════════════════════════════
  layout='external'  → web.external_layout
                       Company logo + address in header, page number in footer
                       USE FOR: invoices, quotes, delivery slips, customer docs

  layout='internal'  → web.internal_layout
                       Minimal company name header only, no footer
                       USE FOR: warehouse picks, internal transfers, internal reports

  layout='minimal'   → web.minimal_layout
                       Completely blank — no header, no footer
                       USE FOR: ID cards, badges, labels, certificates
                       Add all styling via custom_css field

═══════════════════════════════════════════════════════════
STEP 3 — WRITE TEMPLATE (mandatory QWeb rules)
═══════════════════════════════════════════════════════════

CONTEXT VARIABLES (always available):
  docs        → all selected records
  doc         → current record (inside t-foreach="docs" t-as="doc")
  res_company → current company  ← use this, NEVER "company" (KeyError)
  user        → user printing the report

t-field vs t-esc rule:
  t-field → for monetary/date/float/html (formatted display)
             ONLY on <span> <div> <p> <h1-h6> <li> <strong>
             NEVER on <td> <th> <tr> → AssertionError crash
  t-esc   → for char/text/name (plain text) — safe on any element

  CORRECT: <td><span t-field="doc.amount_total"/></td>
  CORRECT: <td t-esc="doc.name"/>
  WRONG:   <td t-field="doc.amount_total"/>   ← crash

═══════════════════════════════════════════════════════════
STEP 4 — CALL odoo_manage_report(action='create', ...)
═══════════════════════════════════════════════════════════

PATTERN — info table:
  <table class="table table-sm table-bordered">
    <tbody>
      <tr><th style="width:35%">Customer</th>
          <td t-esc="doc.partner_id.display_name"/></tr>
      <tr><th>Status</th>
          <td t-esc="doc.state"/></tr>
      <tr><th>Total</th>
          <td><strong><span t-field="doc.amount_total"/></strong></td></tr>
    </tbody>
  </table>

PATTERN — lines table:
  <table class="table table-sm table-bordered mt-3">
    <thead class="table-light">
      <tr><th>Product</th><th class="text-end">Qty</th>
          <th class="text-end">Price</th><th class="text-end">Subtotal</th></tr>
    </thead>
    <tbody>
      <t t-foreach="doc.order_line" t-as="line">
        <tr>
          <td t-esc="line.product_id.display_name"/>
          <td class="text-end" t-esc="line.product_uom_qty"/>
          <td class="text-end"><span t-field="line.price_unit"/></td>
          <td class="text-end"><span t-field="line.price_subtotal"/></td>
        </tr>
      </t>
    </tbody>
    <tfoot>
      <tr><td colspan="3" class="text-end"><strong>Total</strong></td>
          <td class="text-end"><strong><span t-field="doc.amount_total"/></strong></td></tr>
    </tfoot>
  </table>

PATTERN — ID card / badge (use layout='minimal' + custom_css):
  template_html:
    <div class="id-card">
      <h2 t-esc="doc.display_name"/>
      <table class="table table-sm table-borderless">
        <tr t-if="doc.email"><th>Email</th><td t-esc="doc.email"/></tr>
        <tr t-if="doc.phone"><th>Phone</th><td t-esc="doc.phone"/></tr>
      </table>
    </div>
  custom_css:
    .id-card { border: 2px solid #333; padding: 20px; border-radius: 8px;
                width: 85mm; min-height: 54mm; }
    h2 { font-size: 16pt; margin-bottom: 8px; }
    .table td, .table th { padding: 4px 8px; font-size: 10pt; }
"""

REPORT_PROMPT_ENTRY = {
    "name": "create_report",
    "description": "Create an Odoo 19 QWeb PDF/HTML report for any model",
    "arguments": [
        {"name": "description", "description": "What the report should show", "required": True}
    ],
    "_text": _PROMPT_CREATE_REPORT,
}


_PROMPT_CREATE_SNIPPET = """\
Create an Odoo 19 website snippet (drag-and-drop building block) for: {{description}}

Call odoo_manage_snippet(action='create', ...) then odoo_manage_snippet(action='install', ...)

═══════════════════════════════════════════════════════════════════
ODOO 19 SNIPPET ARCHITECTURE
═══════════════════════════════════════════════════════════════════

STRUCTURE:
  module_name/
  ├── __manifest__.py
  ├── static/src/
  │   ├── img/snippets_thumbs/s_name.svg    ← panel thumbnail
  │   ├── snippets/s_name/
  │   │   ├── 000.scss                      ← styles
  │   │   └── 000.js                        ← interactions (optional)
  │   └── website_builder/
  │       └── s_name_option_plugin.js       ← builder options (optional)
  └── views/snippets/
      ├── s_name.xml                        ← QWeb template
      └── snippets.xml                      ← registration in builder

TEMPLATE_XML RULES
══════════════════
ROOT: always <section> with these exact attributes:
  <section class="s_name o_colored_level"
           data-name="Human Name"
           data-snippet="s_name">

LAYOUT — Bootstrap 5 grid:
  <div class="container">
    <div class="row align-items-center">
      <div class="col-lg-6">...</div>
    </div>
  </div>

EDITABLE AREAS:
  class="oe_editable"   → text/content editable in builder
  class="oe_structure"  → droppable zone for other snippets
  class="oe_img_bg"     → replaceable background image

ODOO SPACING HELPERS (use instead of custom padding):
  pt16, pt32, pt48, pt64, pt80, pt96
  pb16, pb32, pb48, pb64, pb80, pb96

BUTTONS — always Odoo classes:
  <a href="#" class="btn btn-primary btn-lg">Primary</a>
  <a href="#" class="btn btn-outline-primary">Outline</a>

ICONS — Font Awesome (always available):
  <i class="fa fa-star fa-2x"/>

DO NOT:
  - Use id attributes (snippets can appear multiple times)
  - Nest <section> inside <section>
  - Use external CDN links

SCSS RULES
══════════
  .s_name {
    // Always root with snippet class
    // CSS variables: var(--bs-primary) var(--color-headings) var(--bs-body-color)
    .s_name_card {
      // Prefix ALL sub-classes with snippet class
      border-radius: 8px;
      transition: transform 0.2s ease;
      &:hover { transform: translateY(-4px); }
    }
  }

NAMING CONVENTIONS (CRITICAL)
══════════════════════════════
  technical_name:  hero_banner           (no s_ prefix — tool adds it)
  snippet_class:   s_hero_banner         (auto-computed by model)
  module_name:     website_hero_banner   (full Odoo module name)
  CSS sub-classes: s_hero_banner_card    (always prefix with snippet_class)
  data-snippet:    must match snippet_class exactly
  template id:     must match snippet_class exactly
"""

SNIPPET_PROMPT_ENTRY = {
    "name": "create_snippet",
    "description": (
        "Create an Odoo 19 website drag-and-drop snippet "
        "(building block) for the Website Builder"
    ),
    "arguments": [
        {
            "name": "description",
            "description": "What the snippet should look like and do",
            "required": True,
        }
    ],
    "_text": _PROMPT_CREATE_SNIPPET,
}

# ═══════════════════════════════════════════════════════════════════════════
# _PROMPT_MODULE_INSTALL_HINT — short stub for install/fix/update actions
# Shown instead of the full prompt to avoid re-consuming thousands of tokens
# on every install/fix/update call after the initial create.
# ═══════════════════════════════════════════════════════════════════════════

_PROMPT_MODULE_INSTALL_HINT = """MODULE INSTALL/FIX RULES (concise — full rules were given at create time):
- On install failure: read 'hints' in the response carefully.
- Call action='fix' (auto-fixes tree→list, selection format, state=manual, ondelete, chatter).
- Then call action='install' again.
- If still failing: call action='preview' to see all errors, then action='update' to patch manually.
- NEVER re-read the full create_module prompt for install/fix/update — it wastes tokens.
- The auto-fixer already handles the most common XML errors automatically.
"""

# ═══════════════════════════════════════════════════════════════════════════
# _PROMPT_CREATE_MODULE — full prompt, only injected on action='create'
# ═══════════════════════════════════════════════════════════════════════════

_PROMPT_CREATE_MODULE = """Create a complete production-grade Odoo 19 data module for: {{description}}

Call odoo_manage_module(action='create', ...) then odoo_manage_module(action='install', ...)

═══════════════════════════════════════════════════════════════════
STEP 0 — DISCOVERY FIRST (always do this before writing any code)
═══════════════════════════════════════════════════════════════════

Before writing ANY XML:
1. Call odoo_list_models() to find existing models if extending Odoo
2. Call odoo_get_fields(model='x_name') to verify field names exist

═══════════════════════════════════════════════════════════════════
STEP 1 — UNDERSTAND THE ARCHITECTURE
═══════════════════════════════════════════════════════════════════

This module installs via base_import_module — NO Python .py files.
Everything is done via XML data records.

WHAT WORKS:
  ✅ Models     → ir.model + ir.model.fields records
  ✅ Fields     → all types: char, text, integer, float, monetary,
                  boolean, date, datetime, selection, many2one,
                  many2many, one2many, binary, html
  ✅ Views      → form, list, kanban, search, calendar, pivot, graph
  ✅ Buttons    → ir.actions.server + type="action" in view
  ✅ Onchange   → base.automation trigger=on_write
  ✅ Constraint → base.automation trigger=on_create_or_write + UserError
  ✅ Computed   → readonly field + base.automation sets value
  ✅ Wizard     → transient ir.model + act_window target=new
  ✅ Cron       → ir.cron records
  ✅ Email      → mail.template records
  ✅ Extend     → inherit existing Odoo views with xpath

WHAT DOES NOT WORK:
  ❌ Python class (no class X(models.Model))
  ❌ @api.onchange, @api.constrains, @api.depends decorators
  ❌ type="object" buttons (no Python method to call)
  ❌ attrs="{...}" or states="..." (removed Odoo 17+)
  ❌ <tree> view (removed Odoo 19 — use <list>)

DEPENDS RULES:
  'base'            → always required
  'mail'            → chatter, message_post, mail.template
  'base_automation' → REQUIRED for any buttons, onchange, constraint,
                      computed field, ir.actions.server, ir.cron
  'sale'            → if referencing sale.order
  'account'         → if referencing account.move
  'stock'           → if referencing stock.picking
  'hr'              → if referencing hr.employee

═══════════════════════════════════════════════════════════════════
STEP 2 — WORKFLOW (follow this exact order)
═══════════════════════════════════════════════════════════════════

SIMPLE MODULE (1-2 models):
  1. Create with all code in one call
  2. Install
  3. If fails → fix → install again

COMPLEX MODULE (3+ models):
  1. create with first model only in models_code
  2. add_feature feature_type='model' for each additional model
  3. update with complete views_code once all models exist
  4. install

ON ANY INSTALL FAILURE:
  1. Read 'hints' in the response carefully
  2. Call action='fix' (auto-fixes tree→list, selection, depends)
  3. Call action='install' again
  4. If still failing, call action='preview' to see all errors
  5. Call action='update' to fix manually
  6. Call action='install' again

═══════════════════════════════════════════════════════════════════
STEP 3 — MANDATORY PRE-WRITE CHECKLIST
═══════════════════════════════════════════════════════════════════

Before writing views_code, verify ALL of the following:

□ EVERY view listed in view_mode has a matching ir.ui.view record
    view_mode="list,form"           → 2 view records needed
    view_mode="list,form,kanban"    → 3 view records needed
    view_mode="list,form,calendar"  → 3 view records needed
    RULE: count the commas + 1 = number of view records required

□ calendar view requires date_start pointing to a real date/datetime field
    WRONG: view_mode="list,form,calendar" with no calendar view record
    WRONG: <calendar> without date_start= attribute
    CORRECT:
      <calendar date_start="x_deadline" color="x_assignee_id" mode="month">
      AND the model must have field x_deadline of ttype=date or datetime

□ pivot view requires a <pivot> view record
    WRONG: view_mode includes "pivot" but no <pivot> view record
    CORRECT: Create ir.ui.view with <pivot> arch

□ graph view requires a <graph> view record
    WRONG: view_mode includes "graph" but no <graph> view record

□ EVERY button %(action_server_id)d has a matching ir.actions.server record
    WRONG: <button name="%(action_server_enroll)d"> with no action_server_enroll record
    CORRECT: Every %(name)d reference needs <record id="name" model="ir.actions.server">

□ EVERY ref= value exists as a record id in models_code or views_code
    WRONG: <field name="model_id" ref="model_x_foo"/> if model_x_foo not defined
    Cross-module refs (containing dot) are OK: ref="sale.model_sale_order"

□ security_code has one CSV row per model
    Every ir.model needs at least one access rule

□ 'base_automation' in depends if using ANY ir.actions.server or ir.cron
□ 'mail' in depends if using <chatter/>, message_post, or mail.template

═══════════════════════════════════════════════════════════════════
MANIFEST_CODE
═══════════════════════════════════════════════════════════════════

{
    'name': 'Hospital Management',
    'version': '19.0.1.0.0',
    'summary': 'Manage patients, doctors, appointments',
    'category': 'Technical',
    'author': 'MCP Builder',
    'depends': ['base', 'mail', 'base_automation'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
# Note: 'data' list is auto-generated by the tool

═══════════════════════════════════════════════════════════════════
MODELS_CODE — all ir.model and ir.model.fields records
═══════════════════════════════════════════════════════════════════

<odoo><data noupdate="1">

  <!-- ── MODEL ─────────────────────────────────────────────── -->
  <record id="model_x_patient" model="ir.model">
    <field name="name">Patient</field>
    <field name="model">x_patient</field>
    <field name="state">manual</field>
  </record>

  <!-- ── CHAR ──────────────────────────────────────────────── -->
  <record id="field_x_patient__x_name" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient"/>
    <field name="name">x_name</field>
    <field name="field_description">Patient Name</field>
    <field name="ttype">char</field>
    <field name="required" eval="True"/>
    <field name="index" eval="True"/>
  </record>

  <!-- ── TEXT ──────────────────────────────────────────────── -->
  <record id="field_x_patient__x_notes" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient"/>
    <field name="name">x_notes</field>
    <field name="field_description">Medical Notes</field>
    <field name="ttype">text</field>
  </record>

  <!-- ── INTEGER ───────────────────────────────────────────── -->
  <record id="field_x_patient__x_age" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient"/>
    <field name="name">x_age</field>
    <field name="field_description">Age</field>
    <field name="ttype">integer</field>
  </record>

  <!-- ── FLOAT ─────────────────────────────────────────────── -->
  <record id="field_x_patient__x_weight" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient"/>
    <field name="name">x_weight</field>
    <field name="field_description">Weight (kg)</field>
    <field name="ttype">float</field>
  </record>

  <!-- ── MONETARY (always add currency_field companion) ─────── -->
  <record id="field_x_patient__x_currency_id" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient"/>
    <field name="name">x_currency_id</field>
    <field name="field_description">Currency</field>
    <field name="ttype">many2one</field>
    <field name="relation">res.currency</field>
  </record>
  <record id="field_x_patient__x_fee" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient"/>
    <field name="name">x_fee</field>
    <field name="field_description">Consultation Fee</field>
    <field name="ttype">monetary</field>
    <field name="currency_field">x_currency_id</field>
  </record>

  <!-- ── BOOLEAN ───────────────────────────────────────────── -->
  <record id="field_x_patient__x_active" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient"/>
    <field name="name">x_active</field>
    <field name="field_description">Active</field>
    <field name="ttype">boolean</field>
  </record>

  <!-- ── DATE ──────────────────────────────────────────────── -->
  <record id="field_x_patient__x_dob" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient"/>
    <field name="name">x_dob</field>
    <field name="field_description">Date of Birth</field>
    <field name="ttype">date</field>
  </record>

  <!-- ── DATETIME ──────────────────────────────────────────── -->
  <record id="field_x_patient__x_admission_date" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient"/>
    <field name="name">x_admission_date</field>
    <field name="field_description">Admission Date</field>
    <field name="ttype">datetime</field>
  </record>

  <!-- ── SELECTION ─────────────────────────────────────────── -->
  <!--
    MUST be Python list format — Odoo calls literal_eval() on this.
    ✅ [('draft','Draft'),('active','Active')]
    ❌ draft:Draft,active:Active  ← causes ParseError every time
    Also add ir.model.fields.selection records for each option.
  -->
  <record id="field_x_patient__x_state" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient"/>
    <field name="name">x_state</field>
    <field name="field_description">Status</field>
    <field name="ttype">selection</field>
    <field name="selection">[('draft','Draft'),('admitted','Admitted'),('discharged','Discharged')]</field>
  </record>

  <!-- ── MANY2ONE ───────────────────────────────────────────── -->
  <record id="field_x_patient__x_doctor_id" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient"/>
    <field name="name">x_doctor_id</field>
    <field name="field_description">Assigned Doctor</field>
    <field name="ttype">many2one</field>
    <field name="relation">x_doctor</field>
    <field name="ondelete">set null</field>
  </record>

  <!-- ── MANY2MANY ──────────────────────────────────────────── -->
  <record id="field_x_patient__x_treatment_ids" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient"/>
    <field name="name">x_treatment_ids</field>
    <field name="field_description">Treatments</field>
    <field name="ttype">many2many</field>
    <field name="relation">x_treatment</field>
    <field name="relation_table">x_patient_treatment_rel</field>
    <field name="column1">patient_id</field>
    <field name="column2">treatment_id</field>
  </record>

  <!-- ── ONE2MANY ───────────────────────────────────────────── -->
  <record id="field_x_patient__x_appointment_ids" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient"/>
    <field name="name">x_appointment_ids</field>
    <field name="field_description">Appointments</field>
    <field name="ttype">one2many</field>
    <field name="relation">x_appointment</field>
    <field name="relation_field">x_patient_id</field>
  </record>

  <!-- ── BINARY (photo/image) ──────────────────────────────── -->
  <record id="field_x_patient__x_photo" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient"/>
    <field name="name">x_photo</field>
    <field name="field_description">Photo</field>
    <field name="ttype">binary</field>
  </record>

  <!-- ── COMPUTED-STYLE (readonly, set by automation) ─────────── -->
  <record id="field_x_patient__x_display_name" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient"/>
    <field name="name">x_display_name</field>
    <field name="field_description">Display Name</field>
    <field name="ttype">char</field>
    <field name="readonly" eval="True"/>
  </record>

  <!-- ── TRANSIENT (wizard) MODEL ─────────────────────────────── -->
  <record id="model_x_patient_note_wizard" model="ir.model">
    <field name="name">Patient Note Wizard</field>
    <field name="model">x_patient_note_wizard</field>
    <field name="state">manual</field>
    <field name="transient" eval="True"/>
  </record>
  <record id="field_x_wizard__x_patient_id" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient_note_wizard"/>
    <field name="name">x_patient_id</field>
    <field name="field_description">Patient</field>
    <field name="ttype">many2one</field>
    <field name="relation">x_patient</field>
  </record>
  <record id="field_x_wizard__x_note" model="ir.model.fields">
    <field name="model_id" ref="model_x_patient_note_wizard"/>
    <field name="name">x_note</field>
    <field name="field_description">Note</field>
    <field name="ttype">text</field>
    <field name="required" eval="True"/>
  </record>

</data></odoo>

═══════════════════════════════════════════════════════════════════
EXTENDING AN EXISTING ODOO MODEL
═══════════════════════════════════════════════════════════════════

DO NOT create a new ir.model — just add ir.model.fields records
pointing to the existing model using the correct ref format.

<!-- Add field to sale.order -->
<record id="field_sale_order__x_note" model="ir.model.fields">
  <field name="model_id" ref="sale.model_sale_order"/>
  <field name="name">x_custom_note</field>
  <field name="field_description">Custom Note</field>
  <field name="ttype">char</field>
</record>

EXISTING MODEL REF FORMAT:
  sale.order     → ref="sale.model_sale_order"
  res.partner    → ref="base.model_res_partner"
  hr.employee    → ref="hr.model_hr_employee"
  account.move   → ref="account.model_account_move"
  stock.picking  → ref="stock.model_stock_picking"
  crm.lead       → ref="crm.model_crm_lead"
  project.task   → ref="project.model_project_task"

Inherit an existing view with xpath:
<record id="view_sale_form_inherit_x" model="ir.ui.view">
  <field name="name">sale.order.form.inherit.x</field>
  <field name="model">sale.order</field>
  <field name="inherit_id" ref="sale.view_order_form"/>
  <field name="arch" type="xml">
    <xpath expr="//field[@name='partner_id']" position="after">
      <field name="x_custom_note"/>
    </xpath>
  </field>
</record>

xpath position: after | before | inside | replace | attributes

═══════════════════════════════════════════════════════════════════
VIEWS_CODE — complete views for every model
═══════════════════════════════════════════════════════════════════

RULE: Count view_mode entries — create exactly that many ir.ui.view records.
  view_mode="list,form,kanban,calendar,pivot"
  → need: list view + form view + kanban view + calendar view + pivot view = 5 records

<odoo><data>

<!-- ═══ FORM VIEW ════════════════════════════════════════════ -->
<record id="view_x_patient_form" model="ir.ui.view">
  <field name="name">x_patient.form</field>
  <field name="model">x_patient</field>
  <field name="arch" type="xml">
    <form string="Patient">
      <header>
        <!--
          BUTTON RULES:
          ✅ type="action" name="%(action_server_id)d"
          ❌ type="object" name="method_name"  — broken in data modules

          Every %(name)d MUST have a matching ir.actions.server record
          with id="name" defined in this same views_code file.

          invisible: use Python expression directly
          ✅ invisible="x_state != 'draft'"
          ❌ attrs="{'invisible': [('x_state','!=','draft')]}"  — removed Odoo 17+
        -->
        <button name="%(action_server_x_patient_admit)d"
                type="action" string="Admit" class="oe_highlight"
                invisible="x_state != 'draft'"/>
        <button name="%(action_server_x_patient_discharge)d"
                type="action" string="Discharge" class="oe_highlight"
                invisible="x_state != 'admitted'"/>
        <button name="%(action_server_x_patient_reset)d"
                type="action" string="Reset to Draft"
                invisible="x_state == 'draft'"/>
        <!-- Wizard popup button -->
        <button name="%(action_open_x_patient_note_wizard)d"
                type="action" string="Add Note" class="btn-secondary"/>
        <field name="x_state" widget="statusbar"
               statusbar_visible="draft,admitted,discharged"/>
      </header>
      <sheet>
        <field name="x_photo" widget="image" class="oe_avatar"
               options="{'zoom': true, 'size': [90, 90]}"/>
        <div class="oe_title">
          <h1><field name="x_name" placeholder="Patient Name..."/></h1>
          <h3><field name="x_display_name" readonly="1"/></h3>
        </div>
        <group>
          <group string="Personal Info">
            <field name="x_dob"/>
            <field name="x_age"/>
            <field name="x_weight"/>
            <field name="x_active"/>
          </group>
          <group string="Medical">
            <field name="x_doctor_id"/>
            <field name="x_fee" widget="monetary"/>
            <field name="x_currency_id" invisible="1"/>
            <field name="x_admission_date"/>
          </group>
        </group>
        <notebook>
          <page string="Appointments">
            <field name="x_appointment_ids" mode="list">
              <list editable="bottom">
                <field name="x_date"/>
                <field name="x_reason"/>
                <field name="x_state"/>
              </list>
            </field>
          </page>
          <page string="Treatments">
            <field name="x_treatment_ids" widget="many2many_tags"/>
          </page>
          <page string="Notes">
            <field name="x_notes"/>
          </page>
        </notebook>
      </sheet>
      <!-- Only if 'mail' in depends -->
      <chatter/>
    </form>
  </field>
</record>

<!-- ═══ LIST VIEW — ALWAYS <list> NEVER <tree> ═══════════════ -->
<record id="view_x_patient_list" model="ir.ui.view">
  <field name="name">x_patient.list</field>
  <field name="model">x_patient</field>
  <field name="arch" type="xml">
    <list string="Patients"
          decoration-success="x_state == 'admitted'"
          decoration-muted="x_state == 'discharged'"
          decoration-warning="x_state == 'draft'">
      <field name="x_name"/>
      <field name="x_doctor_id"/>
      <field name="x_age"/>
      <field name="x_dob" optional="show"/>
      <field name="x_admission_date" optional="show"/>
      <field name="x_fee" widget="monetary" optional="hide"/>
      <field name="x_currency_id" column_invisible="1"/>
      <field name="x_state" widget="badge"
             decoration-success="x_state == 'admitted'"
             decoration-warning="x_state == 'draft'"
             decoration-danger="x_state == 'discharged'"/>
    </list>
  </field>
</record>

<!-- ═══ KANBAN VIEW — Odoo 19 confirmed structure ════════════ -->
<!--
  KANBAN VIEW RULES (Odoo 19):

  CRITICAL CHANGE from older Odoo:
    ❌ OLD: <t t-name="kanban-card">
    ✅ NEW: <t t-name="card">
    Using the old name causes the card template to not render.

  <kanban> attributes:
    default_group_by="x_field"  → group columns by this field on load
    sample="1"                  → show sample data when no records exist
    quick_create="false"        → disable quick-create in column header
    class="o_kanban_mobile"     → responsive mobile layout

  <progressbar> — colored progress bar at top of each column:
    field="x_state_field"       → field driving the bar colors
    colors='{"val":"success","val2":"warning","val3":"danger"}'
    valid color values: success | warning | danger | info | muted

  <t t-name="card"> template structure:
    - Put main content directly in the card body
    - Use <footer> for bottom row (status badge, avatar, action buttons)
    - Bootstrap 5 classes available: d-flex, fw-bolder, text-muted,
      ms-auto, ms-1, mb-2, fs-5, justify-content-between etc.

  Field widgets inside kanban:
    widget="label_selection"    → colored badge for selection fields
      options="{'classes': {'draft':'info','done':'success','cancelled':'danger'}}"
    widget="priority"           → star rating widget
    widget="state_selection"    → dot + label for state
    widget="activity_state"     → activity indicator dot
-->

<record id="view_x_patient_kanban" model="ir.ui.view">
  <field name="name">x_patient.kanban</field>
  <field name="model">x_patient</field>
  <field name="arch" type="xml">
    <kanban default_group_by="x_state"
            sample="1"
            quick_create="false">

      <!-- Declare all fields used in the template -->
      <field name="x_name"/>
      <field name="x_state"/>
      <field name="x_doctor_id"/>
      <field name="x_age"/>
      <field name="x_gender"/>

      <!-- Optional: progress bar colored by state -->
      <progressbar field="x_state"
          colors='{"admitted":"success","under_treatment":"warning","discharged":"muted","cancelled":"danger"}'/>

      <templates>
        <!-- Odoo 19: t-name="card" — NOT "kanban-card" -->
        <t t-name="card">

          <!-- Card header row -->
          <div class="d-flex mb-2" style="justify-content: space-between;">
            <field name="x_name" class="fw-bolder fs-5"/>
            <field name="x_age" class="ms-1 text-muted"/>
          </div>

          <!-- Card body -->
          <div class="text-muted">
            <field name="x_doctor_id"/>
          </div>
          <div class="text-muted">
            <field name="x_gender"/>
          </div>

          <!-- Footer row — status badge + other info -->
          <footer>
            <div class="d-flex">
              <field name="x_state"
                     widget="label_selection"
                     options="{'classes': {
                       'draft': 'info',
                       'admitted': 'success',
                       'under_treatment': 'warning',
                       'discharged': 'muted',
                       'cancelled': 'danger'
                     }}"
                     class="ms-auto"/>
            </div>
          </footer>

        </t>
      </templates>
    </kanban>
  </field>
</record>

KANBAN QUICK REFERENCE (Odoo 19):

  Template name:
    ✅ <t t-name="card">          → Odoo 19
    ❌ <t t-name="kanban-card">  → old syntax, broken in Odoo 19

  progressbar colors:
    "success"  → green
    "warning"  → yellow/orange
    "danger"   → red
    "info"     → blue
    "muted"    → gray

  widget="label_selection" color classes:
    "primary"  → blue
    "success"  → green
    "warning"  → orange
    "danger"   → red
    "info"     → light blue
    "default"  → gray

  Bootstrap classes available in kanban:
    d-flex, fw-bolder, text-muted, ms-auto, mb-2, fs-5,
    justify-content-between, align-items-center


<!-- ═══ PIVOT VIEW — Odoo 19 confirmed structure ════════════ -->
<!--
  PIVOT VIEW RULES (Odoo 19):

  PREREQUISITE: view_mode must include "pivot" AND this view record must exist.

  <pivot> attributes:
    string="Label"              → title shown in breadcrumb
    disable_linking="true"      → prevent clicking cells from opening records
                                  useful for pure analysis views

  <field> inside pivot:
    type="row"    → field appears as a row grouping (left axis)
    type="col"    → field appears as a column grouping (top axis)
    type="measure"→ numeric field shown as the value in cells
                    only integer/float/monetary fields can be measures

  RULES:
  - At least one type="row" or type="col" field required
  - type="measure" must be a numeric field (integer/float/monetary)
  - String/char/selection fields → use type="row" or type="col" only
  - You can have multiple row, col, and measure fields
-->

<record id="view_x_patient_pivot" model="ir.ui.view">
  <field name="name">x_patient.pivot</field>
  <field name="model">x_patient</field>
  <field name="arch" type="xml">
    <pivot string="Patient Analysis">
      <!-- Row groupings — left side axis -->
      <field name="x_department_id" type="row"/>
      <field name="x_doctor_id"     type="row"/>
      <!-- Column groupings — top axis -->
      <field name="x_state"         type="col"/>
      <!-- Measures — numeric values in cells -->
      <!-- Note: x_age must be integer/float field -->
      <field name="x_age"           type="measure"/>
    </pivot>
  </field>
</record>

<!-- PIVOT with monetary measure -->
<record id="view_x_billing_pivot" model="ir.ui.view">
  <field name="name">x_billing.pivot</field>
  <field name="model">x_billing</field>
  <field name="arch" type="xml">
    <pivot string="Billing Analysis" disable_linking="true">
      <field name="x_doctor_id"      type="row"/>
      <field name="x_department_id"  type="row"/>
      <field name="x_state"          type="col"/>
      <field name="x_amount"         type="measure"/>
      <field name="x_discount"       type="measure"/>
    </pivot>
  </field>
</record>

PIVOT QUICK REFERENCE:

  Row fields (left grouping axis):
    <field name="x_category_id" type="row"/>   → Many2one
    <field name="x_state"       type="row"/>   → selection
    <field name="x_doctor_id"   type="row"/>   → Many2one

  Column fields (top grouping axis):
    <field name="x_month"       type="col"/>
    <field name="x_state"       type="col"/>

  Measure fields (cell values — MUST be numeric):
    <field name="x_amount"      type="measure"/>  → monetary/float
    <field name="x_count"       type="measure"/>  → integer
    <field name="x_age"         type="measure"/>  → integer

  ❌ WRONG — char/selection as measure:
    <field name="x_name"  type="measure"/>  → crash, not numeric
    <field name="x_state" type="measure"/>  → crash, not numeric

  disable_linking="true" → cells are not clickable links
  disable_linking="false" (default) → clicking a cell opens filtered list

<!-- ═══ SEARCH VIEW ══════════════════════════════════════════ -->
<!-- ═══ SEARCH VIEW — Odoo 19 confirmed structure ══════════ -->
<!--
  FIELD RULES FOR GROUP BY AND SEARCH PANEL:

  ✅ ALLOWED in Group By filters:
    Many2one fields     → groups records by related record
    selection fields    → groups records by selection value

  ❌ NOT ALLOWED in Group By:
    char, text, integer, float, date, datetime, boolean
    → These have too many unique values, grouping makes no sense

  ✅ ALLOWED in searchpanel:
    Many2one fields     → sidebar filter list
    selection fields    → sidebar filter list with select="multi"

  ❌ NOT ALLOWED in searchpanel:
    char, text, integer, float, date, datetime, boolean
-->

<record id="view_x_patient_search" model="ir.ui.view">
  <field name="name">x_patient.search</field>
  <field name="model">x_patient</field>
  <field name="arch" type="xml">
    <search>

      <!-- Search fields — any field type is OK here -->
      <field name="x_name"          string="Patient Name"/>
      <field name="x_phone"         string="Phone"/>
      <field name="x_doctor_id"     string="Doctor"/>
      <field name="x_department_id" string="Department"/>
      <field name="x_insurance_no"  string="Insurance No"/>

      <separator/>

      <!-- Predefined filters — any domain is OK here -->
      <filter name="filter_draft"
              string="Draft"
              domain="[('x_state','=','draft')]"/>
      <filter name="filter_admitted"
              string="Admitted"
              domain="[('x_state','=','admitted')]"/>
      <filter name="filter_under_treatment"
              string="Under Treatment"
              domain="[('x_state','=','under_treatment')]"/>
      <filter name="filter_discharged"
              string="Discharged"
              domain="[('x_state','=','discharged')]"/>
      <filter name="filter_cancelled"
              string="Cancelled"
              domain="[('x_state','=','cancelled')]"/>

      <separator/>

      <!--
        GROUP BY — ONLY Many2one and selection fields allowed.
        char/text/integer/float/date fields are NOT valid here.
      -->
      <group name="groupby" string="Group By">

        <!-- Many2one fields → valid group by -->
        <filter name="group_by_doctor"
                string="Doctor"
                context="{'group_by': 'x_doctor_id'}"/>
        <filter name="group_by_department"
                string="Department"
                context="{'group_by': 'x_department_id'}"/>

        <!-- selection fields → valid group by -->
        <filter name="group_by_state"
                string="Status"
                context="{'group_by': 'x_state'}"/>
        <filter name="group_by_gender"
                string="Gender"
                context="{'group_by': 'x_gender'}"/>
        <filter name="group_by_blood_group"
                string="Blood Group"
                context="{'group_by': 'x_blood_group'}"/>

        <!--
          ❌ WRONG — do not add these to group by:
          <filter name="group_by_name"   context="{'group_by': 'x_name'}"/>
          <filter name="group_by_age"    context="{'group_by': 'x_age'}"/>
          <filter name="group_by_phone"  context="{'group_by': 'x_phone'}"/>
          <filter name="group_by_dob"    context="{'group_by': 'x_dob'}"/>
        -->

      </group>

      <!--
        SEARCH PANEL — sidebar filters.
        ONLY Many2one and selection fields allowed.
        select="multi" → user can pick multiple values at once.
        select="one"   → user picks one value at a time (default).
      -->
      <searchpanel>

        <!-- Many2one → sidebar list of related records -->
        <field name="x_department_id"
               string="Department"
               select="one"/>

        <field name="x_doctor_id"
               string="Doctor"
               select="multi"/>

        <!-- selection → sidebar list of selection options -->
        <field name="x_state"
               string="Status"
               select="multi"/>

        <field name="x_gender"
               string="Gender"
               select="multi"/>

        <!--
          ❌ WRONG — do not add these to searchpanel:
          <field name="x_name"/>          → char field
          <field name="x_age"/>           → integer field
          <field name="x_dob"/>           → date field
          <field name="x_phone"/>         → char field
        -->

      </searchpanel>

    </search>
  </field>
</record>

SEARCH VIEW QUICK REFERENCE:

  <field> — search input (any field type OK):
    <field name="x_name" string="Label"/>

  <filter> — one-click predefined filter (any domain OK):
    <filter name="unique_id" string="Label"
            domain="[('x_field','=','value')]"/>

  <group name="groupby"> — Group By section:
    ONLY Many2one and selection fields:
    <filter name="group_by_x" string="Label"
            context="{'group_by': 'x_many2one_or_selection_field'}"/>

    ✅ Many2one   → x_doctor_id, x_department_id, x_category_id
    ✅ selection  → x_state, x_gender, x_priority, x_blood_group
    ❌ char       → x_name, x_phone, x_email
    ❌ integer    → x_age, x_count
    ❌ date       → x_dob, x_deadline
    ❌ text       → x_notes, x_description

  <searchpanel> — sidebar filter panel:
    ONLY Many2one and selection fields:
    <field name="x_field" string="Label" select="one|multi"/>

    select="one"   → radio buttons, one value at a time
    select="multi" → checkboxes, multiple values at once

    ✅ Many2one   → sidebar shows list of related records
    ✅ selection  → sidebar shows list of selection options
    ❌ char/integer/float/date/text → not supported, crash or empty

<!--
  CALENDAR VIEW RULES (Odoo 19 official):

  PREREQUISITES — check ALL before adding calendar:
  1. Model has a date or datetime field for date_start (MANDATORY)
  2. view_mode includes "calendar"
  3. A calendar ir.ui.view record exists in views_code
  If ANY of these is missing → remove "calendar" from view_mode

  ATTRIBUTES on <calendar> tag:
    date_start="x_field"   → REQUIRED. Must be a date or datetime field.
                             If Date field → shows as all-day event.
                             If Datetime field → shows with time slot.
    date_stop="x_field"    → Optional end date/datetime field.
                             Correct attribute is date_stop NOT date_end.
    string="Label"         → Title shown above the calendar.
    color="x_field"        → Optional. Many2one or selection field for
                             color-coding events by category.
    mode="month"           → Default display mode: month | week | day
                             Default is month if omitted.

  FIELDS inside <calendar>:
    Show extra info on each event card.
    <field name="x_name"/>          → event title
    <field name="x_doctor_id"/>     → additional info line

  WHEN TO USE date vs datetime:
    date field    → appointment.date='2025-01-15'
                  → shows as full-day block on calendar
    datetime field → appointment.datetime='2025-01-15 14:30:00'
                   → shows in correct time slot

  EXAMPLE — appointment with start + end datetime:
    date_start="x_start_datetime" date_stop="x_end_datetime"

  EXAMPLE — task with only deadline date:
    date_start="x_deadline" (no date_stop)
    → shows as all-day event on deadline date

  DO NOT add calendar to view_mode without this view record.
  DO NOT use date_end — correct attribute is date_stop.
-->

<!-- CALENDAR WITH DATETIME (time-slot display): -->
<record id="view_x_appointment_calendar" model="ir.ui.view">
  <field name="name">x_appointment.calendar</field>
  <field name="model">x_appointment</field>
  <field name="arch" type="xml">
    <calendar
        string="Appointments"
        date_start="x_appointment_date"
        date_stop="x_end_date"
        color="x_doctor_id"
        mode="month">
      <field name="x_patient_id"/>
      <field name="x_doctor_id"/>
    </calendar>
  </field>
</record>

<!-- CALENDAR WITH DATE ONLY (all-day display): -->
<record id="view_x_task_calendar" model="ir.ui.view">
  <field name="name">x_task.calendar</field>
  <field name="model">x_task</field>
  <field name="arch" type="xml">
    <calendar
        string="Tasks"
        date_start="x_deadline"
        color="x_assignee_id"
        mode="month">
      <field name="x_name"/>
      <field name="x_priority"/>
    </calendar>
  </field>
</record>

<!-- WINDOW ACTION — include calendar in view_mode -->
<record id="action_x_appointment" model="ir.actions.act_window">
  <field name="name">Appointments</field>
  <field name="res_model">x_appointment</field>
  <!-- calendar listed here because the view record above exists -->
  <field name="view_mode">list,form,kanban,calendar</field>
</record>

CALENDAR VIEW QUICK REFERENCE:

  Mandatory:
    date_start="x_date_field"   → date or datetime field on the model

  Optional:
    date_stop="x_end_field"     → end date — use date_stop NOT date_end
    color="x_many2one_field"    → color events by category
    mode="month"                → month | week | day (default: month)

  Date field type effects:
    fields.Date     → all-day event block (no time slot)
    fields.Datetime → time-slot event (shows exact time)

  Common date fields by module:
    appointment  → x_appointment_date (datetime)
    task         → x_deadline (date)
    admission    → x_admit_date (datetime)
    leave        → x_date_from, x_date_to (date)

  view_mode rule:
    ONLY add "calendar" to view_mode when ir.ui.view calendar record exists
    ONLY use date fields that actually exist on the model

<!-- ═══ WINDOW ACTION ════════════════════════════════════════ -->
<!--
  view_mode MUST match the view records created above.
  If you created calendar+pivot view records → include in view_mode.
  If you did NOT create them → do NOT include in view_mode.
-->
<record id="action_x_patient" model="ir.actions.act_window">
  <field name="name">Patients</field>
  <field name="res_model">x_patient</field>
  <!-- calendar and pivot included because view records exist above -->
  <field name="view_mode">list,form,kanban,calendar,pivot</field>
  <field name="search_view_id" ref="view_x_patient_search"/>
  <field name="help" type="html">
    <p class="o_view_nocontent_smiling_face">
      Register your first patient!
    </p>
  </field>
</record>

<!-- ═══ SERVER ACTIONS — one per button ══════════════════════ -->
<!--
  REQUIRES 'base_automation' in manifest depends.
  Every %(action_server_NAME)d button needs one of these.
  CDATA is mandatory — Python code inside XML must be wrapped.
-->

<record id="action_server_x_patient_admit" model="ir.actions.server">
  <field name="name">Patient: Admit</field>
  <field name="model_id" ref="model_x_patient"/>
  <field name="binding_model_id" ref="model_x_patient"/>
  <field name="binding_view_types">form,list</field>
  <field name="state">code</field>
  <field name="code"><![CDATA[
import datetime
for record in records:
    if record.x_state == 'draft':
        record.write({
            'x_state': 'admitted',
            'x_admission_date': datetime.datetime.now(),
        })
        if hasattr(record, 'message_post'):
            record.message_post(
                body='Patient admitted.',
                subtype_xmlid='mail.mt_note',
            )
  ]]></field>
</record>

<record id="action_server_x_patient_discharge" model="ir.actions.server">
  <field name="name">Patient: Discharge</field>
  <field name="model_id" ref="model_x_patient"/>
  <field name="state">code</field>
  <field name="code"><![CDATA[
for record in records:
    if record.x_state == 'admitted':
        record.write({'x_state': 'discharged'})
        if hasattr(record, 'message_post'):
            record.message_post(
                body='Patient discharged.',
                subtype_xmlid='mail.mt_note',
            )
  ]]></field>
</record>

<record id="action_server_x_patient_reset" model="ir.actions.server">
  <field name="name">Patient: Reset to Draft</field>
  <field name="model_id" ref="model_x_patient"/>
  <field name="state">code</field>
  <field name="code"><![CDATA[
for record in records:
    record.write({'x_state': 'draft'})
  ]]></field>
</record>

<!-- ═══ ONCHANGE PATTERN (replaces @api.onchange) ════════════ -->
<!-- Fires after record is written — updates computed display name -->

<record id="action_server_x_patient_compute" model="ir.actions.server">
  <field name="name">Patient: Compute display name</field>
  <field name="model_id" ref="model_x_patient"/>
  <field name="state">code</field>
  <field name="code"><![CDATA[
for record in records:
    parts = []
    if record.x_name:
        parts.append(record.x_name)
    if record.x_age:
        parts.append(f'(Age {record.x_age})')
    record.write({'x_display_name': ' '.join(parts)})
  ]]></field>
</record>

<record id="automation_x_patient_compute" model="base.automation">
  <field name="name">Patient: recompute display name</field>
  <field name="model_id" ref="model_x_patient"/>
  <field name="trigger">on_create_or_write</field>
  <field name="action_server_ids"
         eval="[(4, ref('action_server_x_patient_compute'))]"/>
</record>

<!-- ═══ CONSTRAINT PATTERN (replaces @api.constrains) ════════ -->
<!-- Raises UserError to block save if validation fails -->

<record id="action_server_x_patient_validate" model="ir.actions.server">
  <field name="name">Patient: Validate age</field>
  <field name="model_id" ref="model_x_patient"/>
  <field name="state">code</field>
  <field name="code"><![CDATA[
from odoo.exceptions import UserError
for record in records:
    if record.x_age and (record.x_age < 0 or record.x_age > 150):
        raise UserError(
            f"Age must be between 0 and 150. Got: {record.x_age}"
        )
  ]]></field>
</record>

<record id="automation_x_patient_validate" model="base.automation">
  <field name="name">Patient: validate age on save</field>
  <field name="model_id" ref="model_x_patient"/>
  <field name="trigger">on_create_or_write</field>
  <field name="action_server_ids"
         eval="[(4, ref('action_server_x_patient_validate'))]"/>
</record>

<!-- ═══ ON STATE CHANGE ══════════════════════════════════════ -->
<!-- Fires when selection field reaches a specific value -->

<record id="action_server_x_patient_on_admit" model="ir.actions.server">
  <field name="name">Patient: on admission notify</field>
  <field name="model_id" ref="model_x_patient"/>
  <field name="state">code</field>
  <field name="code"><![CDATA[
for record in records:
    if hasattr(record, 'message_post'):
        record.message_post(
            body=f'Patient {record.x_name} has been admitted.',
            subtype_xmlid='mail.mt_note',
        )
  ]]></field>
</record>

<record id="automation_x_patient_on_admit" model="base.automation">
  <field name="name">Patient: notify on admission</field>
  <field name="model_id" ref="model_x_patient"/>
  <field name="trigger">on_state_set</field>
  <field name="trg_selection_field_id"
         ref="sel_x_patient__x_state__admitted"/>
  <field name="action_server_ids"
         eval="[(4, ref('action_server_x_patient_on_admit'))]"/>
</record>

<!-- ═══ WIZARD VIEWS + ACTIONS ═══════════════════════════════ -->

<record id="view_x_patient_note_wizard_form" model="ir.ui.view">
  <field name="name">x_patient.note.wizard.form</field>
  <field name="model">x_patient_note_wizard</field>
  <field name="arch" type="xml">
    <form string="Add Medical Note">
      <group>
        <field name="x_patient_id" readonly="1"/>
        <field name="x_note" placeholder="Enter medical note..."/>
      </group>
      <footer>
        <button name="%(action_server_x_wizard_save_note)d"
                type="action" string="Save Note" class="oe_highlight"/>
        <button string="Cancel" class="btn-secondary" special="cancel"/>
      </footer>
    </form>
  </field>
</record>

<!-- Open wizard as popup: target="new" -->
<record id="action_open_x_patient_note_wizard" model="ir.actions.act_window">
  <field name="name">Add Medical Note</field>
  <field name="res_model">x_patient_note_wizard</field>
  <field name="view_mode">form</field>
  <field name="target">new</field>
</record>

<record id="action_server_x_wizard_save_note" model="ir.actions.server">
  <field name="name">Wizard: Save Medical Note</field>
  <field name="model_id" ref="model_x_patient_note_wizard"/>
  <field name="state">code</field>
  <field name="code"><![CDATA[
from datetime import datetime
for wizard in records:
    patient = wizard.x_patient_id
    if patient and wizard.x_note:
        existing  = patient.x_notes or ''
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        patient.write({
            'x_notes': f"{existing}\n[{timestamp}] {wizard.x_note}".strip()
        })
  ]]></field>
</record>

<!-- ═══ SCHEDULED ACTION (cron) ══════════════════════════════ -->

<record id="ir_cron_x_patient_report" model="ir.cron">
  <field name="name">Hospital: Daily Patient Count</field>
  <field name="model_id" ref="model_x_patient"/>
  <field name="state">code</field>
  <field name="code"><![CDATA[
admitted = env['x_patient'].search([('x_state', '=', 'admitted')])
env['ir.logging'].sudo().create({
    'name': 'hospital_cron',
    'type': 'server',
    'message': f'{len(admitted)} patients currently admitted',
    'level': 'INFO',
    'func': 'ir_cron_x_patient_report',
    'line': '1',
    'path': 'x_hospital_management',
})
  ]]></field>
  <field name="interval_number">1</field>
  <field name="interval_type">days</field>
  <field name="numbercall">-1</field>
  <field name="active" eval="True"/>
</record>

<!-- ═══ EMAIL TEMPLATE — REQUIRES 'mail' in depends ═════════ -->
<!--
  body_html uses QWeb — <t t-out="object.field or ''"/>
  subject uses Jinja2 — {{ object.field }}
-->
<record id="email_template_x_patient_welcome" model="mail.template">
  <field name="name">Patient: Admission Confirmation</field>
  <field name="model_id" ref="model_x_patient"/>
  <field name="subject">Admission Confirmed — {{ object.x_name }}</field>
  <field name="email_to">{{ object.x_doctor_id.email or '' }}</field>
  <field name="body_html" type="html">
    <div>
      <p>Dear <t t-out="object.x_name or 'Patient'"/>,</p>
      <p>You have been admitted to our hospital.
         Your doctor is <t t-out="object.x_doctor_id.name or 'N/A'"/>.</p>
      <p>Admission Date:
         <t t-out="object.x_admission_date or ''"/></p>
      <p>Best regards,<br/>Hospital Administration</p>
    </div>
  </field>
  <field name="auto_delete" eval="True"/>
</record>

<!-- ═══ MENUS ════════════════════════════════════════════════ -->

<menuitem id="menu_x_hospital_root"
          name="Hospital" sequence="90"/>
<menuitem id="menu_x_hospital_patients"
          name="Patients"
          parent="menu_x_hospital_root"
          action="action_x_patient"
          sequence="10"/>

</data></odoo>

═══════════════════════════════════════════════════════════════════
GRAPH VIEW — Odoo 19 confirmed structure
═══════════════════════════════════════════════════════════════════

<!-- GRAPH VIEW RULES (Odoo 19):
  PREREQUISITE: view_mode must include "graph" AND this view record must exist.

  <graph> attributes:
    string="Label"     → title shown in breadcrumb
    type="bar"         → bar (default) | line | pie
    stacked="true"     → stack bars (only for bar type)

  <field> inside graph:
    type="row"    → grouping axis (X-axis for bar/line, slices for pie)
    type="measure"→ numeric value (Y-axis for bar/line, slice size for pie)

  RULES:
  - At least one type="row" field required
  - type="measure" must be integer/float/monetary field
  - Multiple measure fields → multiple bars/lines side by side
-->

<record id="view_x_patient_graph" model="ir.ui.view">
  <field name="name">x_patient.graph</field>
  <field name="model">x_patient</field>
  <field name="arch" type="xml">
    <graph string="Patient Analysis" type="bar" stacked="true">
      <field name="x_state"     type="row"/>
      <field name="x_doctor_id" type="row"/>
      <field name="x_age"       type="measure"/>
    </graph>
  </field>
</record>

═══════════════════════════════════════════════════════════════════
OWL DASHBOARD COMPONENT — client_action in backend
═══════════════════════════════════════════════════════════════════

OWL dashboards are frontend components that render INSIDE the Odoo
backend as client actions. They require 3 files:

  1. js_code   → OWL component JavaScript
  2. owl_code  → OWL XML template
  3. views_code → ir.actions.client + menuitem to launch it

The tool automatically registers these via the Odoo 19 `assets`
manifest key (creates ir.asset records — no XML template needed).

── STEP 1: OWL XML TEMPLATE (owl_code — JSON dict) ─────────────

owl_code = {"dashboard.xml": `
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
  <t t-name="x_module_name.DashboardMain">
    <div class="o_action x_dashboard">
      <div class="x_dashboard_header">
        <h2>Dashboard Title</h2>
      </div>
      <div class="container-fluid">
        <div class="row g-3 mt-3">

          <!-- KPI Card -->
          <div class="col-md-3">
            <div class="card shadow-sm h-100">
              <div class="card-body text-center">
                <h5 class="card-title text-muted">Total Records</h5>
                <h2 class="text-primary">
                  <t t-esc="state.totalRecords"/>
                </h2>
              </div>
            </div>
          </div>

          <!-- Second KPI -->
          <div class="col-md-3">
            <div class="card shadow-sm h-100">
              <div class="card-body text-center">
                <h5 class="card-title text-muted">Active</h5>
                <h2 class="text-success">
                  <t t-esc="state.activeCount"/>
                </h2>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  </t>
</templates>
`}

── STEP 2: OWL COMPONENT JS (js_code — JSON dict) ──────────────

js_code = {"dashboard.js": `
/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class DashboardMain extends Component {
    static template = "x_module_name.DashboardMain";

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            totalRecords: 0,
            activeCount: 0,
        });
        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        const total = await this.orm.searchCount(
            "x_model_name", []);
        const active = await this.orm.searchCount(
            "x_model_name", [["x_state", "=", "active"]]);
        Object.assign(this.state, {
            totalRecords: total,
            activeCount: active,
        });
    }
}

registry
    .category("actions")
    .add("x_module_name.dashboard_action_tag", DashboardMain);
`}

── STEP 3: CLIENT ACTION + MENU (views_code) ───────────────────

Add these records to views_code alongside existing views:

<record id="action_x_module_dashboard" model="ir.actions.client">
  <field name="name">Dashboard</field>
  <field name="tag">x_module_name.dashboard_action_tag</field>
</record>

<menuitem id="menu_x_module_dashboard"
          name="Dashboard"
          parent="menu_x_module_root"
          action="action_x_module_dashboard"
          sequence="1"/>

── STEP 4: OPTIONAL SCSS (scss_code — JSON dict) ───────────────

scss_code = {"dashboard.scss": `
.x_dashboard {
  background: #f8f9fa;
  min-height: 100vh;
  padding: 1rem;
}
.x_dashboard_header {
  padding: 1rem 0;
  border-bottom: 2px solid #dee2e6;
  margin-bottom: 1rem;
}
.x_dashboard .card {
  border-radius: 12px;
  border: none;
  transition: transform 0.2s;
  &:hover { transform: translateY(-2px); }
}
`}

OWL DASHBOARD RULES:
  ✅ Use @odoo-module at the top of JS files
  ✅ Import from @odoo/owl and @web/core/
  ✅ Template name must match static template = "..." in JS
  ✅ Register in registry.category("actions").add("tag", Component)
  ✅ The tag in JS must match <field name="tag"> in ir.actions.client
  ✅ Use this.orm = useService("orm") for data access
  ✅ Use useState + onWillStart for reactive data loading
  ❌ Do NOT use jQuery or direct DOM manipulation
  ❌ Do NOT import from old web.core or web.ajax
  ❌ Do NOT use Widget or AbstractAction — use OWL Component

═══════════════════════════════════════════════════════════════════
ASSETS REGISTRATION — Odoo 19 Manifest Key
═══════════════════════════════════════════════════════════════════

The tool automatically handles this. JS, SCSS, and OWL XML files
are registered via the 'assets' key in __manifest__.py:

  'assets': {
      'web.assets_backend': [
          'x_module/static/src/js/dashboard.js',
          'x_module/static/src/xml/dashboard.xml',
          'x_module/static/src/scss/dashboard.scss',
      ]
  }

This replaces the old <template inherit_id="web.assets_backend">
approach. The tool generates this automatically from js_code,
owl_code, and scss_code parameters.

═══════════════════════════════════════════════════════════════════
WORKFLOW OPTIONS
═══════════════════════════════════════════════════════════════════

STANDARD WORKFLOW:
  1. create → install → done

REVIEW-FIRST WORKFLOW:
  1. create with skip_install=true → saves but does not install
  2. get → review generated code
  3. fix → auto-fix any issues
  4. install → install when ready

CLEAN REINSTALL:
  1. install with uninstall_first=true → removes old module first

FORCE NOUPDATE RECORDS:
  1. install with force=true → overwrites noupdate records

EXPORT FOR DEPLOYMENT:
  1. export → generates CSV attachment on chatter for migration

═══════════════════════════════════════════════════════════════════
SECURITY_CODE (ir.model.access.csv)
═══════════════════════════════════════════════════════════════════

id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_x_patient_user,x_patient.user,model_x_patient,base.group_user,1,1,1,0
access_x_patient_manager,x_patient.manager,model_x_patient,base.group_system,1,1,1,1
access_x_patient_note_wizard,x_wizard.user,model_x_patient_note_wizard,base.group_user,1,1,1,1

═══════════════════════════════════════════════════════════════════
FINAL CHECKLIST — run through this before every install call
═══════════════════════════════════════════════════════════════════

FOR EVERY MODEL:
  □ ir.model record with state='manual'  ← CRITICAL, auto-fixed if missing
  □ All fields as ir.model.fields records
  □ Selection fields have Python list format
  □ At least one security_code CSV row

FOR EVERY MANY2ONE FIELD:
  □ NEVER set ondelete='set null' on a required Many2one field
     Required + set null = PostgreSQL constraint violation → install crash
  □ If required=True, use ondelete='cascade' or omit ondelete entirely
  □ If not required, ondelete='set null' is fine

FOR CHATTER / MAIL FEATURES:
  □ Data-only models do NOT inherit mail.thread automatically
  □ NEVER add <div class="oe_chatter"> unless 'mail' is in depends
  □ NEVER use message_follower_ids, activity_ids, message_ids fields
     unless the model inherits mail.thread (not possible in data-only)
  □ If you need chatter: add 'mail' to depends AND the model must
     explicitly inherit mail.thread (which requires Python, not data-only)
  □ SAFE ALTERNATIVE: skip chatter entirely in data-only modules

FOR SECURITY CSV:
  □ model_id:id column must match the EXACT id= of the ir.model record
     Example: if models_code has <record id="model_x_construction_task" model="ir.model">
     then CSV must use: model_x_construction_task (NOT model_x_task)
  □ If the ir.model record id is "model_x_construction_project",
     the CSV row must be: access_...,model_x_construction_project,...

FOR EVERY VIEW IN view_mode:
  □ Matching ir.ui.view record exists in views_code
  □ calendar → date_start= set to real date field
  □ pivot → <pivot> record exists
  □ graph → <graph> record exists

FOR EVERY BUTTON:
  □ type="action" not type="object"
  □ %(action_server_NAME)d has matching ir.actions.server record id="action_server_NAME"

FOR MANIFEST:
  □ 'base_automation' in depends if any ir.actions.server or ir.cron
  □ 'mail' in depends if any <chatter/>, message_post, mail.template

ALL PYTHON CODE IN XML:
  □ Wrapped in <![CDATA[ ... ]]>
  □ from odoo.exceptions import UserError if raising errors

CIRCULAR REFERENCE ORDERING RULE:
When model A has a Many2one → model B, AND model B has a Many2one → model A:

WRONG (crashes at install):
  Define A with field → B   ← B not defined yet, crash

CORRECT — 3-step pattern:
  Step 1: Define A WITHOUT the field that points to B
  Step 2: Define B WITH field → A (A now exists)
  Step 3: Add the field to A that points to B (B now exists)

Example: Department ↔ Doctor circular reference:
  1. Define x_hms_department (no x_head_id)
  2. Define x_hms_doctor with x_department_id → x_hms_department
  3. Add x_head_id to x_hms_department → x_hms_doctor

VIEW SYNTAX:
  □ <list> not <tree>
  □ invisible="expr" not attrs="{...}"
""" + _SYSTEM_PROMPT

_PROMPT_QUERY_DATA = """Query Odoo data for: {{description}}

INSTRUCTIONS:
1. First call odoo_list_models to find relevant models
2. Call odoo_get_fields to understand model structure
3. Use odoo_search_read for detail queries or odoo_aggregate for group-by analytics
4. Present results clearly with totals and formatting

AVAILABLE TOOLS: odoo_search_read, odoo_aggregate, odoo_get_record, odoo_execute_orm
"""


_PROMPT_ADD_FIELD = """Add a custom field to an Odoo model for: {{description}}

INSTRUCTIONS:
1. Call odoo_get_fields on the target model to see existing fields
2. Call odoo_add_custom_field with the field details
3. Specify position_field and position to place it in the form view

FIELD TYPES: char, text, integer, float, monetary, boolean, date, datetime,
             selection, many2one, many2many, one2many, html, binary
"""

_PROMPT_CREATE_EMAIL_TEMPLATE = """Create a professional email template for: {{description}}

YOU write the complete HTML. The tool saves it and renders it via Odoo 19.

═══════════════════════════════════════════════════════════
CRITICAL — ODOO 19 SYNTAX (confirmed from official source)
═══════════════════════════════════════════════════════════

Odoo 19 switched body_html rendering to QWeb.
{{ object.field }} NEVER renders in body_html — it prints literally.

CORRECT syntax for body_html:
  <t t-out="object.name or ''"/>
  <t t-out="object.job_id.name or 'N/A'"/>
  <t t-out="object.department_id.name or 'N/A'"/>
  <t t-out="object.work_email or ''"/>
  <t t-out="object.partner_id.name or ''"/>
  <t t-out="object.amount_total or 0"/>
  <t t-out="user.name or ''"/>
  <t t-out="user.email_formatted or ''"/>

CORRECT syntax for subject / email_to / email_from (Jinja2 still works here):
  subject  = "Job Offer — {{ object.name }}"
  email_to = "{{ object.work_email }}"

CONDITIONAL block in body:
  <t t-if="object.job_id">
    <t t-out="object.job_id.name or ''"/>
  </t>

LOOP in body (e.g. order lines):
  <t t-foreach="object.order_line" t-as="line">
    <tr>
      <td><t t-out="line.product_id.name or ''"/></td>
      <td><t t-out="line.product_uom_qty or 0"/></td>
      <td><t t-out="line.price_subtotal or 0"/></td>
    </tr>
  </t>

═══════════════════════════════════════════════════════════
STEP 1 — CALL odoo_get_fields TO GET REAL FIELD NAMES
═══════════════════════════════════════════════════════════

NEVER guess field names. Always call odoo_get_fields first.

MODEL SELECTION:
  "employee", "interview", "HR", "job offer", "walk in" → hr.employee
  "invoice", "payment", "bill"                          → account.move
  "order", "quote", "sale"                              → sale.order
  "customer", "contact"                                 → res.partner
  "applicant", "candidate"                              → hr.applicant
  "delivery", "shipment"                                → stock.picking
  "payslip", "salary"                                   → hr.payslip
  "leave", "holiday"                                    → hr.leave
  pure promotion (no Odoo data)                         → omit model

CALL: odoo_get_fields(model='<chosen model>')
Use ONLY fields confirmed in the response.

VERIFIED QWEB EXPRESSIONS:

  hr.employee:
    <t t-out="object.name or ''"/>
    <t t-out="object.job_id.name or 'N/A'"/>
    <t t-out="object.department_id.name or 'N/A'"/>
    <t t-out="object.work_email or ''"/>
    <t t-out="object.parent_id.name or 'N/A'"/>
    <t t-out="object.company_id.name or ''"/>
    <t t-out="object.work_location_id.name or 'N/A'"/>
    <t t-out="object.mobile_phone or ''"/>

  account.move:
    <t t-out="object.name or ''"/>
    <t t-out="object.partner_id.name or ''"/>
    <t t-out="object.amount_total or 0"/>
    <t t-out="object.amount_residual or 0"/>
    <t t-out="object.invoice_date_due or ''"/>
    <t t-out="object.currency_id.symbol or ''"/>
    <t t-out="object.company_id.name or ''"/>

  sale.order:
    <t t-out="object.name or ''"/>
    <t t-out="object.partner_id.name or ''"/>
    <t t-out="object.amount_total or 0"/>
    <t t-out="object.date_order or ''"/>
    <t t-out="object.user_id.name or ''"/>

  res.partner:
    <t t-out="object.name or ''"/>
    <t t-out="object.email or ''"/>
    <t t-out="object.phone or ''"/>
    <t t-out="object.city or ''"/>

  Always available (any model):
    <t t-out="user.name or ''"/>
    <t t-out="user.email_formatted or ''"/>

═══════════════════════════════════════════════════════════
STEP 2 — WRITE MODERN HTML WITH QWEB SYNTAX
═══════════════════════════════════════════════════════════

LAYOUT RULES:
  - Outer wrapper: <table width="100%"> with background color
  - Center column: <table width="600"> max-width:600px
  - ALL CSS must be inline style="" — no <style> blocks
  - Use <t t-out="object.field or ''"/> for ALL dynamic values

WORKING EXAMPLE — Job Offer Letter (hr.employee):

<table width="100%" cellpadding="0" cellspacing="0"
       style="background:#F0FDF4;font-family:Arial,sans-serif;">
<tr><td align="center" style="padding:30px 15px;">
<table width="600" cellpadding="0" cellspacing="0"
       style="max-width:600px;background:#fff;border-radius:16px;
              overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

  <!-- HERO -->
  <tr><td style="background:linear-gradient(135deg,#059669,#0D9488);
                 padding:48px 40px;text-align:center;">
    <div style="font-size:52px;margin-bottom:16px;">🎉</div>
    <h1 style="margin:0;color:#fff;font-size:30px;font-weight:800;">
      Congratulations, <t t-out="object.name or 'Employee'"/>!
    </h1>
  </td></tr>

  <!-- GREETING -->
  <tr><td style="padding:36px 40px 0;">
    <p style="margin:0;color:#374151;font-size:16px;line-height:1.8;">
      Dear <strong><t t-out="object.name or 'Employee'"/></strong>,
    </p>
    <p style="margin:14px 0 0;color:#374151;font-size:16px;line-height:1.8;">
      We are delighted to offer you a position at
      <strong><t t-out="object.company_id.name or ''"/></strong>.
    </p>
  </td></tr>

  <!-- DETAILS CARD -->
  <tr><td style="padding:24px 40px;">
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:#F0FDF4;border-radius:12px;
                  border:1px solid #A7F3D0;">
      <tr><td style="padding:14px 20px;background:#059669;">
        <p style="margin:0;color:#fff;font-size:13px;font-weight:700;
                  text-transform:uppercase;">Your Offer Details</p>
      </td></tr>
      <tr><td style="padding:0 20px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding:12px 0;border-bottom:1px solid #D1FAE5;
                       color:#6B7280;font-size:14px;width:40%;font-weight:600;">
              Position
            </td>
            <td style="padding:12px 0;border-bottom:1px solid #D1FAE5;
                       color:#111827;font-size:14px;font-weight:700;">
              <t t-out="object.job_id.name or 'N/A'"/>
            </td>
          </tr>
          <tr>
            <td style="padding:12px 0;border-bottom:1px solid #D1FAE5;
                       color:#6B7280;font-size:14px;font-weight:600;">
              Department
            </td>
            <td style="padding:12px 0;border-bottom:1px solid #D1FAE5;
                       color:#111827;font-size:14px;">
              <t t-out="object.department_id.name or 'N/A'"/>
            </td>
          </tr>
          <tr>
            <td style="padding:12px 0;border-bottom:1px solid #D1FAE5;
                       color:#6B7280;font-size:14px;font-weight:600;">
              Manager
            </td>
            <td style="padding:12px 0;border-bottom:1px solid #D1FAE5;
                       color:#111827;font-size:14px;">
              <t t-out="object.parent_id.name or 'N/A'"/>
            </td>
          </tr>
          <tr>
            <td style="padding:12px 0;color:#6B7280;font-size:14px;
                       font-weight:600;">Work Email</td>
            <td style="padding:12px 0;color:#111827;font-size:14px;">
              <t t-out="object.work_email or ''"/>
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
  </td></tr>

  <!-- CTA -->
  <tr><td style="padding:28px 40px 36px;text-align:center;">
    <a href="#" style="display:inline-block;padding:14px 40px;
       background:linear-gradient(135deg,#059669,#0D9488);
       color:#fff;text-decoration:none;border-radius:30px;
       font-size:15px;font-weight:700;">
      Accept Offer
    </a>
    <p style="margin:14px 0 0;color:#9CA3AF;font-size:12px;">
      Questions? Contact <t t-out="user.email_formatted or ''"/>
    </p>
  </td></tr>

  <!-- FOOTER -->
  <tr><td style="background:#F9FAFB;padding:20px 40px;
                 border-top:1px solid #E5E7EB;text-align:center;
                 color:#9CA3AF;font-size:12px;">
    <t t-out="object.company_id.name or ''"/> ·
    Sent by <t t-out="user.name or ''"/><br/>
    <a href="#" style="color:#9CA3AF;">Unsubscribe</a>
  </td></tr>

</table>
</td></tr>
</table>

═══════════════════════════════════════════════════════════
STEP 3 — CREATE THE TEMPLATE
═══════════════════════════════════════════════════════════

  odoo_email_template(
      action    = 'create',
      name      = '<name>',
      subject   = '{{ object.name }} — <subject>',
      body_html = '<your HTML with <t t-out="..."/> for all dynamic values>',
      model     = '<model from Step 1>',
      email_to  = '{{ object.work_email }}',
  )

SUBJECT uses Jinja2:  subject = "Hello {{ object.name }}"
BODY uses QWeb:       <t t-out="object.name or ''"/>

═══════════════════════════════════════════════════════════
STEP 4 — PREVIEW WITH REAL DATA
═══════════════════════════════════════════════════════════

  odoo_search_read(model='<model>', fields=['id','name'], limit=3)

  odoo_email_template(action='preview', id=<template_id>, record_id=<id>)

Show rendered_subject and rendered_body with real values.

═══════════════════════════════════════════════════════════
NEVER DO THESE
═══════════════════════════════════════════════════════════

❌ {{ object.name }} inside body_html — NEVER rendered in Odoo 19 body
❌ ${object.name} inside body_html — removed in Odoo 19
❌ [Placeholder] text anywhere
❌ <style> blocks — inline CSS only
❌ odoo_create for email models
✅ <t t-out="object.field or ''"/> for ALL dynamic values in body
✅ {{ object.field }} only in subject/email_to/email_from
""" + _SYSTEM_PROMPT

# ═══════════════════════════════════════════════════════════════════════════
# MCP_PROMPTS — full list
# ═══════════════════════════════════════════════════════════════════════════

_PROMPT_BULK_CRUD = """═══════════════════════════════════════════════════════════════════
BULK CRUD RULES FOR ODOO MCP TOOLS
═══════════════════════════════════════════════════════════════════
These rules MUST be followed for all create, write and delete operations.

═══ BULK CREATE (odoo_create) ════════════════════════════════════

✔ CORRECT — ONE call with a LIST for multiple records:
  odoo_create(
    model  = "res.partner",
    values = [
      {"name": "Alice", "email": "alice@demo.com", "customer_rank": 1},
      {"name": "Bob",   "email": "bob@demo.com",   "customer_rank": 1},
      {"name": "Carol", "email": "carol@demo.com", "customer_rank": 1}
    ]
  )
  → Returns: {"ids": [101, 102, 103], "count": 3}

✔ CORRECT — single dict for one record:
  odoo_create(model="res.partner", values={"name": "Alice"})

❌ WRONG — calling odoo_create three times (wastes 3 round-trips):
  odoo_create(..., values={"name": "Alice"})
  odoo_create(..., values={"name": "Bob"})
  odoo_create(..., values={"name": "Carol"})

═══ BULK WRITE (odoo_write) ══════════════════════════════════════

Mode A — SAME values to multiple IDs (one call):
  odoo_write(model="res.partner", ids=[101, 102, 103], values={"active": False})

Mode B — DIFFERENT values per record (one call with 'records' list):
  odoo_write(
    model   = "res.partner",
    records = [
      {"ids": [101], "values": {"name": "Alice Updated", "phone": "111"}},
      {"ids": [102], "values": {"name": "Bob Updated",   "phone": "222"}}
    ]
  )
  → Returns: {"total_updated": 2}

❌ WRONG — calling odoo_write once per record. Use Mode B records list instead.

═══ BULK DELETE (odoo_unlink) ════════════════════════════════════

Always pass ALL ids in one call:
  odoo_unlink(model="res.partner", ids=[101, 102, 103])
  ❌ NOT: calling odoo_unlink once per id.
""" + _SYSTEM_PROMPT

_PROMPT_IMPORT_DATA = """═══════════════════════════════════════════════════════════════════
FILE IMPORT RULES FOR ODOO MCP TOOLS
═══════════════════════════════════════════════════════════════════
Use these rules whenever the user mentions CSV, Excel, XLSX, XLS, TSV, JSON,
spreadsheet, upload, import, or asks to create contacts/leads/products from a file.

PRIMARY TOOL:
  odoo_import_data

NEVER DO THESE:
  ❌ Do not use odoo_execute_orm to open uploaded files or paths like /mnt/data/...
  ❌ Do not ask the user to paste the file manually if the file is already uploaded
  ❌ Do not convert a file import request into repeated odoo_create calls unless the
     file has already been parsed into rows and you are explicitly not using import

VALID INPUT PATTERNS:
  odoo_import_data(
    model="res.partner",
    file_content="name,email\\nAlice,a@a.com\\nBob,b@b.com"
  )

  odoo_import_data(
    model="res.partner",
    records=[
      {"name": "Alice", "email": "a@a.com"},
      {"name": "Bob", "email": "b@b.com"}
    ]
  )

  odoo_import_data(
    model="res.partner",
    headers=["name", "email"],
    rows=[["Alice", "a@a.com"], ["Bob", "b@b.com"]]
  )

SAFE FLOW:
  1. If column mapping is uncertain, call odoo_import_data with dry_run=true first
  2. Check mapped_columns / preview / row count
  3. Then call odoo_import_data again with dry_run=false
  4. Report the imported count and created ids returned by the tool

COMMON TARGETS:
  Contacts  -> model="res.partner"
  Leads     -> model="crm.lead"
  Products  -> model="product.template" or "product.product"
  Employees -> model="hr.employee"

SUCCESS RULE:
  Only say records were imported if odoo_import_data actually returned success.
  If the import tool failed, say it failed and use the returned error message.
""" + _SYSTEM_PROMPT


# ═══════════════════════════════════════════════════════════════════════════
# _PROMPT_PORTAL_APP — dedicated full-portal generator
# Triggered when user types "portal" or any business portal keyword.
# Always builds the COMPLETE multi-page app with all 9 pages and full CRUD.
# ═══════════════════════════════════════════════════════════════════════════

_PROMPT_PORTAL_APP = """\
╔══════════════════════════════════════════════════════════════════════════════╗
║  PORTAL GENERATOR — MANDATORY RULES (read all before writing any code)     ║
╚══════════════════════════════════════════════════════════════════════════════╝

Call odoo_manage_webapp(action='create', ...) IMMEDIATELY with the full portal.

══════════════════════════════════════════════════════════════════════════════════
⚡ TRIGGER: User typed "portal" or any portal/business/ERP keyword.
   → You MUST build the COMPLETE multi-page app. NO excuses. NO simplified version.
   → ALL 9 pages are REQUIRED: Dashboard · Orders · Customers · Products ·
     Invoices · Purchases · Analytics · Payments · Employees.
   → ALL data MUST be live from Odoo ORM. ZERO localStorage. ZERO mock data.
   → Full CRUD (Create/Edit/Delete) on every page.
   → Portal-user isolation: filter by portal_partner_id when portal_uid is set.
   → NEVER build a simple single-page app — the user expects a full ERP portal.
══════════════════════════════════════════════════════════════════════════════════

DESIGN SPEC (follow exactly):
  Background:  #0f172a   | Sidebar: #0a0f1e, width 220, border-right #1e293b
  Cards:       #1e293b, border #334155, radius 12, padding 20
  Primary btn: #6366f1, white, radius 8, padding 8px 18px, weight 600
  Table head:  #0f172a, color #64748b, font-size 10, uppercase
  Table row:   border-bottom #1e293b, color #cbd5e1
  Input:       #0f172a bg, border #334155, color #e2e8f0, radius 8
  Badge draft: bg #1e293b fg #94a3b8 | confirmed/sale/purchase: bg #1e3a5f fg #93c5fd
  Badge done:  bg #064e3b fg #6ee7b7 | cancel: bg #450a0a fg #fca5a5
  Badge paid:  bg #064e3b fg #6ee7b7 | not_paid: bg #451a03 fg #fcd34d
  Font: 'DM Sans', system-ui, sans-serif

NAVIGATION PAGES (sidebar — ALL REQUIRED):
  dashboard · orders · customers · products · invoices · purchases · analytics · payments · employees

══════════════════════════════════════════════════════════════════════════════════
JSX SKELETON — copy EXACTLY, flesh out every page component below
══════════════════════════════════════════════════════════════════════════════════

function App() {{
  const [page, setPage]         = useState('dashboard');
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(true);
  const [toast, setToast]       = useState(null);
  const [modal, setModal]       = useState(null);
  const [search, setSearch]     = useState('');
  const [filter, setFilter]     = useState('all');
  const [sideOpen, setSideOpen] = useState(true);
  const [saving, setSaving]     = useState(false);
  const portal = window.odoo.portal || {{}};

  // ── All form state in ref — prevents focus-loss bug on typing ────────────
  const formRef = useRef({{}});
  const lineItemsRef = useRef([]);

  const showToast = (msg, kind='success') => {{
    setToast({{msg,kind}}); setTimeout(()=>setToast(null), 3200);
  }};

  const load = async (pg=page, extra={{}}) => {{
    setLoading(true); setData(null);
    try {{
      const d = await window.odoo.fetch({{page:pg, search, filter, ...extra}});
      setData(d);
    }} catch(e) {{ showToast(e.message,'error'); }}
    finally {{ setLoading(false); }}
  }};
  useEffect(() => {{ load(); }}, [page, filter]);

  // ── FIELD DEFINITIONS — keys MUST match data_code FIELD_MAP ─────────────
  const FIELD_DEFS = {{
    contacts:  [{{f:'name',l:'Name',t:'text',req:true}},{{f:'email',l:'Email',t:'email'}},
                {{f:'phone',l:'Phone',t:'text'}},{{f:'street',l:'Street',t:'text'}},
                {{f:'city',l:'City',t:'text'}},{{f:'comment',l:'Notes',t:'textarea'}}],
    customers: [{{f:'name',l:'Name',t:'text',req:true}},{{f:'email',l:'Email',t:'email'}},
                {{f:'phone',l:'Phone',t:'text'}},{{f:'street',l:'Street',t:'text'}},
                {{f:'city',l:'City',t:'text'}},{{f:'comment',l:'Notes',t:'textarea'}}],
    orders:    [{{f:'state',l:'Status',t:'select',opts:[{{v:'draft',l:'Quotation'}},{{v:'sale',l:'Confirmed'}},{{v:'done',l:'Done'}},{{v:'cancel',l:'Cancelled'}}]}},
                {{f:'note',l:'Notes',t:'textarea'}}],
    purchases: [{{f:'state',l:'Status',t:'select',opts:[{{v:'draft',l:'Draft'}},{{v:'purchase',l:'Confirmed'}},{{v:'done',l:'Done'}},{{v:'cancel',l:'Cancelled'}}]}},
                {{f:'notes',l:'Notes',t:'textarea'}}],
    products:  [{{f:'name',l:'Name',t:'text',req:true}},{{f:'list_price',l:'Sale Price',t:'number'}},
                {{f:'standard_price',l:'Cost',t:'number'}},
                {{f:'type',l:'Type',t:'select',opts:[{{v:'product',l:'Storable'}},{{v:'consu',l:'Consumable'}},{{v:'service',l:'Service'}}]}},
                {{f:'description',l:'Description',t:'textarea'}}],
    invoices:  [{{f:'payment_state',l:'Payment',t:'select',opts:[{{v:'not_paid',l:'Unpaid'}},{{v:'in_payment',l:'In Payment'}},{{v:'paid',l:'Paid'}}]}}],
    employees: [{{f:'name',l:'Full Name',t:'text',req:true}},{{f:'job_title',l:'Job Title',t:'text'}},
                {{f:'work_email',l:'Work Email',t:'email'}},{{f:'work_phone',l:'Work Phone',t:'text'}}],
  }};

  const getFormFields = (model) => FIELD_DEFS[model] || FIELD_DEFS.customers;
  const pickFormValues = (model, rec) => {{
    const out = {{}};
    getFormFields(model).forEach(fd => {{ if (rec[fd.f] !== undefined) out[fd.f] = rec[fd.f]; }});
    return out;
  }};

  // ── CRUD helpers ──────────────────────────────────────────────────────────
  const openCreate = (model) => {{ formRef.current = {{}}; lineItemsRef.current = []; setModal({{type:'create',model}}); }};
  const openEdit   = (model, rec) => {{ formRef.current = pickFormValues(model,rec); lineItemsRef.current = rec.lines?.map(l=>({{...l}})) || []; setModal({{type:'edit',model,rec}}); }};
  const openView   = (model, rec) => {{ lineItemsRef.current = rec.lines?.map(l=>({{...l}})) || []; setModal({{type:'view',model,rec}}); }};
  const closeModal = () => {{ setModal(null); formRef.current = {{}}; lineItemsRef.current = []; }};

  const handleSave = async () => {{
    setSaving(true);
    try {{
      const isEdit = modal.type === 'edit';
      const d = await window.odoo.fetch({{ action: isEdit?'write':'create', model:modal.model,
        values:{{...formRef.current}}, ...(isEdit?{{id:modal.rec.id}}:{{}}) }});
      if (d.error) throw new Error(d.error);
      showToast(isEdit?'Updated ✓':'Created ✓'); closeModal(); load();
    }} catch(e) {{ showToast(e.message,'error'); }}
    finally {{ setSaving(false); }}
  }};

  const handleDelete = async (model, id, name) => {{
    if (!confirm('Delete "' + name + '"?')) return;
    try {{
      const d = await window.odoo.fetch({{action:'unlink', model, id}});
      if (d.error) throw new Error(d.error);
      showToast('Deleted ✓'); load();
    }} catch(e) {{ showToast(e.message,'error'); }}
  }};

  const handleLineAdd = async (orderId, orderModel, lineData) => {{
    const d = await window.odoo.fetch({{action:'line_add', model:orderModel, id:orderId, values:lineData}});
    if (d.error) throw new Error(d.error);
    showToast('Line added ✓'); load(page, {{detail_id:orderId}});
  }};
  const handleLineUpdate = async (orderId, orderModel, lineId, lineData) => {{
    const d = await window.odoo.fetch({{action:'line_update', model:orderModel, id:orderId, line_id:lineId, values:lineData}});
    if (d.error) throw new Error(d.error);
    showToast('Line updated ✓'); load(page, {{detail_id:orderId}});
  }};
  const handleLineDelete = async (orderId, orderModel, lineId) => {{
    if (!confirm('Remove this line?')) return;
    const d = await window.odoo.fetch({{action:'line_delete', model:orderModel, id:orderId, line_id:lineId}});
    if (d.error) throw new Error(d.error);
    showToast('Line removed ✓'); load(page, {{detail_id:orderId}});
  }};

  // ── NAV ───────────────────────────────────────────────────────────────────
  const NAV = [
    {{id:'dashboard', icon:'📊', label:'Dashboard'}},
    {{id:'orders',    icon:'🛒', label:'Sales Orders'}},
    {{id:'invoices',  icon:'🧾', label:'Invoices'}},
    {{id:'customers', icon:'👥', label:'Customers'}},
    {{id:'products',  icon:'📦', label:'Products'}},
    {{id:'purchases', icon:'🏭', label:'Purchases', hidden:portal.is_portal}},
    {{id:'analytics', icon:'📈', label:'Analytics'}},
    {{id:'payments',  icon:'💳', label:'Payments'}},
    {{id:'employees', icon:'👤', label:'Employees', hidden:portal.is_portal}},
  ].filter(n=>!n.hidden);

  // ── STATUS BADGE ──────────────────────────────────────────────────────────
  const BADGE_MAP = {{
    draft:{{bg:'#1e293b',fg:'#94a3b8'}},sale:{{bg:'#1e3a5f',fg:'#93c5fd'}},
    purchase:{{bg:'#1e3a5f',fg:'#93c5fd'}},confirmed:{{bg:'#1e3a5f',fg:'#93c5fd'}},
    done:{{bg:'#064e3b',fg:'#6ee7b7'}},posted:{{bg:'#1e3a5f',fg:'#93c5fd'}},
    cancel:{{bg:'#450a0a',fg:'#fca5a5'}},paid:{{bg:'#064e3b',fg:'#6ee7b7'}},
    not_paid:{{bg:'#451a03',fg:'#fcd34d'}},in_payment:{{bg:'#1e1b4b',fg:'#a5b4fc'}},
  }};
  const Badge = ({{s}}) => {{
    const c = BADGE_MAP[s] || {{bg:'#1e293b',fg:'#94a3b8'}};
    return <span style={{{{padding:'2px 8px',borderRadius:12,fontSize:11,background:c.bg,color:c.fg,fontWeight:600}}}}>{s}</span>;
  }};

  // ── SEARCH BAR ────────────────────────────────────────────────────────────
  const SearchBar = ({{onSearch}}) => (
    <div style={{{{display:'flex',gap:8,marginBottom:16}}}}>
      <input placeholder="Search…" defaultValue={{search}}
        onChange={{e=>setSearch(e.target.value)}}
        onKeyDown={{e=>e.key==='Enter'&&onSearch()}}
        style={{{{flex:1,background:'#0f172a',border:'1px solid #334155',color:'#e2e8f0',borderRadius:8,padding:'8px 12px'}}}}/>
      <button onClick={{onSearch}}
        style={{{{background:'#6366f1',color:'#fff',border:'none',borderRadius:8,padding:'8px 16px',fontWeight:600,cursor:'pointer'}}}}>Search</button>
    </div>
  );

  // ── FILTER TABS ───────────────────────────────────────────────────────────
  const FilterTabs = ({{tabs}}) => (
    <div style={{{{display:'flex',gap:4,marginBottom:16,flexWrap:'wrap'}}}}>
      {{tabs.map(t => (
        <button key={{t.v}} onClick={{()=>setFilter(t.v)}}
          style={{{{padding:'5px 14px',borderRadius:20,fontSize:12,cursor:'pointer',
            background:filter===t.v?'#6366f1':'#1e293b',color:filter===t.v?'#fff':'#94a3b8',
            border:filter===t.v?'none':'1px solid #334155',fontWeight:500}}}}>{{t.l}}</button>
      ))}}
    </div>
  );

  // ── CRUD MODAL ────────────────────────────────────────────────────────────
  const CrudModal = () => {{
    if (!modal) return null;
    const fields = getFormFields(modal.model);
    const isView = modal.type === 'view';
    const recId  = modal.rec?.id ?? 'new';
    return (
      <div style={{{{position:'fixed',inset:0,background:'rgba(0,0,0,0.7)',zIndex:50,display:'flex',alignItems:'center',justifyContent:'center'}}}}>
        <div style={{{{background:'#1e293b',border:'1px solid #334155',borderRadius:16,padding:28,width:'100%',maxWidth:540,maxHeight:'85vh',overflowY:'auto'}}}}>
          <div style={{{{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:20}}}}>
            <h3 style={{{{color:'#e2e8f0',margin:0}}}}>{{modal.type==='view'?'View':modal.type==='edit'?'Edit':'New'}} — {{modal.model}}</h3>
            <button onClick={{closeModal}} style={{{{background:'none',border:'none',color:'#94a3b8',fontSize:20,cursor:'pointer'}}}}>✕</button>
          </div>
          {{fields.map(fd => (
            <div key={{fd.f}} style={{{{marginBottom:14}}}}>
              <label style={{{{display:'block',color:'#94a3b8',fontSize:12,marginBottom:4}}}}>{{fd.l}}{{fd.req?' *':''}}</label>
              {{fd.t==='select'?(
                <select key={{fd.f+'-'+recId}} defaultValue={{formRef.current[fd.f]??''}}
                  onChange={{e=>{{formRef.current[fd.f]=e.target.value;}}}} disabled={{isView}}
                  style={{{{width:'100%',background:'#0f172a',border:'1px solid #334155',color:'#e2e8f0',borderRadius:8,padding:'8px 12px'}}}}>
                  <option value=''>— select —</option>
                  {{(fd.opts||[]).map(o=><option key={{o.v}} value={{o.v}}>{{o.l}}</option>)}}
                </select>
              ):fd.t==='textarea'?(
                <textarea key={{fd.f+'-'+recId}} defaultValue={{formRef.current[fd.f]??''}}
                  onChange={{e=>{{formRef.current[fd.f]=e.target.value;}}}} readOnly={{isView}} rows={{3}}
                  style={{{{width:'100%',background:'#0f172a',border:'1px solid #334155',color:'#e2e8f0',borderRadius:8,padding:'8px 12px',resize:'vertical',boxSizing:'border-box'}}}}/>
              ):(
                <input key={{fd.f+'-'+recId}} type={{fd.t||'text'}}
                  defaultValue={{formRef.current[fd.f]??''}} readOnly={{isView}}
                  onChange={{e=>{{formRef.current[fd.f]=e.target.value;}}}}
                  style={{{{width:'100%',background:'#0f172a',border:'1px solid #334155',color:'#e2e8f0',borderRadius:8,padding:'8px 12px',boxSizing:'border-box'}}}}/>
              )}}
            </div>
          ))}}
          {{!isView&&(
            <div style={{{{display:'flex',justifyContent:'flex-end',gap:10,marginTop:20}}}}>
              <button onClick={{closeModal}} style={{{{border:'1px solid #334155',background:'transparent',color:'#94a3b8',borderRadius:6,padding:'8px 16px',cursor:'pointer'}}}}>Cancel</button>
              <button onClick={{handleSave}} disabled={{saving}}
                style={{{{background:'#6366f1',color:'#fff',border:'none',borderRadius:8,padding:'8px 18px',fontWeight:600,cursor:'pointer',opacity:saving?0.6:1}}}}>
                {{saving?'Saving…':'Save'}}
              </button>
            </div>
          )}}
        </div>
      </div>
    );
  }};

  // ── PAGE COMPONENTS (implement fully): ────────────────────────────────────
  //
  // DASHBOARD: 6 KPI cards (total_revenue,order_count,pending_invoices,active_customers,avg_order,collection_rate)
  //   + Chart.js line chart (data.monthly_revenue: array of {{label,value}})
  //   + Chart.js donut chart (data.by_state: array of {{state,count}})
  //   + Recent orders table (data.recent_orders: array of {{id,name,partner,date,amount,state}})
  //
  // ORDERS: FilterTabs [All/Quotation/Confirmed/Done/Cancelled] + SearchBar
  //   Table: Name|Customer|Date|Amount|Status + View/Edit/Delete
  //   Detail view (load detail_id): order header + line items table with Add/Edit/Remove
  //   line item fields: product_id_name(text), product_uom_qty(number), price_unit(number), name(text)
  //
  // CUSTOMERS: SearchBar + Table: Name|Email|Phone|City|Country + Create/Edit/Delete
  //   HIDDEN for portal.is_portal
  //
  // PRODUCTS: SearchBar + Grid cards: Name,Category,Price,Cost,Type + Create/Edit/Delete
  //   ⚠ NEVER use qty_available — wrong model
  //
  // INVOICES: FilterTabs [All/Draft/Sent/Paid/Overdue] + SearchBar
  //   Table: Invoice#|Customer|Date|Due|Amount|Status + detail with line items
  //
  // PURCHASES: FilterTabs [All/Draft/Confirmed/Done/Cancelled] + same as orders
  //   HIDDEN for portal.is_portal
  //
  // ANALYTICS: Three Chart.js canvases in a grid:
  //   1. Bar chart — monthly revenue (data.monthly_revenue)
  //   2. Donut chart — orders by state (data.by_state)
  //   3. Horizontal bar — top 10 products (data.top_products)
  //   Use useEffect + canvas refs to init Chart.js. Destroy old chart before re-creating.
  //
  // PAYMENTS: Table: Ref|Partner|Amount|Date|Type|Journal|State
  //
  // EMPLOYEES: Grid cards with avatar initial bubble, name, job, dept, email, phone
  //   HIDDEN for portal.is_portal

  const renderPage = () => {{
    // implement switch on `page`:
    // 'dashboard' → <DashboardPage data={{data}} .../>
    // 'orders'    → <OrdersPage data={{data}} load={{load}} openView={{openView}} openEdit={{openEdit}} handleDelete={{handleDelete}} handleLineAdd={{handleLineAdd}} handleLineUpdate={{handleLineUpdate}} handleLineDelete={{handleLineDelete}} Badge={{Badge}} SearchBar={{SearchBar}} FilterTabs={{FilterTabs}} openCreate={{openCreate}} portal={{portal}} />
    // ... etc for all 9 pages
  }};

  const LINE_FIELD_DEFS = {{
    orders:    [{{f:'product_id_name',l:'Product',t:'text',req:true}},{{f:'product_uom_qty',l:'Qty',t:'number'}},{{f:'price_unit',l:'Unit Price',t:'number'}},{{f:'name',l:'Description',t:'text'}}],
    purchases: [{{f:'product_id_name',l:'Product',t:'text',req:true}},{{f:'product_qty',l:'Qty',t:'number'}},{{f:'price_unit',l:'Unit Price',t:'number'}},{{f:'name',l:'Description',t:'text'}}],
    invoices:  [{{f:'name',l:'Description',t:'text',req:true}},{{f:'quantity',l:'Qty',t:'number'}},{{f:'price_unit',l:'Unit Price',t:'number'}}],
  }};

  return (
    <div style={{{{display:'flex',background:'#0f172a',minHeight:'100vh',color:'#e2e8f0',fontFamily:"'DM Sans',system-ui,sans-serif"}}}}>
      <nav style={{{{width:sideOpen?220:0,minWidth:sideOpen?220:0,background:'#0a0f1e',borderRight:'1px solid #1e293b',transition:'width .2s',overflow:'hidden',flexShrink:0}}}}>
        <div style={{{{padding:'20px 16px 12px'}}}}>
          <div style={{{{fontWeight:700,fontSize:16,color:'#e2e8f0',marginBottom:4}}}}>⚡ BizPortal</div>
          <div style={{{{fontSize:11,color:'#475569'}}}}>{{portal.name||'Staff View'}}</div>
        </div>
        {{NAV.map(n=>(
          <button key={{n.id}} onClick={{()=>{{setPage(n.id);setFilter('all');setSearch('');}}}}
            style={{{{width:'100%',textAlign:'left',padding:'10px 16px',border:'none',cursor:'pointer',
              background:page===n.id?'rgba(99,102,241,0.08)':'transparent',
              color:page===n.id?'#6366f1':'#94a3b8',
              borderLeft:page===n.id?'3px solid #6366f1':'3px solid transparent',
              fontSize:13,fontWeight:page===n.id?600:400,display:'flex',alignItems:'center',gap:8}}}}>
            {{n.icon}} {{n.label}}
          </button>
        ))}}
      </nav>
      <div style={{{{flex:1,display:'flex',flexDirection:'column',overflow:'hidden'}}}}>
        <header style={{{{background:'#0a0f1e',borderBottom:'1px solid #1e293b',padding:'12px 20px',display:'flex',alignItems:'center',justifyContent:'space-between'}}}}>
          <div style={{{{display:'flex',alignItems:'center',gap:12}}}}>
            <button onClick={{()=>setSideOpen(o=>!o)}} style={{{{background:'none',border:'none',color:'#64748b',fontSize:18,cursor:'pointer'}}}}>☰</button>
            <span style={{{{fontSize:15,fontWeight:600,color:'#e2e8f0',textTransform:'capitalize'}}}}>{{NAV.find(n=>n.id===page)?.label||page}}</span>
          </div>
          <div style={{{{fontSize:12,color:'#475569'}}}}>{{portal.is_portal?'Portal User':'Internal Staff'}}</div>
        </header>
        <main style={{{{flex:1,overflowY:'auto',padding:24}}}}>
          {{loading && <div style={{{{textAlign:'center',color:'#475569',paddingTop:60}}}}>Loading…</div>}}
          {{!loading && data?.error && <div style={{{{color:'#ef4444',padding:20}}}}>{{data.error}}</div>}}
          {{!loading && data && renderPage()}}
        </main>
      </div>
      <CrudModal />
      {{toast && (
        <div style={{{{position:'fixed',bottom:24,right:24,padding:'12px 20px',borderRadius:10,fontWeight:600,zIndex:100,
          background:toast.kind==='error'?'#450a0a':'#064e3b',color:toast.kind==='error'?'#fca5a5':'#6ee7b7'}}}}>
          {{toast.msg}}
        </div>
      )}}
    </div>
  );
}}

══════════════════════════════════════════════════════════════════════════════════
DATA_CODE — UNIVERSAL PYTHON BACKEND (use EXACTLY this template)
══════════════════════════════════════════════════════════════════════════════════

Handles all 9 pages + full CRUD + line items. Copy into data_code parameter.

```python
try:
    import datetime as _dt
    action = params.get('action')
    page   = params.get('page', 'dashboard')
    search = (params.get('search') or '').strip()
    filt   = (params.get('filter') or 'all').strip()
    is_portal = bool(portal_partner_id)
    pid       = portal_partner_id

    MODEL_MAP = {{
        'contacts':'res.partner','customers':'res.partner',
        'orders':'sale.order','invoices':'account.move',
        'purchases':'purchase.order','products':'product.template',
        'employees':'hr.employee','payments':'account.payment','analytics':'sale.order',
    }}
    LINE_MODEL_MAP = {{
        'sale.order':'sale.order.line','purchase.order':'purchase.order.line','account.move':'account.move.line',
    }}
    LINE_PARENT_FIELD = {{
        'sale.order.line':'order_id','purchase.order.line':'order_id','account.move.line':'move_id',
    }}
    FIELD_MAP = {{
        'res.partner':{{'name':'name','email':'email','phone':'phone','street':'street','city':'city','comment':'comment'}},
        'sale.order':{{'state':'state','note':'note'}},
        'purchase.order':{{'state':'state','notes':'notes'}},
        'product.template':{{'name':'name','list_price':'list_price','standard_price':'standard_price','type':'type','description':'description'}},
        'account.move':{{'payment_state':'payment_state'}},
        'hr.employee':{{'name':'name','job_title':'job_title','work_email':'work_email','work_phone':'work_phone'}},
        'account.payment':{{'amount':'amount','payment_type':'payment_type','memo':'memo'}},
        'sale.order.line':{{'product_id_name':'product_id','product_uom_qty':'product_uom_qty','price_unit':'price_unit','name':'name'}},
        'purchase.order.line':{{'product_id_name':'product_id','product_qty':'product_qty','price_unit':'price_unit','name':'name'}},
        'account.move.line':{{'name':'name','quantity':'quantity','price_unit':'price_unit'}},
    }}

    def _crud_values(mn, raw):
        fm=FIELD_MAP.get(mn,{{}}); valid=set(env[mn].fields_get().keys()); out={{}}
        for k,v in (raw or {{}}).items():
            real=fm.get(k,k)
            if real in valid and v is not None and v!='':
                fi=env[mn].fields_get().get(real,{{}})
                if fi.get('type') in ('integer','float','monetary') and isinstance(v,str):
                    try: v=float(v)
                    except: pass
                out[real]=v
        return out

    def _resolve_product_id(mn, vals):
        if 'product_id' in vals and isinstance(vals['product_id'],str):
            name=vals['product_id'].strip()
            prod=env['product.product'].search([('name','ilike',name)],limit=1)
            if prod: vals['product_id']=prod.id
            else:
                pt=env['product.template'].search([('name','ilike',name)],limit=1)
                if pt and pt.product_variant_id: vals['product_id']=pt.product_variant_id.id
                else: raise ValueError(f"Product not found: {{name}}")
        return vals

    if action=='create':
        mk=params.get('model',''); mn=MODEL_MAP.get(mk)
        if not mn: result={{'error':f'Unknown model: {{mk}}'}}
        else:
            vals=_crud_values(mn,params.get('values'))
            if not vals: result={{'error':f'No valid fields for {{mn}}'}}
            else:
                if mn=='res.partner' and 'customer_rank' not in vals: vals['customer_rank']=1
                result={{'ok':True,'id':env[mn].create(vals).id}}

    elif action=='write':
        mk=params.get('model',''); mn=MODEL_MAP.get(mk); rid=int(params.get('id') or 0)
        if not mn or not rid: result={{'error':'model and id required'}}
        else:
            rec=env[mn].browse(rid)
            if not rec.exists(): result={{'error':f'Record {{rid}} not found'}}
            elif is_portal and hasattr(rec,'partner_id') and rec.partner_id.id!=pid: result={{'error':'Access denied'}}
            else: vals=_crud_values(mn,params.get('values')); rec.write(vals) if vals else None; result={{'ok':True}}

    elif action=='unlink':
        mk=params.get('model',''); mn=MODEL_MAP.get(mk); rid=int(params.get('id') or 0)
        if not mn or not rid: result={{'error':'model and id required'}}
        else:
            rec=env[mn].browse(rid)
            if not rec.exists(): result={{'error':f'Record {{rid}} not found'}}
            elif is_portal and hasattr(rec,'partner_id') and rec.partner_id.id!=pid: result={{'error':'Access denied'}}
            else: rec.unlink(); result={{'ok':True}}

    elif action=='line_add':
        mk=params.get('model',''); mn=MODEL_MAP.get(mk); rid=int(params.get('id') or 0)
        if not mn or not rid: result={{'error':'model and id required'}}
        else:
            lm=LINE_MODEL_MAP.get(mn); lpf=LINE_PARENT_FIELD.get(lm)
            if not lm: result={{'error':f'No line model for {{mn}}'}}
            else:
                vals=_crud_values(lm,params.get('values')); vals=_resolve_product_id(lm,vals); vals[lpf]=rid
                if lm=='sale.order.line' and 'product_uom_qty' not in vals: vals['product_uom_qty']=1.0
                if lm=='purchase.order.line' and 'product_qty' not in vals: vals['product_qty']=1.0
                if lm=='account.move.line' and 'quantity' not in vals: vals['quantity']=1.0
                result={{'ok':True,'line_id':env[lm].create(vals).id}}

    elif action=='line_update':
        mk=params.get('model',''); mn=MODEL_MAP.get(mk); lid=int(params.get('line_id') or 0)
        if not mn or not lid: result={{'error':'model and line_id required'}}
        else:
            lm=LINE_MODEL_MAP.get(mn)
            if not lm: result={{'error':f'No line model for {{mn}}'}}
            else:
                vals=_crud_values(lm,params.get('values')); vals=_resolve_product_id(lm,vals)
                line=env[lm].browse(lid)
                if line.exists(): line.write(vals); result={{'ok':True}}
                else: result={{'error':f'Line {{lid}} not found'}}

    elif action=='line_delete':
        mk=params.get('model',''); mn=MODEL_MAP.get(mk); lid=int(params.get('line_id') or 0)
        if not mn or not lid: result={{'error':'model and line_id required'}}
        else:
            lm=LINE_MODEL_MAP.get(mn)
            if not lm: result={{'error':f'No line model for {{mn}}'}}
            else:
                line=env[lm].browse(lid)
                if line.exists(): line.unlink(); result={{'ok':True}}
                else: result={{'error':f'Line {{lid}} not found'}}

    elif page=='dashboard':
        so_dom=[('partner_id','=',pid)] if is_portal else []
        inv_dom=([('partner_id','=',pid)] if is_portal else [])+[('move_type','in',['out_invoice','out_refund'])]
        orders=env['sale.order'].search_read(so_dom,['name','partner_id','amount_total','state','date_order'],order='date_order desc',limit=200)
        try: invoices=env['account.move'].search_read(inv_dom,['amount_total','payment_state','invoice_date_due'],limit=200)
        except: invoices=[]
        confirmed=[o for o in orders if o['state'] in ['sale','done']]
        total_rev=sum(o['amount_total'] or 0 for o in confirmed)
        paid_inv=sum(1 for i in invoices if i.get('payment_state')=='paid')
        pending=sum(1 for i in invoices if i.get('payment_state') not in ['paid','reversed'])
        monthly={{}}
        for o in confirmed:
            dt=o.get('date_order'); key=dt.strftime('%b %y') if hasattr(dt,'strftime') else str(dt)[:7]
            monthly[key]=round(monthly.get(key,0)+(o['amount_total'] or 0),2)
        try:
            sr=env['sale.order']._read_group(domain=so_dom,groupby=['state'],aggregates=['id:count'])
            by_state=[{{'state':r[0] or 'unknown','count':r[1] or 0}} for r in sr]
        except: by_state=[]
        result={{
            'kpis':{{'total_revenue':round(total_rev,2),'order_count':len(orders),
                'pending_invoices':pending,
                'active_customers':env['res.partner'].search_count([('customer_rank','>',0)]) if not is_portal else 1,
                'avg_order':round(total_rev/len(confirmed),2) if confirmed else 0,
                'collection_rate':round(paid_inv/len(invoices)*100,1) if invoices else 0}},
            'monthly_revenue':[{{'label':k,'value':v}} for k,v in list(monthly.items())[-6:]],
            'by_state':by_state,
            'recent_orders':[{{'id':o['id'],'name':o.get('name',''),
                'partner':(o.get('partner_id') or [0,''])[1],
                'date':o['date_order'].strftime('%d %b %Y') if hasattr(o.get('date_order'),'strftime') else str(o.get('date_order',''))[:10],
                'amount':round(o.get('amount_total') or 0,2),'state':o.get('state','')}} for o in orders[:5]],
        }}

    elif page=='orders':
        dom=[('partner_id','=',pid)] if is_portal else []
        if filt!='all': dom+=[('state','=',filt)]
        if search: dom+=['|',('name','ilike',search),('partner_id.name','ilike',search)]
        detail_id=params.get('detail_id')
        if detail_id:
            order=env['sale.order'].browse(int(detail_id))
            result={{'record':{{'id':order.id,'name':order.name,
                'partner':order.partner_id.name if order.partner_id else '','date':str(order.date_order or '')[:10],
                'amount':round(order.amount_total or 0,2),'state':order.state,
                'lines':[{{'id':ln.id,'product_name':ln.product_id.name if ln.product_id else '',
                    'product_id_name':ln.product_id.name if ln.product_id else '','name':ln.name or '',
                    'qty':ln.product_uom_qty,'price_unit':ln.price_unit,'subtotal':ln.price_subtotal}} for ln in order.order_line]}}}}
        else:
            rows=env['sale.order'].search_read(dom,['id','name','partner_id','date_order','amount_total','state','order_line'],order='date_order desc',limit=100)
            result={{'records':[{{'id':o['id'],'name':o.get('name',''),'partner':(o.get('partner_id') or [0,''])[1],
                'date':str(o.get('date_order',''))[:10],'amount':round(o.get('amount_total') or 0,2),
                'state':o.get('state',''),'line_count':len(o.get('order_line') or [])}} for o in rows]}}

    elif page=='purchases':
        if is_portal: result={{'records':[]}}
        else:
            dom=[]
            if filt!='all': dom+=[('state','=',filt)]
            if search: dom+=['|',('name','ilike',search),('partner_id.name','ilike',search)]
            detail_id=params.get('detail_id')
            if detail_id:
                po=env['purchase.order'].browse(int(detail_id))
                result={{'record':{{'id':po.id,'name':po.name,'partner':po.partner_id.name if po.partner_id else '',
                    'date':str(po.date_order or '')[:10],'amount':round(po.amount_total or 0,2),'state':po.state,
                    'lines':[{{'id':ln.id,'product_name':ln.product_id.name if ln.product_id else '',
                        'product_id_name':ln.product_id.name if ln.product_id else '','name':ln.name or '',
                        'qty':ln.product_qty,'price_unit':ln.price_unit,'subtotal':ln.price_subtotal}} for ln in po.order_line]}}}}
            else:
                rows=env['purchase.order'].search_read(dom,['id','name','partner_id','date_order','amount_total','state'],order='date_order desc',limit=100)
                result={{'records':[{{'id':p['id'],'name':p.get('name',''),'partner':(p.get('partner_id') or [0,''])[1],
                    'date':str(p.get('date_order',''))[:10],'amount':round(p.get('amount_total') or 0,2),'state':p.get('state','')}} for p in rows]}}

    elif page=='invoices':
        dom=([('partner_id','=',pid)] if is_portal else [])+[('move_type','in',['out_invoice','out_refund'])]
        if filt=='paid': dom+=[('payment_state','=','paid')]
        elif filt=='posted': dom+=[('state','=','posted'),('payment_state','!=','paid')]
        elif filt=='draft': dom+=[('state','=','draft')]
        if search: dom+=[('name','ilike',search)]
        detail_id=params.get('detail_id')
        if detail_id:
            inv=env['account.move'].browse(int(detail_id))
            result={{'record':{{'id':inv.id,'name':inv.name,'partner':inv.partner_id.name if inv.partner_id else '',
                'date':str(inv.invoice_date or '')[:10],'due':str(inv.invoice_date_due or '')[:10],
                'amount':round(inv.amount_total or 0,2),'payment_state':inv.payment_state,'state':inv.state,
                'lines':[{{'id':ln.id,'name':ln.name or '','product_name':ln.product_id.name if ln.product_id else '',
                    'qty':ln.quantity,'price_unit':ln.price_unit,'subtotal':ln.price_subtotal}} for ln in inv.invoice_line_ids]}}}}
        else:
            rows=env['account.move'].search_read(dom,['id','name','partner_id','invoice_date','invoice_date_due','amount_total','payment_state','state'],order='invoice_date desc',limit=100)
            today=_dt.date.today()
            result={{'records':[{{'id':i['id'],'name':i.get('name',''),'partner':(i.get('partner_id') or [0,''])[1],
                'date':str(i.get('invoice_date',''))[:10],'due':str(i.get('invoice_date_due',''))[:10],
                'amount':round(i.get('amount_total') or 0,2),'payment_state':i.get('payment_state',''),
                'state':i.get('state',''),
                'overdue':bool(i.get('invoice_date_due') and i.get('payment_state')!='paid'
                    and hasattr(i.get('invoice_date_due'),'year') and i['invoice_date_due']<today)}} for i in rows]}}

    elif page in ('customers','contacts'):
        if is_portal: result={{'records':[]}}
        else:
            dom=[('customer_rank','>',0)]
            if filt=='supplier': dom=[('supplier_rank','>',0)]
            if search: dom+=['|',('name','ilike',search),('email','ilike',search)]
            rows=env['res.partner'].search_read(dom,['id','name','email','phone','city','country_id'],order='name asc',limit=80)
            result={{'records':[{{'id':r['id'],'name':r.get('name',''),'email':r.get('email','') or '',
                'phone':r.get('phone','') or '','city':r.get('city','') or '',
                'country':(r.get('country_id') or [0,''])[1]}} for r in rows]}}

    elif page=='products':
        dom=[('active','=',True)]
        if search: dom+=['|',('name','ilike',search),('categ_id.name','ilike',search)]
        rows=env['product.template'].search_read(dom,['id','name','categ_id','list_price','standard_price','type','sale_ok','purchase_ok'],order='name asc',limit=80)
        result={{'records':[{{'id':p['id'],'name':p.get('name',''),'categ':(p.get('categ_id') or [0,''])[1],
            'price':round(p.get('list_price') or 0,2),'cost':round(p.get('standard_price') or 0,2),
            'type':p.get('type','product'),'sale_ok':p.get('sale_ok',True),'purchase_ok':p.get('purchase_ok',True)}} for p in rows]}}

    elif page=='employees':
        if is_portal: result={{'records':[]}}
        else:
            dom=[('active','=',True)]
            if search: dom+=['|',('name','ilike',search),('department_id.name','ilike',search)]
            rows=env['hr.employee'].search_read(dom,['id','name','job_title','department_id','work_email','work_phone'],order='name asc',limit=80)
            result={{'records':[{{'id':e['id'],'name':e.get('name',''),'job':e.get('job_title',''),
                'dept':(e.get('department_id') or [0,''])[1],'email':e.get('work_email','') or '',
                'phone':e.get('work_phone','') or ''}} for e in rows]}}

    elif page=='payments':
        dom=[('partner_id','=',pid)] if is_portal else []
        if search: dom+=[('name','ilike',search)]
        try:
            rows=env['account.payment'].search_read(dom,['id','name','partner_id','amount','date','payment_type','journal_id','state'],order='date desc',limit=100)
            result={{'records':[{{'id':p['id'],'name':p.get('name',''),'partner':(p.get('partner_id') or [0,''])[1],
                'amount':round(p.get('amount') or 0,2),'date':str(p.get('date',''))[:10],
                'type':p.get('payment_type',''),'journal':(p.get('journal_id') or [0,''])[1],
                'state':p.get('state','')}} for p in rows]}}
        except Exception as e: result={{'records':[],'error':str(e)}}

    elif page=='analytics':
        so_dom=[('partner_id','=',pid),('state','in',['sale','done'])] if is_portal else [('state','in',['sale','done'])]
        try:
            mr=env['sale.order']._read_group(domain=so_dom,groupby=['date_order:month'],aggregates=['amount_total:sum'],order='date_order:month asc',limit=12)
            monthly=[{{'label':r[0].strftime('%b %Y') if r[0] else '?','value':round(r[1] or 0,2)}} for r in mr]
        except: monthly=[]
        try:
            sr=env['sale.order']._read_group(domain=[] if not is_portal else [('partner_id','=',pid)],groupby=['state'],aggregates=['id:count'])
            by_state=[{{'state':r[0] or 'unknown','count':r[1] or 0}} for r in sr]
        except: by_state=[]
        top_products=[]
        try:
            pr=env['sale.order.line']._read_group(
                domain=[('order_id.state','in',['sale','done'])]+([('order_id.partner_id','=',pid)] if is_portal else []),
                groupby=['product_id'],aggregates=['price_subtotal:sum'],order='price_subtotal:sum desc',limit=10)
            top_products=[{{'name':r[0].name if r[0] else 'Unknown','value':round(r[1] or 0,2)}} for r in pr]
        except: pass
        result={{'monthly_revenue':monthly,'by_state':by_state,'top_products':top_products}}

    else:
        result={{'error':f'Unknown page: {{page}}'}}

except Exception as e:
    import traceback as _tb
    result={{'error':str(e),'traceback':_tb.format_exc()}}
```

══════════════════════════════════════════════════════════════════════════════════
FINAL CALL — invoke odoo_manage_webapp like this:
══════════════════════════════════════════════════════════════════════════════════

odoo_manage_webapp(
    action      = 'create',
    name        = 'Business Portal',
    description = 'Full multi-page business management portal with live Odoo data',
    data_code   = '<the full Python data_code from the template above>',
    jsx_code    = '<the complete App() JSX, fully implemented for all 9 pages>',
    
    # ⚠ REQUIRED: You must include at least ONE page here (e.g., your Dashboard).
    pages       = [
        {"name": "Dashboard", "route_path": "/", "page_title": "Dashboard"},
        {"name": "Orders",    "route_path": "/orders", "page_title": "Orders"},
        {"name": "Customers", "route_path": "/customers", "page_title": "Customers"}
    ],
    
    # ⚠ REQUIRED: You must define at least ONE discrete API endpoint with handler_code.
    endpoints   = [
        {
            "name": "List Orders", 
            "method": "GET", 
            "path": "/api/orders", 
            "description": "Returns all orders",
            "handler_code": "result = {'orders': env['sale.order'].search_read([], ['name', 'amount_total'])}"
        },
        {
            "name": "Update Order", 
            "method": "POST", 
            "path": "/api/orders/update", 
            "description": "Updates an order status",
            "handler_code": "order = env['sale.order'].browse(params['id'])\norder.write({'state': params['state']})\nresult = {'success': True}"
        }
    ]
)

After creating, output the URL from the tool response so the user can open the portal.
""" + _SYSTEM_PROMPT


MCP_PROMPTS = [
    {
        "name":        "system",
        "description": "Operating instructions — always use Odoo MCP tools, never write code manually",
        "_text":       _SYSTEM_PROMPT,
    },
    {
        "name":        "create_email_template",
        "description": "Create a professional email template — apartment, school, restaurant, promo, newsletter, welcome, invitation, or any custom design",
        "arguments":   [{"name": "description", "description": "What the email template is for (e.g. 'apartment advertisement', 'school admission campaign')", "required": True}],
        "_text":       _PROMPT_CREATE_EMAIL_TEMPLATE,
    },
    {
        "name":        "create_echart",
        "description": "Create an ECharts dashboard with live Odoo data — supports bar, line, pie, scatter, radar, funnel, gauge, treemap, sunburst, sankey, heatmap",
        "arguments":   [{"name": "description", "description": "What to visualise (e.g. 'monthly sales by product category')", "required": True}],
        "_text":       _PROMPT_CREATE_ECHART,
    },
    {
        "name":        "create_webapp",
        "description": "Create a React 18 web application with live Odoo data, Tailwind CSS, Chart.js 4 and in-browser JSX. Also use for business portals, ERP apps, customer portals, ManageSphere-style apps.",
        "arguments":   [{"name": "description", "description": "App purpose and features (e.g. 'business management portal', 'customer portal', 'employee directory')", "required": True}],
        "_text":       _PROMPT_CREATE_WEBAPP,
    },
    {
        "name":        "portal",
        "description": (
            "INSTANT TRIGGER: user typed 'portal' — build COMPLETE multi-page business web app "
            "immediately. Includes Dashboard, Sales Orders, Customers, Products, Invoices, "
            "Purchases, Analytics, Payments, Employees. Live Odoo data, full CRUD, "
            "portal-user isolation, Chart.js analytics. Dark theme React app."
        ),
        "arguments":   [{"name": "description", "description": "Portal type and scope (e.g. 'sales portal', 'customer portal')", "required": False}],
        "_text":       _PROMPT_PORTAL_APP,
    },
    {
        "name":        "create_business_portal",
        "description": (
            "Build a full multi-module business management portal (ManageSphere / ERP style). "
            "Triggers on: 'portal', 'business portal', 'management app', 'ERP app', 'customer portal', "
            "'vendor portal', 'ManageSphere', 'business suite', 'my orders portal'. "
            "Generates 9-page live Odoo-connected dark-theme React app with sidebar navigation, "
            "Chart.js analytics, full CRUD on all modules, and portal-user data isolation."
        ),
        "arguments":   [{"name": "description", "description": "Portal scope and modules needed", "required": True}],
        "_text":       _PROMPT_PORTAL_APP,
    },
    {
        "name":        "create_module",
        "description": "Create a complete Odoo 19 data module with models, views, security and install it",
        "arguments":   [{"name": "description", "description": "Module purpose (e.g. 'library management with books and members')", "required": True}],
        "_text":       _PROMPT_CREATE_MODULE,
    },
    {
        "name":        "query_data",
        "description": "Query and analyse data from any Odoo model with search, aggregation, and ORM",
        "arguments":   [{"name": "description", "description": "What data to query (e.g. 'top 10 customers by revenue')", "required": True}],
        "_text":       _PROMPT_QUERY_DATA,
    },
    {
        "name":        "add_field",
        "description": "Add a custom field to any Odoo model and inject it into the form view",
        "arguments":   [{"name": "description", "description": "Field details (e.g. 'add priority field to sale.order')", "required": True}],
        "_text":       _PROMPT_ADD_FIELD,
    },
    {
        "name":        "bulk_crud",
        "description": "Rules for bulk create, bulk write and bulk delete in a single tool call",
        "arguments":   [{"name": "description", "description": "What records to create/update/delete", "required": True}],
        "_text":       _PROMPT_BULK_CRUD,
    },
    {
        "name":        "import_data",
        "description": "Import contacts, leads, products, employees, or any model records from CSV, Excel, spreadsheets, uploads, TSV, or JSON files",
        "arguments":   [{"name": "description", "description": "What file is being imported and into which model", "required": True}],
        "_text":       _PROMPT_IMPORT_DATA,
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# MCP_RESOURCES
# ═══════════════════════════════════════════════════════════════════════════

MCP_RESOURCES = [
    {
        "uri":         "odoo://docs/echart-patterns",
        "name":        "EChart Patterns",
        "description": "Complete echart_option + data_code patterns for all chart types: bar, line, pie, scatter, radar, funnel, gauge, treemap, sunburst, sankey, heatmap",
        "mimeType":    "text/plain",
    },
    {
        "uri":         "odoo://docs/odoo19-orm",
        "name":        "Odoo 19 ORM Reference",
        "description": "Quick reference for Odoo 19 ORM: _read_group, search_read, search_count, create, write, unlink",
        "mimeType":    "text/plain",
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Resource content
# ═══════════════════════════════════════════════════════════════════════════

def _resource_content(uri):
    if uri == "odoo://docs/echart-patterns":
        return """ECHART PATTERNS — ALL CHART TYPES
==================================

HORIZONTAL BAR (top N by value):
  echart_option: {"xAxis":{"type":"value"},"yAxis":{"type":"category","data":[]},"series":[{"type":"bar","data":[]}]}
  result: {'yAxis':{'data':[names_reversed]},'series':[{'data':[values_reversed]}]}

VERTICAL BAR (monthly trends):
  echart_option: {"xAxis":{"type":"category","data":[]},"yAxis":{"type":"value"},"series":[{"type":"bar","data":[]}]}
  result: {'xAxis':{'data':['Jan','Feb']},'series':[{'data':[100,200]}]}

LINE CHART (time series):
  echart_option: {"xAxis":{"type":"category","data":[]},"yAxis":{"type":"value"},"series":[{"type":"line","smooth":true,"data":[]}]}
  result: {'xAxis':{'data':['Jan','Feb']},'series':[{'data':[100,200]}]}

PIE / DONUT:
  echart_option: {"series":[{"type":"pie","radius":["40%","70%"],"data":[]}]}
  result: {'series':[{'data':[{'name':'X','value':100},{'name':'Y','value':200}]}]}

SCATTER PLOT:
  echart_option: {"xAxis":{"type":"value"},"yAxis":{"type":"value"},"series":[{"type":"scatter","data":[]}]}
  result: {'series':[{'data':[[x1,y1],[x2,y2],...]}]}

RADAR:
  echart_option: {"radar":{"indicator":[]},"series":[{"type":"radar","data":[]}]}
  result: {'radar':{'indicator':[{'name':'A','max':500}]},'series':[{'data':[{'value':[430,340],'name':'Team A'}]}]}

FUNNEL:
  echart_option: {"series":[{"type":"funnel","sort":"descending","data":[]}]}
  result: {'series':[{'data':[{'name':'Visit','value':1000},{'name':'Lead','value':600}]}]}

GAUGE (single KPI):
  echart_option: {"series":[{"type":"gauge","data":[{"value":0}]}]}
  result: {'series':[{'data':[{'value':72.5,'name':'KPI'}]}]}

TREEMAP:
  echart_option: {"series":[{"type":"treemap","data":[]}]}
  result: {'series':[{'data':[{'name':'A','value':100,'children':[{'name':'A1','value':60}]}]}]}

SUNBURST:
  echart_option: {"series":[{"type":"sunburst","data":[],"radius":["15%","90%"]}]}
  result: {'series':[{'data':[{'name':'Cat','value':100,'children':[{'name':'Sub','value':40}]}]}]}

SANKEY:
  echart_option: {"series":[{"type":"sankey","data":[],"links":[]}]}
  result: {'series':[{'data':[{'name':'A'},{'name':'B'}],'links':[{'source':'A','target':'B','value':5}]}]}

HEATMAP:
  echart_option: {"xAxis":{"type":"category","data":[]},"yAxis":{"type":"category","data":[]},
    "visualMap":{"min":0,"max":100},"series":[{"type":"heatmap","data":[]}]}
  result: {'xAxis':{'data':['Mon','Tue']},'yAxis':{'data':['AM','PM']},'series':[{'data':[[0,0,10],[0,1,20]]}]}

MULTI-SERIES (multiple lines/bars):
  Just add multiple entries in the series array with different names.
  result: {'series':[{'data':[1,2,3]},{'data':[4,5,6]}]}

DARK THEME STYLING:
  backgroundColor: "#0f172a"
  text color: "#f1f5f9"
  axis labels: "#94a3b8"
  grid lines: "#1e293b"
"""

    if uri == "odoo://docs/odoo19-orm":
        return """ODOO 19 ORM QUICK REFERENCE
============================

SEARCH + READ:
  records = env['sale.order'].search_read(
      domain=[('state','in',['sale','done'])],
      fields=['name','amount_total','partner_id','date_order'],
      limit=50, order='amount_total desc')

AGGREGATION (Odoo 19 _read_group):
  rows = env['sale.order']._read_group(
      domain=[('state','in',['sale','done'])],
      groupby=['partner_id'],
      aggregates=['amount_total:sum', 'id:count'],
  )
  # rows = [(partner_recordset, total_sum, id_count), ...]
  for partner, total, count in rows:
      print(partner.display_name, total, count)

  # With date grouping:
  rows = env['sale.order']._read_group(
      domain=[('state','in',['sale','done'])],
      groupby=['date_order:month'],
      aggregates=['amount_total:sum'],
  )
  for month_date, total in rows:
      label = month_date.strftime('%b %Y')

COUNT:
  count = env['sale.order'].search_count([('state','=','sale')])

CREATE:
  new_rec = env['res.partner'].create({'name': 'Test', 'email': 'test@example.com'})

WRITE:
  env['res.partner'].browse(42).write({'email': 'new@example.com'})

DELETE:
  env['res.partner'].browse(42).unlink()

IMPORTANT — Odoo 19 changes:
  - read_group() is DEPRECATED → use _read_group()
  - _read_group() returns TUPLES not dicts
  - Many2one in _read_group → recordset (use .display_name)
  - Date in _read_group → date object (use .strftime())
"""

    return ""
