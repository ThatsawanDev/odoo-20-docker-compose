# -*- coding: utf-8 -*-
"""
mcp.report — Odoo Report Builder
=================================

LAYOUTS (verified from official Odoo 19 source & docs):

  web.external_layout       — Company header + footer + company address
                              Most common. Used for customer-facing docs.
                              (sale orders, invoices, delivery slips)

  web.internal_layout       — Minimal header with company name only
                              For internal documents.
                              (internal transfers, warehouse docs)

  web.minimal_layout        — No header, no footer. Blank page.
                              For labels, cards, certificates, badges.

  web.html_container        — Required wrapper for ALL report types.
                              Always outermost, wraps the layout call.

LAYOUT SELECTION GUIDE:
  Customer invoice / quote → external_layout
  Internal warehouse doc   → internal_layout
  ID card / badge / label  → minimal_layout
  Certificate / diploma    → minimal_layout (full custom CSS)

QWEB RULES (from official Odoo docs, never change across versions):
  t-field → ONLY on <span> <div> <p> <h1-h6> <li> <strong>
             NEVER on <td> <tr> <th> → AssertionError
  t-esc   → safe on any element
  res_company → correct variable name (NOT company / o_company)
"""
import logging
import re
import uuid
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

# ── Baseline CSS injected into EVERY report ──────────────────────────────────
# Ensures tables have visible borders, proper font, and consistent spacing
# regardless of what the AI client provides. Custom CSS overrides these.
_BASE_REPORT_CSS = """
/* ── MCP Report baseline (always injected) ─────────────────────── */
.page { font-family: 'Lato', Arial, Helvetica, sans-serif; font-size: 13px; color: #212529; }
.page table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
.page table, .page table th, .page table td {
    border: 1px solid #000 !important;
}
.page table th, .page table td {
    padding: 6px 10px;
    vertical-align: middle;
    text-align: left;
}
.page table th {
    background-color: #f0f0f0;
    font-weight: 700;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}
.page table td { font-size: 13px; }
.page table tr:nth-child(even) td { background-color: #fafafa; }
.page h2, .page h3, .page h4 { margin-top: 18px; margin-bottom: 8px; }
.page .section-header {
    background-color: #e8f0fe; padding: 8px 12px;
    border: 1px solid #c4d8f0; border-radius: 4px;
    margin-bottom: 12px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.5px;
    color: #1a4b8c; font-size: 13px;
}
.page .kpi-card {
    border: 1px solid #dee2e6; border-radius: 6px;
    padding: 12px 16px; text-align: center;
    margin-bottom: 10px; page-break-inside: avoid;
}
.page .kpi-card .kpi-value { font-size: 22px; font-weight: 700; }
.page .kpi-card .kpi-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #6c757d; }
.page .badge {
    display: inline-block; padding: 3px 10px;
    border-radius: 12px; font-size: 11px;
    font-weight: 600; text-transform: uppercase;
}
/* ── wkhtmltopdf-safe card grid (float-based) ── */
.page .card-grid { overflow: hidden; }
.page .card-grid::after { content: ''; display: table; clear: both; }
.page .card-item {
    float: left; width: 48%; margin: 0 1% 12px;
    border: 1px solid #dee2e6; border-radius: 8px;
    overflow: hidden; page-break-inside: avoid;
    background: #fff;
}
.page .card-item .card-header {
    padding: 12px 14px; color: #fff;
    background: #4f46e5; font-weight: 700;
}
.page .card-item .card-body { padding: 10px 14px; }
.page .clearfix::after { content: ''; display: table; clear: both; }
"""

_REPORT_FIELD_ALIASES = {
    'hr.employee': {
        'address_home_id': 'work_contact_id',
    },
    'product.template': {
        'detailed_type': 'type',
    },
    'product.product': {
        'detailed_type': 'type',
    },
}


