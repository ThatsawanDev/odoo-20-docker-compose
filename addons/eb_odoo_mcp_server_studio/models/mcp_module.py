# -*- coding: utf-8 -*-
# =============================================================================
#  mcp.module — AI Module Builder
#
#  Uses Odoo 19's exact base_import_module API for installation:
#    base.import.module wizard → IrModule._import_zipfile(BytesIO)
#    → _import_module() → convert_file() for each XML/CSV
#    → Module gets imported=True, state='installed'
# =============================================================================
import base64
import logging

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.addons.eb_odoo_mcp_server_studio.controllers.odoo_module import _auto_generate_security_csv, _auto_generate_security_xml
from odoo.addons.eb_odoo_mcp_server_studio.controllers.odoo_module import ( _fix_security_csv_model_refs, _pre_install_cross_validate)
_logger = logging.getLogger(__name__)


class McpModule(models.Model):
    _name        = 'mcp.module'
    _description = 'MCP Generated Module'
    _order       = 'create_date desc'
    _inherit     = ['mail.thread']

    name           = fields.Char(string='Module Name', required=True, tracking=True)
    technical_name = fields.Char(string='Technical Name', required=True, index=True)
    description    = fields.Text(string='Description')
    version        = fields.Char(string='Version', default='19.0.1.0.0')
    state          = fields.Selection([
        ('draft',     'Draft'),
        ('generated', 'Generated'),
        ('installed', 'Installed'),
        ('error',     'Error'),
    ], string='State', default='draft', tracking=True)
    attachment_id  = fields.Many2one('ir.attachment', string='Module ZIP')
    install_log    = fields.Text(string='Install Log', readonly=True)
    user_id        = fields.Many2one('res.users', string='Created By',
                                     default=lambda self: self.env.user)
    active         = fields.Boolean(default=True)

    # ── Code fields ────────────────────────────────────────────────────────
    manifest_code   = fields.Text(string='__manifest__.py')
    models_code     = fields.Text(string='Model Definitions (XML)')
    views_code      = fields.Text(string='Views XML')
    security_code   = fields.Text(string='Security CSV')
    data_files_code = fields.Text(string='Extra Data Files (JSON)')
    demo_data_code  = fields.Text(string='Demo Data (XML)')
    report_code     = fields.Text(string='Report Templates (XML)')
    js_code         = fields.Text(string='JavaScript / OWL (JSON)')
    scss_code       = fields.Text(string='SCSS Stylesheets (JSON)')
    owl_code        = fields.Text(string='OWL XML Templates (JSON)')
    icon_image      = fields.Binary(string='Module Icon', attachment=True)

    # =====================================================================
    #  ZIP Generation
    # =====================================================================

    def action_generate_zip(self):
        """Generate ZIP and update manifest_code to show the actual manifest used."""
        self.ensure_one()
        zip_data, actual_manifest = self._build_zip()  # now returns tuple

        if self.attachment_id:
            self.attachment_id.unlink()

        attach = self.env['ir.attachment'].create({
            'name': f"{self.technical_name}.zip",
            'datas': base64.b64encode(zip_data).decode(),
            'mimetype': 'application/zip',
            'res_model': 'mcp.module',
            'res_id': self.id,
        })
        self.write({
            'attachment_id': attach.id,
            'state': 'generated',
            'install_log': 'ZIP generated successfully.',
            'manifest_code': actual_manifest,  # always show exact manifest in the ZIP
        })
        return True

    # =====================================================================
    #  Module Installation — uses Odoo 19 base_import_module exact API
    #
    #  Source: odoo/addons/base_import_module/models/base_import_module.py
    #
    #    class BaseImportModule(TransientModel):
    #        def import_module(self):
    #            zip_data = base64.decodebytes(self.module_file)
    #            fp = BytesIO()
    #            fp.write(zip_data)
    #            IrModule._import_zipfile(fp, force=self.force)
    #
    #  The _import_zipfile method:
    #    1. Opens ZIP, finds manifest files
    #    2. Extracts to temp directory (file_open_temporary_directory)
    #    3. For each module: calls _import_module(name, path)
    #    4. _import_module: reads manifest, checks deps, creates/updates
    #       ir.module.module record with imported=True + state='installed',
    #       then calls convert_file() for each XML/CSV in 'data' list
    #    5. Static files → ir.attachment, translations → load
    # =====================================================================

    def action_install_module(self):
        """
        Validate → auto-fix → generate ZIP → install via base_import_module.
        Now runs all fixes and validation whether called from UI button or MCP tool.
        """
        self.ensure_one()

        # ── 1. Import fixers (lazy to avoid circular import) ─────────────
        try:
            from .odoo_module import _apply_all_fixes, _validate_module_code
            _apply_all_fixes(self)
            issues = _validate_module_code(self)
            errors = [i for i in issues if i.startswith('ERROR')]
            if errors:
                msg = (
                        f"Cannot install — {len(errors)} error(s) must be fixed:\n"
                        + "\n".join(errors)
                        + "\n\nUse action='fix' then action='install' again, "
                          "or click 'Fix & Install' if available."
                )
                self.write({'state': 'error', 'install_log': msg})
                return True
        except ImportError:
            _logger.warning("Could not import odoo_module fixers — skipping pre-validation.")

        # ── 2. Generate ZIP ───────────────────────────────────────────────
        self.action_generate_zip()

        zip_data = base64.b64decode(self.attachment_id.datas)
        b64_zip = base64.b64encode(zip_data).decode()

        install_ok = False
        log_msg = ''

        try:
            with self.env.cr.savepoint():
                wizard = self.env['base.import.module'].create({
                    'module_file': b64_zip,
                    'state': 'init',
                    'force': True,
                })
                wizard.import_module()

            self.env.registry.clear_cache()
            install_ok = True
            log_msg = (
                f"Module '{self.technical_name}' installed successfully.\n\n"
                f"IMPORTANT: Reload your browser (Ctrl+Shift+R) to see new menus.\n\n"
                f"To update: call action='update' then action='install' again. "
                f"Do NOT use the Apps 'Upgrade' button on imported modules."
            )

        except Exception as e:
            _logger.error("Module install failed [%s]: %s",
                          self.technical_name, e, exc_info=True)
            error_str = str(e)

            if 'Unknown module dependencies' in error_str:
                log_msg = (
                    f"Install failed — missing dependencies:\n{error_str}\n\n"
                    f"Add missing modules to manifest depends "
                    f"(base_automation, mail, sale, account, stock, hr, etc.)."
                )
            elif 'Only administrators' in error_str:
                log_msg = (
                    f"Install failed — permission denied.\n"
                    f"Log in as an Odoo administrator and try again."
                )
            elif 'No matching record found for external id' in error_str:
                log_msg = (
                    f"Install failed — external ID not found:\n{error_str}\n\n"
                    f"The security CSV references a model that isn't defined in models_code, "
                    f"or the record id in models_code doesn't match the CSV reference.\n"
                    f"Check that every CSV row's model_id:id matches an "
                    f"<record id='...' model='ir.model'> id exactly."
                )
            elif 'null value in column' in error_str and 'model_id' in error_str:
                log_msg = (
                    f"Install failed — security CSV model reference is NULL:\n{error_str}\n\n"
                    f"The CSV model_id:id column references an external ID that doesn't exist. "
                    f"Check that the model record id in models_code matches the CSV reference. "
                    f"Example: if models_code has <record id='model_x_task'> then CSV must use model_x_task."
                )
            else:
                log_msg = (
                    f"Auto-install failed: {error_str}\n\n"
                    f"Manual install:\n"
                    f"  1. Click 'Download ZIP'\n"
                    f"  2. Go to Odoo → Apps → Import Module\n"
                    f"  3. Upload the .zip file\n"
                    f"  4. Refresh browser"
                )

        self.write({
            'state': 'installed' if install_ok else 'error',
            'install_log': log_msg,
        })
        return True

    def action_download_zip(self):
        """Download the generated ZIP file."""
        self.ensure_one()
        if not self.attachment_id:
            self.action_generate_zip()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.attachment_id.id}?download=true',
            'target': 'self',
        }

    # =====================================================================
    #  ZIP Builder — creates a valid Odoo module structure
    # =====================================================================

    def _build_zip(self):
        """
        Build complete Odoo 19 importable module ZIP.
        Returns (zip_bytes, actual_manifest_str) tuple.

        CRITICAL LOAD ORDER (Odoo 19 processes data files sequentially):
          1. models/models.xml          ← ir.model + ir.model.fields FIRST
          2. security/security_groups.xml
          3. security/ir_model_access.xml  ← ALWAYS XML, AFTER views
          4. security/record_rules.xml
          5. data/sequences.xml
          6. actions/server_actions.xml  ← BEFORE views (buttons use %(id)d refs)
          7. actions/automated.xml       ← BEFORE views
          8. views/views.xml             ← act_window buttons resolve after server actions
          9. data/mail_templates.xml
         10. report/report_actions.xml
         11. report/report_templates.xml
         12. data/cron.xml
        """
        import base64 as _b64
        import io as _io
        import json as _json
        import zipfile as _zip
        import re as _re

        self.ensure_one()
        tech = self.technical_name
        buf = _io.BytesIO()
        data_files = []
        demo_files = []

        with _zip.ZipFile(buf, 'w', _zip.ZIP_DEFLATED) as zf:

            # ── __init__.py — single write, always data-only ─────────────
            zf.writestr(f"{tech}/__init__.py",
                        "# -*- coding: utf-8 -*-\n# Data-only module\n")

            # ── 1. MODELS (MUST be first) ─────────────────────────────────
            mc = (self.models_code or '').strip()
            if mc:
                # Safety: detect Python class code and refuse to wrap as XML
                is_python = bool(
                    _re.search(r'\bclass\s+\w+\s*\(', mc) or
                    'from odoo import' in mc or
                    'from odoo import' in mc
                )
                if is_python:
                    _logger.error(
                        "mcp.module [%s]: models_code contains Python — "
                        "base_import_module does NOT execute Python files. "
                        "Use ir.model XML records instead.",
                        tech,
                    )
                    placeholder = (
                        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
                        "<odoo><data noupdate=\"1\">\n"
                        "<!-- ERROR: models_code contained Python class code.\n"
                        "     Replace with ir.model + ir.model.fields XML records.\n"
                        "     base_import_module NEVER executes Python files. -->\n"
                        "</data></odoo>"
                    )
                    zf.writestr(f"{tech}/models/models.xml", placeholder)
                    data_files.append('models/models.xml')
                else:
                    # models.xml MUST use noupdate="1" so Odoo never tries to
                    # UPDATE ir.model / ir.model.fields records on reinstall.
                    # Re-processing them causes the ParseError at line 5.
                    content = self._ensure_xml_wrapper(mc, noupdate=True)
                    zf.writestr(f"{tech}/models/models.xml", content)
                    data_files.append('models/models.xml')

            # ── 2–4. SECURITY (after models, before views) ────────────────
            # NOTE: Groups and rules load here. Access rights are deferred
            #       to AFTER views (section 8b) so model XML IDs exist.
            views_raw = (self.views_code or '').strip()

            groups_xml = self._extract_by_model(views_raw, 'res.groups')
            if groups_xml:
                zf.writestr(f"{tech}/security/security_groups.xml",
                            self._ensure_xml_wrapper(groups_xml))
                data_files.append('security/security_groups.xml')

            rules_xml = self._extract_by_model(views_raw, 'ir.rule')
            if rules_xml:
                zf.writestr(f"{tech}/security/record_rules.xml",
                            self._ensure_xml_wrapper(rules_xml))
                data_files.append('security/record_rules.xml')

            # ── 5. SEQUENCES ──────────────────────────────────────────────
            seq_xml = self._extract_by_model(views_raw, 'ir.sequence')
            if seq_xml:
                zf.writestr(f"{tech}/data/sequences.xml",
                            self._ensure_xml_wrapper(seq_xml))
                data_files.append('data/sequences.xml')

            # ── 6. SERVER ACTIONS ← BEFORE VIEWS ─────────────────────────
            # Odoo resolves %(action_server_NAME)d refs at view-load time.
            # The server action record must already exist in ir.model.data
            # before the view file that references it is processed.
            srv_xml = self._extract_by_model(views_raw, 'ir.actions.server')
            if srv_xml:
                zf.writestr(f"{tech}/actions/server_actions.xml",
                            self._ensure_xml_wrapper(srv_xml))
                data_files.append('actions/server_actions.xml')

            # ── 7. AUTOMATED ACTIONS ← BEFORE VIEWS ──────────────────────
            auto_xml = self._extract_by_model(views_raw, 'base.automation')
            if auto_xml:
                zf.writestr(f"{tech}/actions/automated.xml",
                            self._ensure_xml_wrapper(auto_xml))
                data_files.append('actions/automated.xml')

            # ── 8. VIEWS + ACT_WINDOW + MENUS ─────────────────────────────
            skip_models = {
                'res.groups', 'ir.rule', 'ir.sequence',
                'ir.actions.server', 'base.automation',
                'mail.template', 'ir.cron',
                'ir.actions.report', 'report.paperformat',
            }
            views_clean = self._remove_models_from_xml(views_raw, skip_models)
            views_no_templates = self._extract_templates(views_clean)[1]

            if views_no_templates.strip():
                sanitized = self._sanitize_views_xml(views_no_templates)
                zf.writestr(f"{tech}/views/views.xml",
                            self._ensure_xml_wrapper(sanitized))
                data_files.append('views/views.xml')

            # ── 8b. ACCESS RIGHTS (AFTER views — model XML IDs now exist) ─
            # ALWAYS regenerate XML security from models_code.
            # CSV refs (model_id:id) CANNOT resolve during base_import_module
            # because the XML IDs are not yet committed. XML ref() works.
            if mc:
                access_xml = _auto_generate_security_xml(mc)
                if access_xml:
                    zf.writestr(f"{tech}/security/ir_model_access.xml", access_xml)
                    data_files.append('security/ir_model_access.xml')
                    # Also update stored security_code to XML format
                    if not (self.security_code or '').strip().startswith('<'):
                        self.write({'security_code': access_xml})

            # ── 9. MAIL TEMPLATES ─────────────────────────────────────────
            mail_xml = self._extract_by_model(views_raw, 'mail.template')
            if mail_xml:
                zf.writestr(f"{tech}/data/mail_templates.xml",
                            self._ensure_xml_wrapper(mail_xml))
                data_files.append('data/mail_templates.xml')

            # ── 10. REPORTS ───────────────────────────────────────────────
            if self.report_code and self.report_code.strip():
                rpt_raw = self.report_code.strip()
                rpt_actions = self._extract_by_model(rpt_raw, 'ir.actions.report')
                rpt_paperformat = self._extract_by_model(rpt_raw, 'report.paperformat')
                templates_xml, _ = self._extract_templates(rpt_raw)

                if rpt_actions or rpt_paperformat:
                    combined = (rpt_actions or '') + '\n' + (rpt_paperformat or '')
                    zf.writestr(f"{tech}/report/report_actions.xml",
                                self._ensure_xml_wrapper(combined))
                    data_files.append('report/report_actions.xml')

                if templates_xml:
                    zf.writestr(f"{tech}/report/report_templates.xml",
                                self._ensure_xml_wrapper(templates_xml))
                    data_files.append('report/report_templates.xml')

            # ── 11. CRON JOBS ─────────────────────────────────────────────
            cron_xml = self._extract_by_model(views_raw, 'ir.cron')
            if cron_xml:
                zf.writestr(f"{tech}/data/cron.xml",
                            self._ensure_xml_wrapper(cron_xml))
                data_files.append('data/cron.xml')

            # ── 12. EXTRA DATA FILES ──────────────────────────────────────
            if self.data_files_code and self.data_files_code.strip():
                try:
                    for fname, content in _json.loads(self.data_files_code).items():
                        zf.writestr(f"{tech}/{fname}",
                                    self._ensure_xml_wrapper(content))
                        data_files.append(fname)
                except _json.JSONDecodeError:
                    pass

            # ── 13. DEMO DATA ─────────────────────────────────────────────
            if self.demo_data_code and self.demo_data_code.strip():
                zf.writestr(f"{tech}/demo/demo.xml",
                            self._ensure_xml_wrapper(self.demo_data_code.strip()))
                demo_files.append('demo/demo.xml')

            # ── 14. JS / SCSS / OWL ───────────────────────────────────────
            asset_paths = []

            if self.js_code and self.js_code.strip():
                try:
                    for fname, code in _json.loads(self.js_code).items():
                        zf.writestr(f"{tech}/static/src/js/{fname}", code)
                        asset_paths.append(f"{tech}/static/src/js/{fname}")
                except _json.JSONDecodeError:
                    zf.writestr(f"{tech}/static/src/js/main.js", self.js_code)
                    asset_paths.append(f"{tech}/static/src/js/main.js")

            if self.scss_code and self.scss_code.strip():
                try:
                    for fname, code in _json.loads(self.scss_code).items():
                        zf.writestr(f"{tech}/static/src/scss/{fname}", code)
                        asset_paths.append(f"{tech}/static/src/scss/{fname}")
                except _json.JSONDecodeError:
                    zf.writestr(f"{tech}/static/src/scss/main.scss", self.scss_code)
                    asset_paths.append(f"{tech}/static/src/scss/main.scss")

            if self.owl_code and self.owl_code.strip():
                try:
                    for fname, code in _json.loads(self.owl_code).items():
                        zf.writestr(f"{tech}/static/src/xml/{fname}", code)
                        asset_paths.append(f"{tech}/static/src/xml/{fname}")
                except _json.JSONDecodeError:
                    zf.writestr(f"{tech}/static/src/xml/templates.xml", self.owl_code)
                    asset_paths.append(f"{tech}/static/src/xml/templates.xml")

            # ── 15. ICON ──────────────────────────────────────────────────
            if self.icon_image:
                zf.writestr(f"{tech}/static/description/icon.png",
                            _b64.b64decode(self.icon_image))
            else:
                zf.writestr(
                    f"{tech}/static/description/index.html",
                    f"<html><body><h1>{self._escape(self.name)}</h1></body></html>",
                )

            # ── 16. MANIFEST (last — knows full data_files list) ──────────
            auto_manifest = self._build_manifest_v19(data_files, demo_files, asset_paths)

            # Use LLM-provided manifest only if it parses AND has a valid data list.
            # Otherwise always use the auto-generated one (it knows the real file list).
            actual_manifest = auto_manifest
            if self.manifest_code and self.manifest_code.strip():
                custom = self.manifest_code.strip()
                try:
                    import ast as _ast
                    parsed = _ast.literal_eval(custom)
                    if isinstance(parsed, dict) and parsed.get('depends'):
                        # Merge: keep LLM's depends/name/version, use auto data list
                        auto_parsed = _ast.literal_eval(auto_manifest.split('\n', 1)[1])
                        parsed['data'] = auto_parsed.get('data', [])
                        parsed['demo'] = auto_parsed.get('demo', [])
                        if asset_paths:
                            parsed['assets'] = auto_parsed.get('assets', {})
                        # Rebuild as string
                        lines = [
                            "# -*- coding: utf-8 -*-",
                            "{"
                        ]
                        for k, v in parsed.items():
                            lines.append(f"    {repr(k)}: {repr(v)},")
                        lines.append("}")
                        actual_manifest = '\n'.join(lines) + '\n'
                except Exception:
                    actual_manifest = auto_manifest

            zf.writestr(f"{tech}/__manifest__.py", actual_manifest)

        return buf.getvalue(), actual_manifest

    def _build_manifest_v19(self, data_files, demo_files, asset_paths=None):
        """Build proper Odoo 19 __manifest__.py with assets key."""
        self.ensure_one()
        views_raw = (self.views_code or '')
        models_raw = (self.models_code or '')
        all_code = views_raw + models_raw

        # ── Auto-detect depends ──────────────────────────────────
        depends = ['base']
        if any(kw in all_code for kw in (
            'chatter', 'mail.template', 'mail.mt_note',
            'message_post', 'mail.thread',
        )):
            depends.append('mail')
        if any(kw in all_code for kw in (
            'base.automation', 'ir.actions.server', 'ir.cron',
        )):
            depends.append('base_automation')
        if 'sale.order' in all_code:
            depends.append('sale')
        if 'account.move' in all_code:
            depends.append('account')
        if 'stock.picking' in all_code or 'stock.quant' in all_code:
            depends.append('stock')
        if 'hr.employee' in all_code:
            depends.append('hr')
        if 'project.task' in all_code or 'project.project' in all_code:
            depends.append('project')
        if 'purchase.order' in all_code:
            depends.append('purchase')
        if 'crm.lead' in all_code:
            depends.append('crm')
        # deduplicate while keeping order
        seen = set()
        depends = [d for d in depends if not (d in seen or seen.add(d))]

        dep_str = repr(depends)
        lines = [
            "# -*- coding: utf-8 -*-",
            "{",
            f"    'name': {repr(self.name or self.technical_name)},",
            f"    'version': {repr(self.version or '19.0.1.0.0')},",
            f"    'summary': {repr((self.description or self.name or '')[:100])},",
            "    'category': 'Technical',",
            "    'author': 'MCP Builder',",
            f"    'depends': {dep_str},",
            "    'installable': True,",
            "    'application': True,",
            "    'auto_install': False,",
            "    'license': 'LGPL-3',",
        ]
        if data_files:
            lines.append("    'data': [")
            for f in data_files:
                lines.append(f"        {repr(f)},")
            lines.append("    ],")
        else:
            lines.append("    'data': [],")
        if demo_files:
            lines.append("    'demo': [")
            for f in demo_files:
                lines.append(f"        {repr(f)},")
            lines.append("    ],")

        # ── Odoo 19 assets key (replaces template-based assets.xml) ──
        if asset_paths:
            lines.append("    'assets': {")
            lines.append("        'web.assets_backend': [")
            for ap in asset_paths:
                lines.append(f"            {repr(ap)},")
            lines.append("        ],")
            lines.append("    },")

        lines.append("}")
        return '\n'.join(lines) + '\n'

    @staticmethod
    def _sanitize_views_xml(xml_str):
        """Fix Odoo 19 incompatibilities: <tree> → <list>, view_mode tree → list."""
        if not xml_str:
            return xml_str
        import re as _re
        xml_str = _re.sub(r'<tree(\s|>|/>)', r'<list\1', xml_str)
        xml_str = xml_str.replace('</tree>', '</list>')
        xml_str = _re.sub(
            r'(<field\s+name=["\']view_mode["\']\'?>)(.*?)(</field>)',
            lambda m: m.group(1) + m.group(2).replace('tree', 'list') + m.group(3),
            xml_str
        )
        xml_str = _re.sub(
            r'(<field\s+name=["\']name["\']\'?>)([^<]*?)\.tree([^<]*?)(</field>)',
            r'\1\2.list\3\4',
            xml_str
        )
        return xml_str

    @staticmethod
    def _escape(s):
        return (s or '').replace("'", "\\'").replace('\n', ' ')

    def _ensure_xml_wrapper(self, xml_str, noupdate: bool = False):
        """
        Ensure XML has <?xml?> + <odoo><data ...> wrapper.

        noupdate=True  → <data noupdate="1">  (models.xml — ir.model records)
        noupdate=False → <data noupdate="0">  (views, security, data files)

        CRITICAL: ir.model records MUST be noupdate="1" — if Odoo tries to
        re-process them on reinstall it raises XMLSyntaxError at line 5.
        """
        import re as _re
        xml_str = xml_str.strip()
        if not xml_str:
            return xml_str

        nu_attr = 'noupdate="1"' if noupdate else 'noupdate="0"'

        if not xml_str.startswith('<?xml') and not xml_str.startswith('<odoo'):
            # Bare records — wrap completely
            xml_str = f'<odoo><data {nu_attr}>\n{xml_str}\n</data></odoo>'
        elif xml_str.startswith('<odoo'):
            # Already has <odoo> — make sure correct <data ...> is present
            if '<data' not in xml_str:
                # <odoo>..records..</odoo> — inject <data noupdate> wrapper
                xml_str = _re.sub(
                    r'(<odoo[^>]*>)',
                    r'\1<data ' + nu_attr + '>',
                    xml_str, count=1
                )
                xml_str = xml_str.replace('</odoo>', '</data></odoo>', 1)
            elif noupdate:
                # Fix wrong noupdate value (0→1) for model files
                xml_str = xml_str.replace(
                    'noupdate="0"', 'noupdate="1"'
                ).replace("noupdate='0'", 'noupdate="1"')

        if not xml_str.startswith('<?xml'):
            xml_str = f'<?xml version="1.0" encoding="utf-8"?>\n{xml_str}'
        return xml_str

    def _sanitize_csv(self, csv_str):
        """Add missing header, strip blank lines."""
        lines = [l.strip() for l in csv_str.splitlines() if l.strip()]
        if lines and 'model_id' not in lines[0].lower():
            lines.insert(0,
                         'id,name,model_id:id,group_id:id,'
                         'perm_read,perm_write,perm_create,perm_unlink')
        return '\n'.join(lines) + '\n'

    def _extract_by_model(self, xml_str, model_name):
        """Extract <record model="model_name"> blocks from XML string."""
        import re as _re
        pattern = _re.compile(
            r'<record[^>]+model=["\']' + _re.escape(model_name) + r'["\'][^>]*>.*?</record>',
            _re.DOTALL
        )
        found = pattern.findall(xml_str)
        return '\n\n'.join(found) if found else ''

    def _extract_templates(self, xml_str):
        """
        Extract <template ...>...</template> blocks.
        Returns (templates_content, xml_without_templates).
        """
        import re as _re
        pattern = _re.compile(
            r'<template\b[^>]*>.*?</template>',
            _re.DOTALL
        )
        templates = pattern.findall(xml_str)
        clean = pattern.sub('', xml_str)
        return '\n\n'.join(templates), clean

    def _remove_models_from_xml(self, xml_str, model_names):
        """Remove <record model="X"> blocks for given model names."""
        import re as _re
        for model in model_names:
            pattern = _re.compile(
                r'<record[^>]+model=["\']' + _re.escape(model) + r'["\'][^>]*>.*?</record>',
                _re.DOTALL
            )
            xml_str = pattern.sub('', xml_str)
        return xml_str
