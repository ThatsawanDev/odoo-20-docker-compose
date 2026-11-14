# -*- coding: utf-8 -*-
# mcp_tools_meta.py — TOOLS list (all 25 inputSchema definitions)
# Moved verbatim from mcp_controller.py. Zero logic changed.

TOOLS = [
    # ═══════════════════════════════════════════════════════════════════════════
    # 📧 EMAIL TEMPLATE — single tool for all email template operations
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "odoo_email_template",
        "description": (
            "Create and send email templates in Odoo. "
            "YOU (the LLM) write the full HTML body and pass it as body_html.\n\n"

            "ACTIONS:\n"
            "  create         — save a new template (you generate the HTML)\n"
            "  list           — list all templates (optional: filter by model)\n"
            "  get            — get one template by id or name\n"
            "  update         — edit subject, body_html, email_from, email_to\n"
            "  delete         — remove a template permanently\n"
            "  generate       — create/sync mail.template from mcp.email.template\n"
            "  send           — send for one specific record\n"
            "  send_bulk      — send to many records (by record_ids or domain)\n"
            "  send_test      — send to current user inbox for preview\n"
            "  preview        — render subject+body for a record without sending\n"
            "  create_mailing — create an Email Marketing (mass mailing) campaign from this template\n\n"

            "HOW TO CREATE:\n"
            "  1. Generate complete mobile-responsive HTML with inline CSS yourself\n"
            "  2. Call create with name, subject, body_html\n"
            "  3. ALWAYS set model= to EXACTLY what the user said (e.g. 'mailing.contact', 'res.partner',\n"
            "     'sale.order', etc.). DO NOT default to 'res.partner' unless the user explicitly said 'Contacts'.\n"
            "  4. If unsure of the model name, call action='list_models' with a keyword to search first.\n\n"

            "MODEL SELECTION RULES (CRITICAL):\n"
            "  - User says 'mailing contacts' or 'mailing list' → model='mailing.contact'\n"
            "  - User says 'customers' or 'contacts' → model='res.partner'\n"
            "  - User says 'sales orders' → model='sale.order'\n"
            "  - User says 'invoices' → model='account.move'\n"
            "  - User says 'employees' → model='hr.employee'\n"
            "  - User says 'leads' or 'CRM' → model='crm.lead'\n"
            "  - When unsure: call action='list_models', keyword='<user term>' to discover\n\n"

            "HTML RULES for body_html:\n"
            "  - 600px wide table layout, ALL CSS must be inline style= attributes\n"
            "  - No <style> blocks — email clients strip them\n"
            "  - Colored gradient header, white content area, gray footer\n"
            "  - One clear CTA button\n"
            "  - Dynamic: {{ object.name }} {{ object.email }} {{ object.partner_id.name }}\n"
            "  - Always available: {{ user.name }} {{ user.email_formatted }}\n\n"

            "NEVER use odoo_create or odoo_execute_orm for any email/template/mail model."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {

                "action": {
                    "type": "string",
                    "description": (
                        "REQUIRED. One of: "
                        "create | list | get | update | delete | "
                        "generate | send | send_bulk | send_test | preview | create_mailing | list_models"
                    )
                },

                # ── identify an existing template ────────────────────────────────
                "id": {
                    "type": "integer",
                    "description": "mcp.email.template record ID. Used by get, update, delete, generate, send, send_test, preview."
                },
                "name": {
                    "type": "string",
                    "description": "Template name. Required for create. Also used as fallback identifier for get/update/delete."
                },

                # ── core content fields (match model exactly) ────────────────────
                "subject": {
                    "type": "string",
                    "description": "Email subject. Required for create. Supports {{ object.field }} QWeb expressions."
                },
                "body_html": {
                    "type": "string",
                    "description": (
                        "Full HTML email body. YOU generate this. Required for create. "
                        "Must use 600px table layout with inline CSS only. "
                        "Use {{ object.field }} for dynamic Odoo data. "
                        "No <style> blocks, no external fonts, no JavaScript."
                    )
                },

                # ── model binding (model_id field on mcp.email.template) ─────────
                "model": {
                    "type": "string",
                    "description": (
                        "Odoo model technical name e.g. 'res.partner', 'sale.order', "
                        "'account.move'. Required when body_html uses {{ object.field }}. "
                        "Maps to model_id on the mcp.email.template record. "
                        "Also used by list to filter templates."
                    )
                },

                # ── email header fields ──────────────────────────────────────────
                "email_from": {
                    "type": "string",
                    "description": "Sender address. Default: {{ user.email_formatted }}"
                },
                "email_to": {
                    "type": "string",
                    "description": (
                        "Recipient. Use {{ object.email }} or "
                        "{{ object.partner_id.email }} for model-bound templates. "
                        "Or a static address for campaigns."
                    )
                },

                # ── state field ──────────────────────────────────────────────────
                "state": {
                    "type": "string",
                    "description": "Template state. One of: draft, ready, tested, archived."
                },

                # ── send / preview params ────────────────────────────────────────
                "record_id": {
                    "type": "integer",
                    "description": "ID of the Odoo record to send or preview the template for. Required for send and preview."
                },
                "record_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of Odoo record IDs for send_bulk."
                },
                "domain": {
                    "type": "array",
                    "items": {},
                    "description": (
                        "Odoo domain filter for send_bulk to select records automatically. "
                        "Example: [['state','=','posted']] or [['customer_rank','>',0]]"
                    )
                },
                "recipient": {
                    "type": "string",
                    "description": "Direct email address for send when template has no model set."
                },

                # ── misc ─────────────────────────────────────────────────────────
                "limit": {
                    "type": "integer",
                    "description": "Max records for list (default 100) or send_bulk (default 500)."
                },
                "auto_delete": {
                    "type": "boolean",
                    "description": "Delete mail.mail record after sending. Default: true."
                },
            },
            "required": ["action"]
        }
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # STANDARD ODOO TOOLS - DO NOT USE FOR EMAIL TEMPLATES!
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "odoo_list_models",
        "description": (
            "List all installed Odoo models accessible to the current user. "
            "Returns technical model names and human-readable descriptions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {"type": "string"},
                "limit":  {"type": "integer", "default": 200}
            },
            "required": []
        }
    },
    {
        "name": "odoo_get_model_info",
        "description": "Get detailed metadata about a specific Odoo model.",
        "inputSchema": {
            "type": "object",
            "properties": {"model": {"type": "string"}},
            "required": ["model"]
        }
    },
    {
        "name": "odoo_get_fields",
        "description": "Return field definitions for an Odoo model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model":       {"type": "string"},
                "attributes":  {"type": "array", "items": {"type": "string"}},
                "filter_type": {"type": "string"},
                "filter_name": {"type": "string"}
            },
            "required": ["model"]
        }
    },
    {
        "name": "odoo_search_read",
        "description": "Search Odoo records using a domain filter and return specified fields.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model":  {"type": "string"},
                "domain": {"type": "array", "items": {"type": "array", "items": {}}, "default": []},
                "fields": {"type": "array", "items": {"type": "string"}},
                "limit":  {"type": "integer", "default": 80},
                "offset": {"type": "integer", "default": 0},
                "order":  {"type": "string"}
            },
            "required": ["model"]
        }
    },
    {
        "name": "odoo_get_record",
        "description": "Fetch a single Odoo record by its ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model":     {"type": "string"},
                "record_id": {"type": "integer"},
                "fields":    {"type": "array", "items": {"type": "string"}}
            },
            "required": ["model", "record_id"]
        }
    },
    {
        "name": "odoo_create",
        "description": (
            "⚠️ CREATE RECORDS IN ODOO MODELS ⚠️ "
            "🚫 NEVER USE THIS FOR EMAIL TEMPLATES! "
            "This tool creates one or multiple records in standard Odoo models. "
            "BULK CREATE: pass 'values' as a LIST of dicts to create multiple records in ONE call. "
            "Single create: pass 'values' as a single dict. "
            "❌ DO NOT USE this tool for CSV/XLSX/spreadsheet/upload imports. "
            "✅ USE odoo_import_data for file-based imports. "
            "❌ DO NOT USE for email/template/newsletter/mailing models. "
            "✅ USE odoo_email_template INSTEAD for all email-related content."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": (
                        "⚠️ If this is an email/template/mail/mailing model "
                        "→ STOP! Use 'odoo_email_template' tool instead! "
                        "If the records come from a CSV/XLSX/uploaded file "
                        "→ STOP! Use 'odoo_import_data' instead."
                    )
                },
                "values": {
                    "description": (
                        "Single record: {field: value}. "
                        "Bulk create (multiple records in one call): [{field:value}, {field:value}, ...]"
                    ),
                    "oneOf": [
                        {"type": "object"},
                        {"type": "array", "items": {"type": "object"}, "minItems": 1}
                    ]
                }
            },
            "required": ["model", "values"]
        }
    },
    {
        "name": "odoo_write",
        "description": (
            "Update existing Odoo records. Two modes: "
            "Mode A (uniform): pass 'ids' + 'values' to apply the SAME values to all IDs. "
            "Mode B (per-record bulk): pass 'records' as [{ids:[...], values:{...}}, ...] "
            "to apply DIFFERENT values to different records in ONE call."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string"},
                "ids":   {"type": "array", "items": {"type": "integer"}, "description": "[Mode A] IDs to update with same values."},
                "values": {"type": "object", "description": "[Mode A] Field values applied to all ids."},
                "records": {
                    "type": "array",
                    "description": "[Mode B] Per-record updates with different values each.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ids":    {"type": "array", "items": {"type": "integer"}},
                            "values": {"type": "object"}
                        },
                        "required": ["ids", "values"]
                    }
                }
            },
            "required": ["model"]
        }
    },
    {
        "name": "odoo_unlink",
        "description": "Delete records by ID list.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string"},
                "ids":   {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["model", "ids"]
        }
    },
    {
        "name": "odoo_import_data",
        "description": (
            "Bulk import records into any Odoo model from a CSV, Excel (.xlsx/.xls), JSON, or TSV file. "
            "Use this whenever the user mentions CSV, Excel, spreadsheet, upload, import, "
            "contacts-from-file, leads-from-file, or products-from-file. "
            "Uses Odoo's native import engine (model.load()) which handles Many2one by name, "
            "selection fields by label, external IDs, dates, and more. "
            "Returns a detailed import report with created IDs and per-row errors. "
            "Supports dry_run mode to validate files before committing. "
            "IMPORTANT for ChatGPT/Claude/Gemini file uploads: NEVER pass a sandbox path like "
            "'/mnt/data/file.csv'. Read the uploaded file in the MCP client and pass either "
            "raw file_content, structured records, or headers+rows."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Odoo model technical name (e.g. 'res.partner', 'sale.order')"
                },
                "file_content": {
                    "type": "string",
                    "description": (
                        "File content as raw text (CSV/JSON/TSV) or base64-encoded string (Excel). "
                        "For CSV/JSON, just paste the text. For .xlsx/.xls, provide base64-encoded bytes. "
                        "Data-URI prefix (data:...;base64,) is automatically stripped."
                    )
                },
                "records": {
                    "type": "array",
                    "description": (
                        "Alternative to file_content for uploaded files: a list of row objects already extracted "
                        "from the CSV/XLSX by the MCP client. Example: "
                        "[{\"name\":\"John Doe\",\"email\":\"john@example.com\"}]."
                    ),
                    "items": {"type": "object"}
                },
                "columns": {
                    "type": "array",
                    "description": "Optional explicit column order to use with records mode.",
                    "items": {"type": "string"}
                },
                "headers": {
                    "type": "array",
                    "description": "Column names when using rows mode.",
                    "items": {"type": "string"}
                },
                "rows": {
                    "type": "array",
                    "description": (
                        "Alternative to file_content for uploaded files: list of row arrays matching headers. "
                        "Example: [[\"John Doe\", \"john@example.com\"]]."
                    ),
                    "items": {
                        "type": "array",
                        "items": {}
                    }
                },
                "file_name": {
                    "type": "string",
                    "description": "Original filename (e.g. 'contacts.csv'). Used for auto-detecting format if file_format is not set."
                },
                "file_format": {
                    "type": "string",
                    "enum": ["csv", "tsv", "xlsx", "xls", "json"],
                    "description": "Override format detection. One of: csv, tsv, xlsx, xls, json."
                },
                "is_base64": {
                    "type": "boolean",
                    "description": "Set true if file_content is base64-encoded. Auto-detected for Excel formats."
                },
                "field_mapping": {
                    "type": "object",
                    "description": (
                        "Optional column-to-field rename map. "
                        "e.g. {\"Full Name\": \"name\", \"Email Address\": \"email\"}. "
                        "Use this when CSV column names don't match Odoo field names exactly."
                    )
                },
                "delimiter": {
                    "type": "string",
                    "description": "CSV delimiter override (auto-detected if not set). Examples: ',', ';', '|'"
                },
                "sheet_index": {
                    "type": "integer",
                    "default": 0,
                    "description": "Zero-based Excel sheet index (default: 0 = first sheet)."
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "Parse and validate without creating records. "
                        "Returns column preview and row count. Use this first to verify mappings."
                    )
                },
                "limit": {
                    "type": "integer",
                    "default": 5000,
                    "description": "Max rows to import per call (default 5000, max 50000)."
                },
                "skip_rows": {
                    "type": "integer",
                    "default": 0,
                    "description": "Skip N data rows from the top (useful for files with sub-headers or notes)."
                },
            },
            "required": ["model"],
            "anyOf": [
                {"required": ["file_content"]},
                {"required": ["records"]},
                {"required": ["headers", "rows"]}
            ]
        }
    },
    {
        "name": "odoo_aggregate",
        "description": "Perform GROUP BY aggregations on Odoo data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model":     {"type": "string"},
                "group_by":  {"type": "array", "items": {"type": "string"}},
                "agg_field": {"type": "string"},
                "agg_func":  {"type": "string"},
                "domain":    {"type": "array", "items": {"type": "array", "items": {}}, "default": []},
                "limit":     {"type": "integer", "default": 80},
                "order_by":  {"type": "string"}
            },
            "required": ["model", "group_by"]
        }
    },
    {
        "name": "odoo_call_method",
        "description": "Call any public business method on an Odoo model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model":  {"type": "string"},
                "ids":    {"type": "array", "items": {"type": "integer"}},
                "method": {"type": "string"},
                "args":   {"type": "array", "items": {}, "default": []},
                "kwargs": {"type": "object", "default": {}}
            },
            "required": ["model", "method"]
        }
    },
    {
        "name": "odoo_execute_action",
        "description": "Run a named Server Action (ir.actions.server) by its XML ID or database ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action_ref": {"type": "string"},
                "model":      {"type": "string"},
                "record_ids": {"type": "array", "items": {"type": "integer"}}
            },
            "required": ["action_ref"]
        }
    },
    {
        "name": "odoo_add_custom_field",
        "description": "Create a custom field on any Odoo model and inject it into the form view.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model":            {"type": "string"},
                "field_name":       {"type": "string"},
                "field_label":      {"type": "string"},
                "field_type":       {"type": "string"},
                "position_field":   {"type": "string"},
                "position":         {"type": "string"},
                "required":         {"type": "boolean"},
                "readonly":         {"type": "boolean"},
                "help":             {"type": "string"},
                "selection_values": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                "relation":         {"type": "string"},
                "groups":           {"type": "string"}
            },
            "required": ["model", "field_name", "field_label", "field_type"]
        }
    },
    {
        "name": "odoo_execute_orm",
        "description": (
            "Execute Python code in a secure safe_eval sandbox with full Odoo ORM access. "
            "Code MUST assign the final answer to a variable named 'result'.\n\n"
            "🚫 CRITICAL RULES:\n"
            "1. NEVER use this tool to create or send Email Templates ('mail.template' or 'mcp.email.template').\n"
            "2. For ALL email/campaign/newsletter tasks, you MUST use 'odoo_email_template' instead.\n"
            "3. NEVER use this tool to open uploaded CSV/XLSX/JSON files or paths like '/mnt/data/...'.\n"
            "4. For file imports, you MUST use 'odoo_import_data' with file_content, records, or headers+rows."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": (
                        "Python code. Must set result = ... at the end. "
                        "DO NOT use for email templates or uploaded file imports."
                    )
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "odoo_manage_echart",
        "description": (
            "Create or manage an Apache ECharts dashboard with LIVE Odoo data.\n"
            "Chart is served at /mcp/echart/<slug>.\n\n"
            "ACTIONS: create | update | get | list | delete\n\n"
            "REQUIRED FIELDS for create:\n"
            "  - name: chart title\n"
            "  - echart_option: valid JSON skeleton with EMPTY arrays for data\n"
            "  - data_code: Python that queries Odoo ORM and sets result = {dict}\n\n"
            "RULES:\n"
            "  1. echart_option arrays (xAxis.data, series[].data) must be empty []\n"
            "  2. data_code must use Odoo 19 _read_group(), NOT read_group()\n"
            "  3. Wrap data_code in try/except, set result = {'__error': str(e)} on failure\n"
            "  4. result keys are DEEP MERGED into echart_option at render time\n"
            "  5. NEVER guess fields - call odoo_get_fields(model='...') first\n"
            "  6. Guard optional models with env.has_model('model.name')\n"
            "  7. Verify live data with odoo_search_read or odoo_aggregate before shipping\n\n"
            "MULTI-CHART DASHBOARDS:\n"
            "  - The renderer uses CSS Grid: each series gets its own panel\n"
            "  - For pie/donut/gauge/radar/sunburst, ALWAYS set explicit center and radius\n"
            "  - Do NOT leave multiple center-based series at default ['50%','50%']\n"
            "  - Use chart_type='custom' or let it auto-detect for mixed types\n\n"
            "ADVANCED:\n"
            "  - pre_init_js runs BEFORE chart.setOption() (use for echarts.registerMap)\n"
            "  - post_init_js runs AFTER data loads (use for click handlers, drill-down)\n"
            "  - data_code can set result['__js_data__'] = {} -> exposed as window.mcpJsData\n"
            "  - mcp_layout in echart_option controls minHeight/minWidth for responsive sizing"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action":        {"type": "string", "description": "create | update | get | list | delete"},
                "name":          {"type": "string"},
                "chart_type":    {"type": "string", "description": "Optional. Auto-detected from echart_option series type if omitted."},
                "slug":          {"type": "string"},
                "echart_option": {"type": "string", "description": "Static JSON skeleton. Arrays must be empty []."},
                "data_code":     {"type": "string", "description": "Python. Must set result = {dict}."},
                "pre_init_js":   {"type": "string"},
                "post_init_js":  {"type": "string"},
                "description":   {"type": "string"},
                "is_public":     {"type": "boolean", "default": True}
            },
            "required": ["action"]
        }
    },
    {
        "name": "odoo_manage_webapp",
        "description": (
            "Create or manage a React 18 web application served at /mcp/app/<slug>.\n\n"
            "RUNTIME GLOBALS (no imports needed):\n"
            "  - React 18, ReactDOM 18, Babel Standalone (in-browser JSX transpile)\n"
            "  - Tailwind CSS Play CDN (full Tailwind, all classes available)\n"
            "  - Chart.js 4.x — use as global 'Chart' for analytics charts\n"
            "  - window.odoo.portal = {uid, name, partner_id, is_portal, is_admin}\n"
            "  - React hooks also injected as globals: useState, useEffect, useRef, etc.\n"
            "  - NO npm, NO imports, NO require() — everything runs in-browser\n\n"
            "MANDATORY RULES for jsx_code:\n"
            "  1. MUST define: function App() { ... } at top level\n"
            "  2. React hooks as globals: useState(), useEffect(), useRef() etc.\n"
            "  3. Use JSX syntax (<div>, <input>) — Babel transpiles it\n"
            "  4. For dynamic keys: key={`${r}-${c}`}\n"
            "  5. NEVER use localStorage — ALL data must come from window.odoo.fetch()\n"
            "  6. Do NOT use import/export — all code runs in one script block\n"
            "  7. For charts: new Chart(canvasRef.current.getContext('2d'), {...})\n"
            "  8. Portal check: window.odoo.portal.is_portal — hide admin sections\n"
            "  9. Dark theme default: bg-gray-950 shell, bg-gray-900 cards, indigo accent\n"
            " 10. Business portals: include sidebar nav, KPI cards, Chart.js, CRUD modals\n\n"
            "data_code Python globals (auto-injected by controller):\n"
            "  env, params, portal_uid, portal_partner_id, portal_name\n"
            "  portal_uid/partner_id are None for anonymous visitors\n"
            "  ALWAYS filter: domain=[('partner_id','=',portal_partner_id)] if portal_partner_id\n"
            "  Must set: result = {dict}\n"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action":      {"type": "string", "description": "create | update | get | list | delete"},
                "name":        {"type": "string"},
                "slug":        {"type": "string"},
                "jsx_code":    {"type": "string", "description": "React JSX code. MUST define function App(). Uses React 18 globals."},
                "data_code":   {"type": "string", "description": "Optional Python code for server-side data. Must set result = {dict}."},
                "description": {"type": "string"},
                "is_public":   {"type": "boolean", "default": False},
                "pages": {
                    "type": "array",
                    "description": (
                        "REQUIRED list of pages/routes for the app. Each item: "
                        "{name, route_path, page_title, jsx_code, sequence}. "
                        "For create: MUST include at least one page."
                    ),
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "name":       {"type": "string", "description": "Page name, e.g. 'Dashboard'"},
                            "route_path": {"type": "string", "description": "Route path, e.g. '/orders' or '/orders/:id'"},
                            "page_title": {"type": "string", "description": "HTML page title for this route"},
                            "jsx_code":   {"type": "string", "description": "Optional per-page React JSX component"},
                            "sequence":   {"type": "integer", "description": "Sort order (default: auto 10, 20, ...)"}
                        },
                        "required": ["name"]
                    }
                },
                "endpoints": {
                    "type": "array",
                    "description": (
                        "REQUIRED list of API endpoints exposed by this app. Each item: "
                        "{name, method, path, description, handler_code, sequence}. "
                        "For create: MUST include at least one endpoint."
                    ),
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "name":         {"type": "string", "description": "Endpoint label, e.g. 'Get Orders'"},
                            "method":       {"type": "string", "enum": ["GET","POST","PUT","DELETE"], "description": "HTTP method"},
                            "path":         {"type": "string", "description": "URL path, e.g. '/api/orders'"},
                            "description":  {"type": "string", "description": "What this endpoint does"},
                            "handler_code": {"type": "string", "description": "Python handler. Must set result = {dict}."},
                            "sequence":     {"type": "integer", "description": "Sort order (default: auto 10, 20, ...)"}
                        },
                        "required": ["name"]
                    }
                }
            },
            "required": ["action", "name", "pages", "endpoints"]
        }
    },

    {
        "name": "odoo_manage_module",
        "description": (
            "Create a full custom Odoo 19 module with models, views, security, menus.\n\n"
            "🚨 MANDATORY: ALWAYS use spec={} for action='create'.\n"
            "NEVER provide raw models_code/views_code/security_code — the server generates "
            "all XML, CSV, and manifest automatically from the spec.\n\n"
            "CORRECT FLOW:\n"
            "  1. action='create', technical_name='x_myapp', spec={...}\n"
            "  2. Check response errors array\n"
            "  3. If no errors → action='install', technical_name='x_myapp'\n"
            "  4. If errors → fix spec → action='create' again (auto-deletes broken drafts)\n"
            "  ❌ NEVER loop: create→install(fail)→fix→install(fail)\n\n"
            "NAMING RULES:\n"
            "  - ALL model names MUST start with x_ (e.g. x_patient, x_invoice_line)\n"
            "  - ALL field names MUST start with x_ (e.g. x_name, x_customer_id)\n"
            "  - ❌ REJECTED: patient, name, status, vendor_id\n\n"
            "ACTIONS:\n"
            "  create  — create module from spec (always saved, never auto-installed)\n"
            "  install — validate + generate ZIP + install via base_import_module\n"
            "  update  — update specific code fields\n"
            "  get | list | delete | preview | fix | duplicate | add_feature | export"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": (
                        "create | update | get | list | delete | install | "
                        "preview | duplicate | add_feature | fix | export"
                    ),
                },
                "name": {"type": "string", "description": "Human-readable module name"},
                "technical_name": {
                    "type": "string",
                    "description": "Must start with x_ (e.g. x_library_management)",
                },
                "models_code": {
                    "type": "string",
                    "description": "XML defining models via ir.model + ir.model.fields. NOT needed when using spec.",
                },
                "views_code": {
                    "type": "string",
                    "description": "XML with views, actions, menus. NOT needed when using spec.",
                },
                "security_code": {
                    "type": "string",
                    "description": "ir.model.access.csv content. AUTO-GENERATED — do not provide.",
                },
                "data_files_code": {
                    "type": "string",
                    "description": "JSON dict of extra data files {filename: xml_content}",
                },
                "demo_data_code": {"type": "string", "description": "Demo data XML"},
                "report_code": {
                    "type": "string",
                    "description": "Report QWeb templates + ir.actions.report XML",
                },
                "js_code": {
                    "type": "string",
                    "description": (
                        "JSON dict of JS files for static/src/js/. "
                        "For OWL components: {\"dashboard.js\": \"...OWL code...\"}"
                    ),
                },
                "scss_code": {
                    "type": "string",
                    "description": "JSON dict of SCSS files for static/src/scss/",
                },
                "owl_code": {
                    "type": "string",
                    "description": (
                        "JSON dict of OWL XML template files for static/src/xml/. "
                        "Example: {\"dashboard.xml\": \"<templates>...</templates>\"}"
                    ),
                },
                "manifest_code": {
                    "type": "string",
                    "description": "AUTO-GENERATED — do not provide unless overriding depends.",
                },
                "description": {"type": "string"},
                "skip_install": {
                    "type": "boolean",
                    "description": (
                        "Default: true for create. Module is saved but NOT auto-installed. "
                        "Call action='install' separately after review."
                    ),
                    "default": True,
                },
                "force": {
                    "type": "boolean",
                    "description": (
                        "For install: if true, use init mode to overwrite noupdate records."
                    ),
                },
                "uninstall_first": {
                    "type": "boolean",
                    "description": (
                        "For install: if true, uninstall existing module before "
                        "reinstalling (clean slate for development)."
                    ),
                },
                # add_feature params
                "feature_type": {
                    "type": "string",
                    "description": "For add_feature: model | view | automation | security_row",
                },
                "code": {
                    "type": "string",
                    "description": "For add_feature: XML or CSV code to append",
                },
                # new_technical_name and new_name for duplicate
                "new_technical_name": {
                    "type": "string",
                    "description": "For duplicate: technical name for the copy",
                },
                "new_name": {
                    "type": "string",
                    "description": "For duplicate: human name for the copy",
                },
                # ── SPEC-BASED GENERATION — MANDATORY for create ─────────────
                "spec": {
                    "type": "object",
                    "description": (
                        "🚨 MANDATORY for action='create'. Structured JSON spec — server generates all XML.\n"
                        "Format: {\n"
                        "  name: 'Hospital Management',\n"
                        "  technical_name: 'x_hospital',\n"
                        "  depends: ['base'],\n"
                        "  models: [{\n"
                        "    name: 'x_patient',       ← MUST start with x_\n"
                        "    label: 'Patient',\n"
                        "    views: ['list','form'],   ← NEVER use 'tree'\n"
                        "    fields: [\n"
                        "      {name:'x_name', type:'char', label:'Name', required:true},\n"
                        "      {name:'x_status', type:'selection', label:'Status',\n"
                        "       options:[['draft','Draft'],['done','Done']]},\n"
                        "      {name:'x_doctor_id', type:'many2one', label:'Doctor',\n"
                        "       relation:'x_doctor', required:true},\n"
                        "       ← required many2one auto-gets ondelete='restrict'\n"
                        "      {name:'x_line_ids', type:'one2many', label:'Lines',\n"
                        "       relation:'x_line', inverse_name:'x_patient_id'}\n"
                        "    ]\n"
                        "  }]\n"
                        "}.\n"
                        "Field types: char|text|integer|float|monetary|boolean|date|datetime|"
                        "selection(+options)|many2one(+relation)|many2many(+relation)|"
                        "one2many(+relation,inverse_name)|binary|html.\n"
                        "Security CSV + manifest are AUTO-GENERATED. Never provide them.\n"
                        "❌ ondelete='set null' on required many2one = CRASH. Server auto-uses 'restrict'."
                    ),
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "odoo_read_group",
        "description": (
            "Aggregate records with GROUP BY. Odoo 19: uses formatted_read_group with "
            "groupby, aggregates (field:sum, field:count, etc.), domain, limit, order."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string"},

                "domain": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {}
                    },
                    "default": []
                },

                "groupby": {
                    "type": "array",
                    "items": {"type": "string"}
                },

                "aggregates": {
                    "type": "array",
                    "items": {"type": "string"}
                },

                "orderby": {"type": "string"},

                "limit": {"type": "integer", "default": 80},
                "offset": {"type": "integer", "default": 0}
            },
            "required": ["model", "groupby"]
        }
    },
    {
        "name": "odoo_code_search",
        "description": (
            "Search addon source code with regex. "
            "Uses ripgrep (rg) if available, else GNU grep, else Python fallback. "
            "Returns file path, line number, and matching text."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for in addon source files."},
                "path": {"type": "string", "description": "Optional path filter — only search roots containing this substring."},
                "limit": {"type": "integer", "default": 50, "description": "Max results to return."},
                "file_ext": {
                    "type": "string",
                    "default": "py,xml",
                    "description": "Comma-separated file extensions to search (e.g. 'py,xml,csv,js')."
                },
                "case_insensitive": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, perform case-insensitive search."
                },
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "odoo_code_read",
        "description": "Read source file contents with optional line range.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start": {"type": "integer"},
                "end": {"type": "integer"},
            },
            "required": ["path"]
        }
    },
    {
        "name": "odoo_search_webapp_code",
        "description": "Search within webapp code fields (jsx_code, data_code, endpoints) by regex.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "webapp_id": {"type": "integer"},
                "pattern": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "odoo_search_module_code",
        "description": "Search within MCP module file contents (XML, Python, CSV) by regex.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "module_id": {"type": "integer"},
                "pattern": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "odoo_manage_snippet",
        "description": (
            "Create and install an Odoo 19 website snippet (drag-and-drop building block). "
            "The snippet appears in the Website Builder panel immediately after install.\n\n"
            "IMPORTANT: action='create' installs automatically — do NOT call install separately.\n\n"
            "ACTIONS: create | update | get | list | delete | install | uninstall\n\n"
            "TEMPLATE RULES:\n"
            "  Root: <section class='s_name o_colored_level' data-name='Name' data-snippet='s_name'>\n"
            "  Layout: Bootstrap 5 — container > row > col-*\n"
            "  Editable text: class='oe_editable'\n"
            "  Buttons: class='btn btn-primary'\n"
            "  Icons: <i class='fa fa-star'/>\n"
            "  NO id attributes, NO nested <section>, NO external CDN links\n\n"
            "CSS RULES:\n"
            "  Root selector must be .s_name\n"
            "  Prefix all sub-classes: .s_name_card, .s_name_icon\n"
            "  Use CSS variables: var(--bs-primary), var(--bs-body-color)\n\n"
            # "CATEGORIES: snippet_structure | snippet_content | snippet_feature | snippet_effect"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string",
                           "description": "create | update | get | list | delete | install | uninstall"},
                "name": {"type": "string", "description": "Human name, e.g. 'Hero Banner'"},
                "technical_name": {"type": "string",
                                   "description": "Snake_case, e.g. 'hero_banner' — s_ prefix auto-added"},
                # "category": {"type": "string",
                #              "description": "snippet_structure | snippet_content | snippet_feature | snippet_effect"},
                "template_xml": {"type": "string",
                                 "description": "Full HTML for the snippet. Must start with <section class='s_name ...'>"},
                "scss_code": {"type": "string", "description": "CSS/SCSS. Root selector must be .s_name"},
                "js_code": {"type": "string", "description": "Optional JavaScript"},
                "thumbnail_svg": {"type": "string",
                                  "description": "Optional SVG thumbnail 200x150. Auto-generated if empty."},
                "description": {"type": "string"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "odoo_manage_report",
        "description": (
            "Create and install a QWeb PDF or HTML report for any Odoo model. "
            "Use for ANY request about reports, printing, PDF generation, Print menu. "
            "action='create' installs automatically — do NOT use odoo_manage_module for reports.\n\n"
            "ACTIONS: create | update | get | list | delete | install | uninstall\n\n"
            "🚨 TEMPLATE CONTEXT (CRITICAL — misunderstanding = blank report):\n"
            "  Your template_html runs INSIDE a per-record loop:\n"
            "    <t t-foreach='docs' t-as='doc'><div class='page'>YOUR HTML</div></t>\n"
            "  Variable 'doc' = current record. 'docs' = all records.\n"
            "  ❌ DO NOT add your own t-foreach='docs' loop\n"
            "  ❌ DO NOT use docs.filtered(lambda ...) — it may crash\n"
            "  ❌ DO NOT use hasattr() — use <t t-if=\"'field' in doc\">\n"
            "  ✅ Use doc.field_name directly for the current record's data\n"
            "  ✅ Use t-foreach='doc.order_line' t-as='line' for child records\n\n"
            "🚨 PDF USES WKHTMLTOPDF (old WebKit) — CSS RESTRICTIONS:\n"
            "  ❌ NO display:flex (use Bootstrap grid: div.row > div.col-6)\n"
            "  ❌ NO calc() in CSS (use fixed widths: width:48% not calc(50%-8px))\n"
            "  ❌ NO CSS custom properties (var(--x))\n"
            "  ❌ NO flexbox: flex-wrap, justify-content, align-items in inline styles\n"
            "  ✅ Use <table> for grids and card layouts\n"
            "  ✅ Use Bootstrap classes: row, col-6, col-4, text-center, text-end\n"
            "  ✅ Use float:left + width:48% for side-by-side cards\n"
            "  ✅ Use -webkit-linear-gradient() not linear-gradient()\n\n"
            "⚠️ TABLE & CSS RULES (Odoo 19 standard):\n"
            "  1. ALL <table> MUST use class=\"table table-bordered\"\n"
            "  2. Use <thead> with <th> for header row\n"
            "  3. NEVER put t-field on <td>/<th>/<tr> — use <td><span t-field=\"...\"/></td>\n"
            "  4. For section headers: <div class=\"section-header\">TITLE</div>\n"
            "  5. For KPI cards: <div class=\"kpi-card\"><div class=\"kpi-value\">123</div>"
            "<div class=\"kpi-label\">Label</div></div>\n"
            "  6. For badges: <span class=\"badge\" style=\"background:#28a745;color:#fff\">Active</span>\n"
            "  7. Baseline CSS (borders, Lato font) is ALWAYS auto-injected\n\n"
            "CARD LAYOUT EXAMPLE (wkhtmltopdf-safe):\n"
            "  <div style=\"float:left;width:48%;margin:0 1% 12px;border:1px solid #ccc;"
            "border-radius:8px;overflow:hidden;page-break-inside:avoid;\">\n"
            "    <div style=\"background:#4f46e5;padding:12px;color:#fff;\">Header</div>\n"
            "    <div style=\"padding:12px;\">Content</div>\n"
            "  </div>\n\n"
            "LAYOUTS: external (company header+footer, default) | internal | minimal.\n"
            "PAPER: A4 (default) | A3 | A5 | Letter | Legal"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "create | update | get | list | delete | install | uninstall"
                },
                "name": {
                    "type": "string",
                    "description": "Report display name, e.g. 'Sale Order Summary'"
                },
                "technical_name": {
                    "type": "string",
                    "description": "Snake_case, e.g. 'sale_order_summary'. Used as report key."
                },
                "model_name": {
                    "type": "string",
                    "description": "Odoo model, e.g. 'sale.order', 'account.move', 'stock.picking'"
                },
                "report_type": {
                    "type": "string",
                    "description": "qweb-pdf (default) | qweb-html"
                },
                "binding_model": {
                    "type": "string",
                    "description": "Model whose Print menu shows this report. Defaults to model_name."
                },
                "landscape": {
                    "type": "boolean",
                    "description": "True for landscape orientation"
                },
                "template_html": {
                    "type": "string",
                    "description": (
                        "QWeb HTML content inside <div class='page'>. "
                        "MUST use class='table table-bordered' on every <table>. "
                        "Use <thead>+<th> for headers, <tbody>+<td> for data. "
                        "Use t-esc on <td>, or <td><span t-field='...'/></td>."
                    )
                },
                "custom_css": {
                    "type": "string",
                    "description": (
                        "Custom CSS injected AFTER baseline CSS. "
                        "Baseline already provides: table borders (1px solid black), "
                        "Lato font, header backgrounds, KPI cards, badges. "
                        "Only provide custom_css to override or add extra styles."
                    )
                },
                "layout": {
                    "type": "string",
                    "description": "external (company header+footer) | internal (minimal header) | minimal (blank page). Default: external"
                },
                "paper_format": {
                    "type": "string",
                    "description": "A4 | A3 | A5 | Letter | Legal | custom. Default: A4"
                },
                "paper_width": {
                    "type": "number",
                    "description": "Page width in mm. Required when paper_format='custom'."
                },
                "paper_height": {
                    "type": "number",
                    "description": "Page height in mm. Required when paper_format='custom'."
                },
                "description": {"type": "string"},
            },
            "required": ["action"]
        }
    }
]