class McpReport(models.Model):
    _name        = 'mcp.report'
    _description = 'MCP AI Report'
    _order       = 'write_date desc'
    _inherit     = ['mail.thread']

    # ── Identity ──────────────────────────────────────────────────────────────
    name           = fields.Char(string='Report Name', required=True, tracking=True)
    technical_name = fields.Char(string='Technical Name', required=True, index=True)
    description    = fields.Text(string='Description')

    # ── Target model ──────────────────────────────────────────────────────────
    model_name    = fields.Char(string='Model', required=True,
                                 help='Technical model name e.g. sale.order, res.partner')
    report_type   = fields.Selection([
        ('qweb-pdf',  'PDF'),
        ('qweb-html', 'HTML (preview in browser)'),
    ], default='qweb-pdf', required=True)
    binding_model = fields.Char(string='Add to Print Menu',
                                 help='Leave blank = same as Model')
    landscape     = fields.Boolean(default=False)

    # ── Layout ────────────────────────────────────────────────────────────────
    layout = fields.Selection([
        ('external', 'External — company header + footer (invoices, quotes)'),
        ('internal', 'Internal — minimal header, no footer (warehouse, internal)'),
        ('minimal',  'Minimal — no header, no footer (badges, cards, labels)'),
    ], string='Layout', default='external', required=True,
       help='external: company logo + address header + footer\n'
            'internal: small header with company name only\n'
            'minimal:  blank page — full control via CSS')

    # ── Template ──────────────────────────────────────────────────────────────
    template_html = fields.Text(
        string='Report Content (QWeb HTML)',
        help='Content inside <div class="page">.\n'
             'RULE: t-field only on <span>/<div>/<p> — NEVER on <td>.\n'
             'Use t-esc on <td>, or wrap: <td><span t-field="..."/></td>\n'
             'Variables: doc, docs, res_company, user')
    custom_css    = fields.Text(
        string='Custom CSS',
        help='CSS injected into the report. Use for badges, cards, labels.\n'
             'Example: body { font-family: Arial; } .badge { border: 2px solid #333; }')

    # ── Paper format ──────────────────────────────────────────────────────────
    paper_format = fields.Selection([
        ('A4',     'A4 (210×297mm)'),
        ('A3',     'A3 (297×420mm)'),
        ('A5',     'A5 (148×210mm)'),
        ('Letter', 'US Letter (216×279mm)'),
        ('Legal',  'US Legal (216×356mm)'),
        ('custom', 'Custom (set width/height below)'),
    ], string='Paper Format', default='A4')
    paper_width  = fields.Float(string='Width (mm)',  default=210)
    paper_height = fields.Float(string='Height (mm)', default=297)

    # ── State ─────────────────────────────────────────────────────────────────
    state       = fields.Selection([
        ('draft',     'Draft'),
        ('installed', 'Installed'),
        ('error',     'Error'),
    ], default='draft', tracking=True)
    install_log = fields.Text(readonly=True)
    active      = fields.Boolean(default=True)
    user_id     = fields.Many2one('res.users', default=lambda self: self.env.user)

    # ── Links to created DB records ───────────────────────────────────────────
    view_id   = fields.Many2one('ir.ui.view',        string='Template View',
                                 ondelete='set null')
    action_id = fields.Many2one('ir.actions.report', string='Report Action',
                                 ondelete='set null')
    report_key = fields.Char(compute='_compute_report_key', store=True)
    report_url = fields.Char(compute='_compute_report_url')

    @api.depends('technical_name')
    def _compute_report_key(self):
        for r in self:
            n = (r.technical_name or '').lower().replace(' ', '_').replace('-', '_')
            r.report_key = 'mcp_report.' + n if n else ''

    @api.depends('action_id', 'model_name')
    def _compute_report_url(self):
        base = self.env['ir.config_parameter'].sudo().get_str('web.base.url', '')
        for r in self:
            if not r.action_id:
                r.report_url = ''
                continue
            sample_id = ''
            model = (r.model_name or '').strip()
            if model:
                try:
                    rec = self.env[model].sudo().search([], limit=1)
                    if rec:
                        sample_id = '/' + str(rec.id)
                except Exception:
                    sample_id = ''
            r.report_url = base + '/report/html/' + r.action_id.report_name + sample_id

    @staticmethod
    def _build_report_arch(report_name, layout_call, page_content, css_block, is_multi):
        if is_multi:
            return (
                '<t t-name="' + report_name + '">'
                '<t t-call="web.html_container">'
                '<t t-call="' + layout_call + '">'
                '<div class="page">'
                + css_block
                + page_content +
                '</div>'
                '</t>'
                '</t>'
                '</t>'
            )
        return (
            '<t t-name="' + report_name + '">'
            '<t t-call="web.html_container">'
            '<t t-foreach="docs" t-as="doc">'
            '<t t-call="' + layout_call + '">'
            '<div class="page">'
            + css_block
            + page_content +
            '</div>'
            '</t>'
            '</t>'
            '</t>'
            '</t>'
        )

    def _validate_report_render(self, report_action, report_name, model_name):
        docs = self.env[model_name].sudo().search([], limit=1)
        sample_label = 'sample record #%s' % docs.id if docs else 'empty draft record'
        if not docs:
            docs = self.env[model_name].sudo().new({})
        values = {
            'doc_ids': docs.ids,
            'doc_model': model_name,
            'docs': docs,
        }
        report_action.with_context(discard_logo_check=True)._render_template(
            report_name, values
        )
        return sample_label

    # =========================================================================
    # action_install
    # =========================================================================
    def action_install(self):
        self.ensure_one()

        # Read ALL values before try block
        name         = self.name or ''
        tech         = (self.technical_name or '').lower().replace(' ', '_').replace('-', '_')
        model        = (self.model_name or '').strip()
        rtype        = self.report_type or 'qweb-pdf'
        layout       = self.layout or 'external'
        tmpl_html    = (self.template_html or '').strip()
        custom_css   = (self.custom_css or '').strip()
        binding      = (self.binding_model or '').strip() or model
        landscape    = self.landscape
        paper_format = self.paper_format or 'A4'
        paper_width  = int(self.paper_width or 0)
        paper_height = int(self.paper_height or 0)
        old_view     = self.view_id.id   if self.view_id   else None
        old_action   = self.action_id.id if self.action_id else None

        if not model:
            self.write({'state': 'error', 'install_log': 'model_name is required.'})
            return True
        if not tech:
            self.write({'state': 'error', 'install_log': 'technical_name is required.'})
            return True

        # report_name MUST equal the template key — official Odoo rule
        report_name = 'mcp_report.' + tech
        temp_report_name = report_name + '.__tmp__.' + uuid.uuid4().hex
        ok  = False
        msg = ''
        view = self.env['ir.ui.view']
        action = self.env['ir.actions.report']
        created_paperformat = self.env['report.paperformat']

        try:
            IrView   = self.env['ir.ui.view'].sudo()
            IrReport = self.env['ir.actions.report'].sudo()

            # Clean only stale temporary records first. The current live report
            # is kept intact until the replacement has been validated.
            IrView.search([('key', '=like', report_name + '.__tmp__.%')]).unlink()
            IrReport.search([('report_name', '=like', report_name + '.__tmp__.%')]).unlink()

            # ── 1. Auto-fix common AI mistakes in template HTML ───────────────
            page_content = tmpl_html or self._default_template(model, name)
            page_content = self._autofix_template(page_content)
            page_content, field_warnings = self._validate_field_refs(
                page_content, model, self.env)
            template_updates = {}
            if page_content != (self.template_html or '').strip():
                template_updates['template_html'] = page_content

            # ── 3. Build CSS block (baseline + user CSS with wkhtmltopdf fix) ─
            fixed_css = self._autofix_css(custom_css) if custom_css else ''
            if fixed_css != custom_css:
                template_updates['custom_css'] = fixed_css
            css_block = '<style>' + _BASE_REPORT_CSS
            if fixed_css:
                css_block += '\n/* ── Custom CSS ── */\n' + fixed_css
            css_block += '</style>\n'
            if template_updates:
                self.write(template_updates)

            # ── 3. Build QWeb arch based on selected layout ───────────────────
            layout_call = {
                'external': 'web.external_layout',
                'internal': 'web.internal_layout',
                'minimal':  'web.basic_layout',
            }.get(layout, 'web.external_layout')

            # Detect if template already iterates over docs itself
            # (multi-record patterns: card grids, directories, labels)
            is_multi = self._is_multi_record_template(page_content)

            arch = self._build_report_arch(
                temp_report_name, layout_call, page_content, css_block, is_multi
            )

            # ── 4. Create candidate ir.ui.view / ir.actions.report ───────────
            view = IrView.create({
                'name':    name + ' Report Template',
                'type':    'qweb',
                'key':     temp_report_name,
                'arch_db': arch,
                'active':  True,
            })

            # ── 5. Create candidate ir.actions.report ────────────────────────
            report_vals = {
                'name':        name,
                'model':       model,
                'report_type': rtype,
                'report_name': temp_report_name,  # must match temp view key
            }

            # Bind to model Print menu
            bmodel = self.env['ir.model'].sudo().search(
                [('model', '=', binding)], limit=1
            )
            if bmodel:
                report_vals['binding_model_id'] = bmodel.id
                report_vals['binding_type']     = 'report'

            # Paper format + landscape orientation
            if paper_format == 'custom':
                if not paper_width or not paper_height:
                    raise ValueError('Custom paper format requires paper_width and paper_height in millimeters.')
                created_paperformat = self.env['report.paperformat'].sudo().create({
                    'name': name + ' (Custom)',
                    'format': 'custom',
                    'page_width': paper_width,
                    'page_height': paper_height,
                    'orientation': 'Landscape' if landscape else 'Portrait',
                })
                report_vals['paperformat_id'] = created_paperformat.id
            elif paper_format:
                pf = self.env['report.paperformat'].sudo().search(
                    [('name', 'ilike', paper_format)], limit=1
                )
                if pf:
                    report_vals['paperformat_id'] = pf.id
            if landscape and paper_format != 'custom':
                # If a paper format is set, update its orientation;
                # otherwise create a custom one with landscape
                if report_vals.get('paperformat_id'):
                    pf_rec = self.env['report.paperformat'].sudo().browse(
                        report_vals['paperformat_id'])
                    # Don't modify shared format — copy it
                    created_paperformat = pf_rec.copy({
                        'name': name + ' (Landscape)',
                        'orientation': 'Landscape',
                    })
                    report_vals['paperformat_id'] = created_paperformat.id
                else:
                    created_paperformat = self.env['report.paperformat'].sudo().create({
                        'name': name + ' (Landscape)',
                        'format': paper_format or 'A4',
                        'orientation': 'Landscape',
                    })
                    report_vals['paperformat_id'] = created_paperformat.id

            action = IrReport.create(report_vals)

            # ── 6. Validate candidate render before swapping ─────────────────
            try:
                sample_label = self._validate_report_render(
                    action, temp_report_name, model
                )
            except Exception as render_error:
                raise ValueError(
                    'Live report validation failed on model "%s" using %s: %s'
                    % (model, sample_label if 'sample_label' in locals() else 'validation context', render_error)
                )

            # ── 7. Swap candidate into place only after validation succeeds ──
            with self.env.cr.savepoint():
                for m, rid in [
                    ('ir.ui.view', old_view),
                    ('ir.actions.report', old_action),
                ]:
                    if rid:
                        try:
                            self.env[m].sudo().browse(rid).unlink()
                        except Exception:
                            pass

                stale_views = IrView.search([
                    ('key', '=', report_name),
                    ('id', '!=', view.id),
                ])
                if stale_views:
                    stale_views.unlink()
                stale_actions = IrReport.search([
                    ('report_name', '=', report_name),
                    ('id', '!=', action.id),
                ])
                if stale_actions:
                    stale_actions.unlink()

                view.write({'key': report_name})
                action.write({'report_name': report_name})
                self.write({'view_id': view.id, 'action_id': action.id})

            ok  = True
            base = self.env['ir.config_parameter'].sudo().get_str('web.base.url', '')
            msg = (
                'Report "' + name + '" installed.\n'
                'Layout:      ' + layout_call + '\n'
                'Model:       ' + model + '\n'
                'report_name: ' + report_name + '\n\n'
                'Open any ' + binding + ' record → Print → ' + name + '\n'
                'Preview: ' + base + '/report/html/' + report_name
            )
            if field_warnings:
                msg += '\n\n\u26a0 Field warnings (auto-fixed):\n' + '\n'.join(field_warnings)
            msg += '\nValidated with: ' + sample_label

        except Exception as e:
            _logger.error('mcp.report [%s]: %s', tech, e, exc_info=True)
            for rec in (action, view, created_paperformat):
                try:
                    if rec:
                        rec.sudo().unlink()
                except Exception:
                    pass
            self.write({'view_id': old_view or False, 'action_id': old_action or False})
            msg = 'Install failed: ' + str(e)

        self.write({'state': 'installed' if ok else 'error', 'install_log': msg})
        return True

    def action_uninstall(self):
        self.ensure_one()
        for fname, m in [('view_id', 'ir.ui.view'), ('action_id', 'ir.actions.report')]:
            rec = self[fname]
            if rec:
                try:
                    rec.sudo().unlink()
                except Exception as e:
                    _logger.warning('report uninstall %s: %s', m, e)
        self.write({
            'state': 'draft', 'view_id': False,
            'action_id': False, 'install_log': 'Uninstalled.',
        })

    def action_preview(self):
        self.ensure_one()
        if not self.action_id:
            return
        # Odoo report URLs require at least one record ID to render
        # e.g. /report/html/mcp_report.xyz/42
        model = (self.model_name or '').strip()
        sample_id = ''
        if model:
            try:
                rec = self.env[model].sudo().search([], limit=1)
                if rec:
                    sample_id = '/' + str(rec.id)
            except Exception:
                pass
        return {
            'type':   'ir.actions.act_url',
            'url':    '/report/html/' + self.action_id.report_name + sample_id,
            'target': 'new',
        }

    # =========================================================================
    # Auto-fix — correct common AI mistakes before saving
    # =========================================================================
    @staticmethod
    def _autofix_template(html):
        """
        Fix common AI-generated QWeb mistakes and wkhtmltopdf incompatibilities.

        Fix 1: <td t-field="..."> → <td><span t-field="..."/></td>
        Fix 2: company.xxx → res_company.xxx
        Fix 3: Ensure <table> tags have Bootstrap 'table' class
        Fix 4: docs.filtered(lambda ...) → docs (redundant inside per-doc loop)
        Fix 5: display:flex → -webkit-box (wkhtmltopdf compat)
        Fix 6: calc() → fixed values (wkhtmltopdf doesn't support calc)
        Fix 7: linear-gradient → -webkit-linear-gradient
        """
        # Fix 1: t-field on td/th/tr
        def _fix_td(m):
            tag    = m.group(1)
            before = m.group(2).strip()
            expr   = m.group(3)
            after  = m.group(4).strip()
            attrs  = ((' ' + before) if before else '') + ((' ' + after) if after else '')
            return '<' + tag + attrs + '><span t-field="' + expr + '"/>'

        html = re.sub(
            r'<(td|th|tr)([^>]*)\bt-field="([^"]+)"([^>]*)>',
            _fix_td, html
        )

        # Fix 2: wrong company variable names
        for wrong in ['company.', 'o_company.', 'o.company_id.']:
            html = html.replace('t-esc="'   + wrong, 't-esc="res_company.')
            html = html.replace('t-field="' + wrong, 't-field="res_company.')
            html = html.replace('t-if="'    + wrong, 't-if="res_company.')

        # Fix 3: ensure <table> has Bootstrap 'table' class
        html = McpReport._autofix_table_classes(html)

        # Fix 4: strip docs.filtered(lambda ...) — template is already
        # inside t-foreach="docs" t-as="doc", so filtering is redundant
        # and lambda expressions can crash in QWeb safe_eval.
        # Replace:  t-value="docs.filtered(lambda ...)"  →  t-value="docs"
        html = re.sub(
            r't-value="docs\.filtered\(lambda[^"]*\)"',
            't-value="docs"',
            html
        )

        # Fix 5: wkhtmltopdf CSS — display:flex → -webkit-box
        # wkhtmltopdf 12.6 has broken flexbox; use -webkit-box instead
        html = re.sub(
            r'display\s*:\s*flex',
            'display:-webkit-box;display:flex',
            html
        )
        html = re.sub(
            r'flex-wrap\s*:\s*wrap',
            '-webkit-flex-wrap:wrap;flex-wrap:wrap',
            html
        )

        # Fix 6: calc() → fixed widths (wkhtmltopdf can't eval calc)
        # Common: width:calc(50% - 8px) → width:48%
        def _fix_calc(m):
            try:
                pct = float(m.group(1))
                px  = float(m.group(2))
                # Approximate: subtract px as % of typical page width (~700px)
                approx = max(10, pct - (px / 7.0))
                return 'width:%.1f%%' % approx
            except (ValueError, ZeroDivisionError):
                return m.group(0)
        html = re.sub(
            r'width\s*:\s*calc\(\s*([\d.]+)%\s*-\s*([\d.]+)px\s*\)',
            _fix_calc, html
        )

        # Fix 7: linear-gradient needs -webkit- prefix for wkhtmltopdf
        html = re.sub(
            r'(?<!-webkit-)linear-gradient',
            '-webkit-linear-gradient',
            html
        )

        # Fix 8: hasattr() is not available in QWeb safe_eval context
        # Replace: hasattr(doc, 'mobile')  →  'mobile' in doc
        html = re.sub(
            r"hasattr\(\s*([^,]+)\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
            r"'\2' in \1",
            html
        )

        return html

    @staticmethod
    def _autofix_table_classes(html):
        """Ensure every <table> tag has at least 'table table-bordered' classes."""
        def _fix_table_tag(m):
            full_tag = m.group(0)
            # Already has a 'table' class? skip
            if re.search(r'\bclass\s*=\s*["\'][^"\']*\btable\b', full_tag):
                return full_tag
            # Has a class attr? append to it
            if 'class=' in full_tag:
                return re.sub(
                    r'class\s*=\s*(["\'])',
                    r'class=\1table table-bordered ',
                    full_tag, count=1
                )
            # No class attr — add one
            return full_tag.replace('<table', '<table class="table table-bordered"', 1)

        return re.sub(r'<table(?:\s[^>]*)?>',  _fix_table_tag, html)

    @staticmethod
    def _is_multi_record_template(html):
        """
        Detect if the template already has its own iteration over 'docs'.

        Multi-record templates (card grids, directories, labels) contain
        their own t-foreach that iterates over 'docs' or a variable
        derived from docs (e.g. docs.filtered(...)).

        Per-record templates use 'doc.field_name' directly.

        Returns True if the template handles its own docs iteration.
        """
        # Pattern 1: t-foreach="docs" or t-foreach="customers" where
        # customers is set from docs
        if re.search(r't-foreach="docs"', html):
            return True
        # Pattern 2: t-set that assigns from docs (e.g. docs.filtered, docs.sorted)
        # followed by t-foreach using that variable
        t_sets = re.findall(r't-set="(\w+)"\s+t-value="docs[.\[]', html)
        for var_name in t_sets:
            if re.search(r't-foreach="' + re.escape(var_name) + r'"', html):
                return True
        # Pattern 3: template uses "docs" in t-esc/t-foreach but never "doc."
        # (no single-record field access)
        if 'docs' in html and not re.search(r'\bdoc\.', html):
            return True
        return False

    @staticmethod
    def _autofix_css(css):
        """
        Fix wkhtmltopdf-incompatible CSS patterns in custom_css.

        wkhtmltopdf 12.6 uses an old WebKit engine that doesn't support:
        - display: flex (use float or table layout instead)
        - calc() (use fixed values)
        - CSS custom properties var(--)
        - gap property with flexbox
        - linear-gradient (needs -webkit- prefix)
        """
        if not css:
            return css

        # Fix 1: display:flex → display:block with float children
        # wkhtmltopdf cannot render flex layouts at all
        css = re.sub(
            r'display\s*:\s*flex\s*;',
            'display: block;',
            css
        )

        # Fix 2: flex-wrap → remove (not useful without flex)
        css = re.sub(r'flex-wrap\s*:\s*\w+\s*;', '', css)

        # Fix 3: gap → margin fallback (gap doesn't work without flex/grid)
        css = re.sub(r'\bgap\s*:\s*[^;]+;', '', css)

        # Fix 4: calc() → approximate fixed values
        def _fix_calc(m):
            prop = m.group(1)
            try:
                pct = float(m.group(2))
                px  = float(m.group(3))
                # Approximate: subtract px as % of ~700px page width
                approx = max(10.0, pct - (px / 7.0))
                return '%s: %.1f%%;' % (prop, approx)
            except (ValueError, ZeroDivisionError):
                return m.group(0)
        css = re.sub(
            r'(width|height|max-width|min-width)\s*:\s*calc\(\s*([\d.]+)%\s*-\s*([\d.]+)px\s*\)\s*;',
            _fix_calc, css
        )

        # Fix 5: linear-gradient → -webkit-linear-gradient
        css = re.sub(
            r'(?<!-webkit-)linear-gradient',
            '-webkit-linear-gradient',
            css
        )

        # Fix 6: flex:1 / flex-shrink / flex-grow → remove
        css = re.sub(r'flex\s*:\s*[^;]+;', '', css)
        css = re.sub(r'flex-shrink\s*:\s*[^;]+;', '', css)
        css = re.sub(r'flex-grow\s*:\s*[^;]+;', '', css)

        # Fix 7: align-items / justify-content → remove (flex-only)
        css = re.sub(r'align-items\s*:\s*[^;]+;', '', css)
        css = re.sub(r'justify-content\s*:\s*[^;]+;', '', css)

        return css

    # =========================================================================
    # Field validation — guard against non-existent fields
    # =========================================================================
    @staticmethod
    def _validate_field_refs(html, model_name, env):
        """
        Scan QWeb template for doc/loop_alias field references, check if fields
        actually exist on the target model, and auto-fix invalid ones:

        - t-field="doc.bad_field"   → wrapped with t-if="'bad_field' in doc"
        - t-esc="doc.bad_field"     → t-esc="doc.bad_field if 'bad_field' in doc else ''"
        - t-field="line.bad_field"  → corrected/guarded using the model behind t-as="line"
        - common singular/plural mistakes are auto-corrected:
            line.tax_id   → line.tax_ids
            line.tag_ids  → line.tag_id   (if only singular exists)

        Returns (fixed_html, list_of_warning_strings).
        """
        warnings = []
        try:
            root_model = env[model_name].sudo()
        except KeyError:
            # Model doesn't exist — can't validate, skip
            return html, ['Model "' + model_name + '" not found, skipping field validation.']

        alias_models = {'doc': root_model}

        def _model_for_expr(expr):
            expr = (expr or '').strip()
            if not expr or '.' not in expr:
                return None
            base_alias, path = expr.split('.', 1)
            model = alias_models.get(base_alias)
            if not model:
                return None
            current = model
            for token in path.split('.'):
                field = current._fields.get(token)
                if not field:
                    return None
                comodel_name = getattr(field, 'comodel_name', None)
                if not comodel_name:
                    return None
                try:
                    current = env[comodel_name].sudo()
                except KeyError:
                    return None
            return current

        foreach_patterns = [
            (expr, alias)
            for _, expr, _, alias in re.findall(
                r"""t-foreach\s*=\s*(['"])([^'"]+)\1\s+t-as\s*=\s*(['"])([a-zA-Z_][a-zA-Z0-9_]*)\3""",
                html
            )
        ] + [
            (expr, alias)
            for _, alias, _, expr in re.findall(
                r"""t-as\s*=\s*(['"])([a-zA-Z_][a-zA-Z0-9_]*)\1\s+t-foreach\s*=\s*(['"])([^'"]+)\3""",
                html
            )
        ]
        for expr, alias in foreach_patterns:
            target_model = _model_for_expr(expr)
            if target_model is not None:
                alias_models[alias] = target_model

        # First pass: apply known Odoo field aliases globally for each resolved
        # template alias, regardless of quote style or attribute formatting.
        for alias, model in alias_models.items():
            for wrong_field, correct_field in _REPORT_FIELD_ALIASES.get(model._name, {}).items():
                if correct_field not in model._fields:
                    continue
                if re.search(r'\b' + re.escape(alias) + r'\.' + re.escape(wrong_field) + r'\b', html):
                    warnings.append(
                        '  - "' + alias + '.' + wrong_field + '" not found on ' + model._name +
                        ' (auto-corrected to "' + correct_field + '")'
                    )
                    html = re.sub(
                        r'\b' + re.escape(alias) + r'\.' + re.escape(wrong_field) + r'\b',
                        alias + '.' + correct_field,
                        html
                    )

        field_refs = re.findall(
            r"""\b(t-(?:field|esc|out|if|elif|value|foreach|att(?:-[a-zA-Z_][a-zA-Z0-9_-]*)?))\s*=\s*(['"])[^'"]*\b([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_.]*)[^'"]*\2""",
            html
        )

        seen = set()
        for attr_name, _, alias, ref in field_refs:
            model = alias_models.get(alias)
            if not model:
                continue
            valid_fields = set(model._fields.keys())
            root_field = ref.split('.')[0]
            cache_key = (alias, model._name, root_field)
            if root_field in valid_fields or cache_key in seen:
                continue
            seen.add(cache_key)

            corrected_field = None
            alias_target = _REPORT_FIELD_ALIASES.get(model._name, {}).get(root_field)
            if alias_target and alias_target in valid_fields:
                corrected_field = alias_target
            elif root_field.endswith('_id') and root_field[:-3] + '_ids' in valid_fields:
                corrected_field = root_field[:-3] + '_ids'
            elif root_field.endswith('_ids') and root_field[:-4] + '_id' in valid_fields:
                corrected_field = root_field[:-4] + '_id'

            if corrected_field:
                warnings.append(
                    '  - "' + alias + '.' + root_field + '" not found on ' + model._name +
                    ' (auto-corrected to "' + corrected_field + '")'
                )
                html = re.sub(
                    r'\b' + re.escape(alias) + r'\.' + re.escape(root_field) + r'\b',
                    alias + '.' + corrected_field,
                    html
                )
                continue

            warnings.append(
                '  - "' + alias + '.' + root_field + '" not found on ' + model._name + ' (auto-sanitized)'
            )

            # Remove invalid QWeb expressions from the final template so QWeb
            # never receives a bad field path.

            def _replace_attr_value(attr_regex, replacement):
                pattern = re.compile(
                    r'(' + attr_regex + r'\s*=\s*)(["\'])[^"\']*\b'
                    + re.escape(alias) + r'\.' + re.escape(root_field)
                    + r'(?:\.[a-zA-Z_][a-zA-Z0-9_.]*)?[^"\']*\2'
                )
                return pattern.sub(
                    lambda m: m.group(1) + m.group(2) + replacement + m.group(2),
                    html,
                )

            # Remove invalid t-field/t-esc/t-out/t-if expressions from the
            # final template so QWeb never receives a bad field path.
            tfield_pattern = re.compile(
                r'(<[a-zA-Z][^>]*\bt-field\s*=\s*(["\']))'
                + re.escape(alias) + r'\.' + re.escape(root_field)
                + r'(?:\.[a-zA-Z_][a-zA-Z0-9_.]*)?'
                + r'(\2[^>]*>)'
            )

            def _sanitize_tfield(match):
                tag = match.group(0)
                return re.sub(
                    r'\bt-field\s*=\s*(["\']).*?\1',
                    't-esc="\'\'"',
                    tag,
                    count=1,
                )

            html = tfield_pattern.sub(_sanitize_tfield, html)

            for text_attr in ('t-esc', 't-out'):
                html = re.compile(
                    r'(\b' + text_attr + r'\s*=\s*)(["\'])[^"\']*\b'
                    + re.escape(alias) + r'\.' + re.escape(root_field)
                    + r'(?:\.[a-zA-Z_][a-zA-Z0-9_.]*)?[^"\']*\2'
                ).sub(
                    lambda m: m.group(1) + m.group(2) + "''" + m.group(2),
                    html,
                )

            for bool_attr in ('t-if', 't-elif', 't-value'):
                html = re.compile(
                    r'(\b' + bool_attr + r'\s*=\s*)(["\'])[^"\']*\b'
                    + re.escape(alias) + r'\.' + re.escape(root_field)
                    + r'(?:\.[a-zA-Z_][a-zA-Z0-9_.]*)?[^"\']*\2'
                ).sub(
                    lambda m: m.group(1) + m.group(2) + 'False' + m.group(2),
                    html,
                )

            html = re.compile(
                r'(\bt-foreach\s*=\s*)(["\'])[^"\']*\b'
                + re.escape(alias) + r'\.' + re.escape(root_field)
                + r'(?:\.[a-zA-Z_][a-zA-Z0-9_.]*)?[^"\']*\2'
            ).sub(
                lambda m: m.group(1) + m.group(2) + '[]' + m.group(2),
                html,
            )

            for att_match in set(
                re.findall(r'\b(t-att(?:-[a-zA-Z_][a-zA-Z0-9_-]*)?)\b', html)
            ):
                html = re.compile(
                    r'(\b' + re.escape(att_match) + r'\s*=\s*)(["\'])[^"\']*\b'
                    + re.escape(alias) + r'\.' + re.escape(root_field)
                    + r'(?:\.[a-zA-Z_][a-zA-Z0-9_.]*)?[^"\']*\2'
                ).sub(
                    lambda m: m.group(1) + m.group(2) + "''" + m.group(2),
                    html,
                )

        return html, warnings

    # =========================================================================
    # Default templates per layout type
    # =========================================================================
    @staticmethod
    def _default_template(model, name):
        """
        Generic default template — used when AI provides no template_html.
        Shows basic record info — works for any model.
        """
        return (
            '<div class="row mb-4">'
            '<div class="col-6"><h3 t-esc="doc.display_name"/></div>'
            '<div class="col-6 text-end text-muted small">'
            '<p t-if="hasattr(doc, \'date_order\')">'
            'Date: <span t-field="doc.date_order"/></p>'
            '<p t-elif="hasattr(doc, \'date\')">'
            'Date: <span t-field="doc.date"/></p>'
            '</div>'
            '</div>'
            '<table class="table table-sm table-bordered">'
            '<tbody>'
            '<tr t-if="hasattr(doc, \'partner_id\') and doc.partner_id">'
            '<th style="width:30%">Partner</th>'
            '<td t-esc="doc.partner_id.display_name"/>'
            '</tr>'
            '<tr t-if="hasattr(doc, \'state\')">'
            '<th>Status</th>'
            '<td t-esc="doc.state"/>'
            '</tr>'
            '<tr t-if="hasattr(doc, \'amount_total\')">'
            '<th>Total</th>'
            '<td><strong><span t-field="doc.amount_total"/></strong></td>'
            '</tr>'
            '</tbody>'
            '</table>'
        )
