# -*- coding: utf-8 -*-
import base64
import logging
from odoo import models, fields, api
_logger = logging.getLogger(__name__)


class McpSnippet(models.Model):
    _name        = 'mcp.snippet'
    _description = 'MCP Website Snippet'
    _order       = 'write_date desc'
    _inherit     = ['mail.thread']

    name           = fields.Char(required=True, tracking=True)
    technical_name = fields.Char(required=True, index=True)
    description    = fields.Text()
    template_xml   = fields.Text(string='Snippet HTML')
    scss_code      = fields.Text(string='CSS')
    js_code        = fields.Text(string='JavaScript')
    thumbnail_svg  = fields.Text(string='Thumbnail SVG')
    state          = fields.Selection([
        ('draft', 'Draft'), ('installed', 'Installed'), ('error', 'Error'),
    ], default='draft', tracking=True)
    install_log         = fields.Text(readonly=True)
    active              = fields.Boolean(default=True)
    user_id             = fields.Many2one('res.users', default=lambda self: self.env.user)
    view_template_id    = fields.Many2one('ir.ui.view',    ondelete='set null')
    view_register_id    = fields.Many2one('ir.ui.view',    ondelete='set null')
    asset_css_id        = fields.Many2one('ir.asset',      ondelete='set null')
    asset_js_id         = fields.Many2one('ir.asset',      ondelete='set null')
    attachment_thumb_id = fields.Many2one('ir.attachment', ondelete='set null')
    snippet_class       = fields.Char(compute='_compute_snippet_class', store=True)
    thumb_url           = fields.Char(compute='_compute_thumb_url')

    @api.depends('technical_name')
    def _compute_snippet_class(self):
        for r in self:
            n = (r.technical_name or '').lower().replace(' ', '_').replace('-', '_')
            r.snippet_class = 's_' + n if not n.startswith('s_') else n

    @api.depends('attachment_thumb_id')
    def _compute_thumb_url(self):
        for r in self:
            r.thumb_url = (
                '/web/image/' + str(r.attachment_thumb_id.id)
                if r.attachment_thumb_id else ''
            )

    def action_install(self):
        self.ensure_one()

        # Read ALL values before try — if transaction aborts,
        # except block must not touch self.*
        name    = self.name or ''
        cls     = self.snippet_class or ''
        css     = (self.scss_code or '').strip()
        js      = (self.js_code or '').strip()
        svg     = (self.thumbnail_svg or '').strip()
        html    = (self.template_xml or '').strip()
        sid     = self.id
        o_tmpl  = self.view_template_id.id    if self.view_template_id    else None
        o_reg   = self.view_register_id.id    if self.view_register_id    else None
        o_css   = self.asset_css_id.id        if self.asset_css_id        else None
        o_js    = self.asset_js_id.id         if self.asset_js_id         else None
        o_thumb = self.attachment_thumb_id.id if self.attachment_thumb_id else None

        ok  = False
        msg = ''

        try:
            IrView       = self.env['ir.ui.view'].sudo()
            IrAsset      = self.env['ir.asset'].sudo()
            IrAttachment = self.env['ir.attachment'].sudo()

            # ── 1. Delete previously created records ──────────────────────────
            for model, rid in [
                ('ir.ui.view',    o_tmpl),
                ('ir.ui.view',    o_reg),
                ('ir.asset',      o_css),
                ('ir.asset',      o_js),
                ('ir.attachment', o_thumb),
            ]:
                if rid:
                    try:
                        self.env[model].sudo().browse(rid).unlink()
                    except Exception:
                        pass

            # ── 2. Thumbnail → ir.attachment ──────────────────────────────────
            thumb = IrAttachment.create({
                'name':      cls + '.svg',
                'datas':     base64.b64encode((svg or self._svg(cls, name)).encode()).decode(),
                'mimetype':  'image/svg+xml',
                'res_model': 'mcp.snippet',
                'res_id':    sid,
                'public':    True,
            })
            turl = '/web/image/' + str(thumb.id)

            # ── 3. QWeb template → ir.ui.view ─────────────────────────────────
            tkey  = 'mcp_snippet.' + cls
            inner = html or self._html(cls, name)
            vtmpl = IrView.create({
                'name':    name,
                'type':    'qweb',
                'key':     tkey,
                'arch_db': '<t t-name="' + tkey + '">' + inner + '</t>',
                'active':  True,
            })

            # ── 4. Register in Website Builder panel → ir.ui.view ────────────
            #
            # xpath: //snippets[@id='snippet_content']/*[1]  position="before"
            # SOURCE: Official Odoo 18/19 building_blocks documentation
            #   snippet_content always has Odoo's own snippets as children
            #   so /*[1] never fails.
            #
            vreg = IrView.create({
                'name':       name + ' registration',
                'type':       'qweb',
                'key':        tkey + '_reg',
                'inherit_id': self.env.ref('website.snippets').id,
                'arch_db': (
                    '<data>'
                    '<xpath expr="//snippets[@id=\'snippet_content\']/*[1]"'
                    ' position="before">'
                    '<t t-snippet="' + tkey + '"'
                    ' t-thumbnail="' + turl + '"'
                    ' string="' + self._esc(name) + '"/>'
                    '</xpath>'
                    '</data>'
                ),
                'active': True,
            })

            # ── 5. CSS → ir.asset ─────────────────────────────────────────────
            #
            # SOURCE: Official Odoo 19 documentation (data.html)
            #   <asset id="..."> <bundle>web.assets_frontend</bundle>
            #   <path>module/static/src/file.scss</path> </asset>
            #
            # Since we have no file on disk, we store CSS as an ir.attachment
            # (public) and point ir.asset at its /web/content/ URL.
            # ir.asset.path accepts URLs served by Odoo's own HTTP layer.
            #
            acss = None
            if css:
                css_attach = IrAttachment.create({
                    'name':      cls + '.css',
                    'datas':     base64.b64encode(css.encode()).decode(),
                    'mimetype':  'text/css',
                    'res_model': 'mcp.snippet',
                    'res_id':    sid,
                    'public':    True,
                })
                acss = IrAsset.create({
                    'name':      name + ' CSS',
                    'bundle':    'web.assets_frontend',
                    'path':      '/web/content/' + str(css_attach.id),
                    'directive': 'append',
                    'active':    True,
                })

            # ── 6. JS → ir.asset ──────────────────────────────────────────────
            ajs = None
            if js:
                js_attach = IrAttachment.create({
                    'name':      cls + '.js',
                    'datas':     base64.b64encode(js.encode()).decode(),
                    'mimetype':  'application/javascript',
                    'res_model': 'mcp.snippet',
                    'res_id':    sid,
                    'public':    True,
                })
                ajs = IrAsset.create({
                    'name':      name + ' JS',
                    'bundle':    'web.assets_frontend',
                    'path':      '/web/content/' + str(js_attach.id),
                    'directive': 'append',
                    'active':    True,
                })

            # ── 7. Clear frontend asset cache ─────────────────────────────────
            self.env['ir.attachment'].sudo().search([
                ('url', 'like', '/web/assets/'),
                ('name', 'like', 'assets_frontend'),
            ]).unlink()

            # ── 8. Save all record links ───────────────────────────────────────
            self.write({
                'view_template_id':    vtmpl.id,
                'view_register_id':    vreg.id,
                'attachment_thumb_id': thumb.id,
                'asset_css_id':        acss.id if acss else False,
                'asset_js_id':         ajs.id  if ajs  else False,
            })

            ok  = True
            msg = (
                'Installed: ' + name + '\n'
                'Hard-refresh (Ctrl+Shift+R) → Website → Edit → Blocks'
            )

        except Exception as e:
            _logger.error('mcp.snippet [%s]: %s', cls, e, exc_info=True)
            msg = 'Install failed: ' + str(e)

        self.write({'state': 'installed' if ok else 'error', 'install_log': msg})
        return True

    def action_uninstall(self):
        self.ensure_one()
        for fname, model in [
            ('view_template_id',    'ir.ui.view'),
            ('view_register_id',    'ir.ui.view'),
            ('asset_css_id',        'ir.asset'),
            ('asset_js_id',         'ir.asset'),
            ('attachment_thumb_id', 'ir.attachment'),
        ]:
            rec = self[fname]
            if rec:
                try:
                    rec.sudo().unlink()
                except Exception as e:
                    _logger.warning('uninstall %s %s: %s', model, rec.id, e)
        self.write({
            'state':               'draft',
            'view_template_id':    False,
            'view_register_id':    False,
            'asset_css_id':        False,
            'asset_js_id':         False,
            'attachment_thumb_id': False,
            'install_log':         'Uninstalled.',
        })

    @staticmethod
    def _esc(s):
        return (
            (s or '').replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')
        )

    @staticmethod
    def _html(cls, name):
        return (
            '<section class="' + cls + ' o_colored_level"'
            ' data-name="' + name + '" data-snippet="' + cls + '">'
            '<div class="container">'
            '<div class="row align-items-center py-5">'
            '<div class="col-lg-12 text-center">'
            '<h2 class="oe_editable">' + name + '</h2>'
            '<p class="lead oe_editable">Edit this text in the Website Builder.</p>'
            '<a href="#" class="btn btn-primary mt-3">Learn More</a>'
            '</div></div></div></section>'
        )

    @staticmethod
    def _svg(cls, name):
        label = (name or cls)[:18]
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 150">'
            '<rect width="200" height="150" fill="#0f172a" rx="8"/>'
            '<rect x="10" y="10" width="180" height="130" fill="#1e293b" rx="6"/>'
            '<rect x="30" y="35" width="140" height="14" fill="#38bdf8" rx="3"/>'
            '<rect x="50" y="60" width="100" height="8" fill="#475569" rx="2"/>'
            '<rect x="60" y="76" width="80" height="8" fill="#475569" rx="2"/>'
            '<rect x="70" y="98" width="60" height="20" fill="#0ea5e9" rx="4"/>'
            '<text x="100" y="113" text-anchor="middle" fill="#fff"'
            ' font-size="9" font-family="sans-serif">' + label + '</text>'
            '</svg>'
        )