# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Advanced Odoo MCP Studio - AI Builder for React Apps, Odoo Modules, Reports, Emails & Charts',
    'version': '20.0.1.0.0',
    'category': 'Technical',
    'sequence': '-101',
    'price': '172.00',
    'currency': 'eur',
    'author': 'echoBitz IT Solutions Pvt. Ltd.',
    'maintainer': 'echoBitz IT Solutions Pvt. Ltd.',
    'summary':
        'MCP Server for Odoo 18 | 19 | AI Assistant Integration | ChatGPT, Claude & Gemini Copilot | '
        'LLM Automation | Build Web Apps, React Portals, ECharts Dashboards, Custom Modules, Agent, Voice, Voice agent'
        'QWeb Reports & Website Snippets | CRUD Automation | ORM Code Execution | AI | Dashboard | Claude | CRUD'
        'Custom Field Builder | OAuth2 REST API | AI Agent | No-Code Studio Alternative | Vibe | LLM | Client | Server'
        'Data Analytics | Email Template Builder | Audit Logs | Security & Access Control | Rules | Security | Rights'
        'Odoo Connector | External API | GPT-4 Integration | Anthropic | OpenAI | MCP | mcp | sub agent | Advance'
        'Shopify Connector | WooCommerce | Amazon | eBay | Magento | E-Commerce Integration | Quickbook | Account'
        'Payment Gateway | Stripe | PayPal | Razorpay | Invoice Automation |  Email | Marketing | Report | Inventory | Sales'
        'Accounting Automation | Stock Management | Inventory | Purchase Order | 3cx | Pipedrive | Brevo | Mailchimp '
        'Sales Automation | CRM | Lead Management | Marketing Automation | List View | Management | Print | Pdf'
        'WhatsApp Integration | SMS | Bulk Email | Mass Mailing | Newsletter | Theme | Access | Studio | Ninja |'
        'HR Payroll | Attendance | Leave Management | Employee Portal | Portal | Label Printer | Activity | Email'
        'Project Management | Task Automation | Timesheet | Helpdesk | Ticketing | Whatsapp | Messager | Google | facebook '
        'POS | Point of Sale | Barcode | QR Code | Label Printing | Instagram | Twitter | Login | SSO | Integration'
        'Multi-Company | Multi-Currency | Multi-Warehouse | Logistics | Delivery | API | Rest API | Graphql | Webhook'
        'Website Builder | Landing Page | Blog | SEO | Google Analytics | Odoo MCP Server | odoo mcp | AI Dashboard | Odoo Build Studio'
        'Import Export | Excel | CSV | PDF | Document Management | Agentic | chat bot | bot | Assistant | copilot | Odoo AI Studio'
        'Odoo | Odoo 17 | Odoo 18 | Odoo 19 | Community | Enterprise | SaaS | On-Premise | odoo copilot | AI Analyst | InsightMate'
    ,
    'description': """
        Full-featured Remote MCP Server for Odoo 19.
        Connects Claude, ChatGPT, Gemini and other AI agents.

        Features:
        - 25 MCP tools: CRUD, read_group, code search, AI agent query, email templates
        - AI Web App (React) builder — create/manage/run React apps inside Odoo
        - AI Module builder — generate custom Odoo modules as ZIP
        - EChart dashboard builder — create Apache ECharts dashboards
        - Email Template builder — modern, responsive email templates with marketing integration
        - No-Auth + Bearer token authentication
        - Prompt templates, tool allowlists, model/field restrictions
        - Comprehensive audit logging with timing metrics
    """,
    'live_test_url': 'https://calendly.com/echobitzit-info/45min?back=1',
    'website': 'https://www.echobitzit.com',
    'license': 'OPL-1',
    'depends': ['base', 'web', 'mail', 'mass_mailing', 'website'],
    'data': [
        'security/mcp_security.xml',
        'security/ir.access.csv',
        'views/mcp_config_views.xml',
        'views/mcp_prompt_template_views.xml',
        'views/mcp_tool_allowlist_views.xml',
        'views/mcp_model_group_views.xml',
        'views/mcp_api_key_views.xml',
        'views/mcp_webapp_views.xml',
        'views/mcp_echart_views.xml',
        'views/mcp_module_views.xml',
        'views/mcp_email_template_views.xml',
        'views/mcp_log_views.xml',
        'views/mcp_token_views.xml',
        'views/mcp_website_snippet_views.xml',
        'views/mcp_report_views.xml',
        'views/menu.xml',
        'data/mcp_config_data.xml',
        'data/mcp_log_cron.xml',
        'data/mcp_prompt_templates_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/banner.gif'],
}

