# -*- coding: utf-8 -*-
# odoo_module.py — manage_module (final production version)
# Odoo 19 data module builder via base_import_module

import ast
import keyword
import logging
import re
import re as _re
import xml.etree.ElementTree as _ET
import re
import traceback as _tb

from .mcp_helpers import _sudo_env, _log

_logger = logging.getLogger(__name__)

_MOD_FIELDS = (
    'name', 'description', 'manifest_code', 'models_code', 'views_code',
    'security_code', 'data_files_code', 'demo_data_code', 'report_code',
    'js_code', 'scss_code', 'owl_code',
)


# ═══════════════════════════════════════════════════════════════════════════
# XML HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _wrap_xml(xml_str):
    """Wrap bare XML content in <odoo> for parsing."""
    xml_str = xml_str.strip()
    if xml_str.startswith('<?xml'):
        return xml_str
    if not xml_str.startswith('<odoo'):
        return f'<odoo>{xml_str}</odoo>'
    return xml_str


def _get_defined_ids(xml_str):
    """Return set of all record id= values defined in an XML string."""
    return set(_re.findall(r'<record\s+id=["\']([^"\']+)["\']', xml_str or ''))


# ═══════════════════════════════════════════════════════════════════════════
# AUTO-FIXERS  (applied automatically on save AND by action='fix')
# ═══════════════════════════════════════════════════════════════════════════

def _fix_wrong_closing_tags(code: str) -> str:
    """
    Fix LLM hallucination: </field_description> → </field>
    Every <field ...> must close with </field>, never </field_something>.
    """
    code = _re.sub(r'</field_[a-zA-Z_]+>', '</field>', code)
    code = _re.sub(r'</field[A-Z][a-zA-Z_]*>', '</field>', code)
    return code


def _fix_inline_selection(code: str) -> str:
    """
    Convert wrong selection 'key:Label,key2:Label2'
    → correct [('key','Label'),('key2','Label2')]
    Odoo 19 calls literal_eval() on this field — must be valid Python.
    """
    def fix(match):
        raw = match.group(1).strip()
        if raw.startswith('[') or raw.startswith('('):
            return match.group(0)
        try:
            pairs = []
            for item in raw.split(','):
                item = item.strip()
                if ':' not in item:
                    continue
                key, _, label = item.partition(':')
                pairs.append(f"('{key.strip()}', '{label.strip()}')")
            if pairs:
                return (
                    f'<field name="selection">'
                    f'[{", ".join(pairs)}]</field>'
                )
        except Exception:
            pass
        return match.group(0)

    return _re.sub(
        r'<field\s+name=["\']selection["\']>([^<]+)</field>',
        fix, code,
    )


def _fix_tree_to_list(code: str) -> str:
    """
    Replace <tree> with <list> throughout views_code.
    <tree> was removed in Odoo 19 — causes 'Invalid view type: tree'.
    """
    code = _re.sub(r'<tree(\s|>|/>)', r'<list\1', code)
    code = code.replace('</tree>', '</list>')
    code = _re.sub(
        r'(<field\s+name=["\']view_mode["\']>)([^<]+)(</field>)',
        lambda m: (
            m.group(1)
            + m.group(2).replace('tree', 'list')
            + m.group(3)
        ),
        code,
    )
    code = _re.sub(
        r'(<field\s+name=["\']name["\']>)([^<]+\.tree)([^<]*</field>)',
        lambda m: m.group(1) + m.group(2).replace('.tree', '.list') + m.group(3),
        code,
    )
    return code


def _fix_attrs_to_inline(code: str) -> str:
    """
    Replace deprecated attrs="{...}" with Odoo 17+ inline syntax.
    attrs removed since Odoo 17 — causes AttributeError on view load.
    Handles simple single-condition cases automatically.
    """
    def convert_attrs(match):
        attrs_str = match.group(1)
        result_parts = []
        try:
            parsed = ast.literal_eval(attrs_str)
            for prop in ('invisible', 'readonly', 'required', 'column_invisible'):
                if prop not in parsed:
                    continue
                domain = parsed[prop]
                if not isinstance(domain, list) or not domain:
                    continue
                if (len(domain) == 1
                        and isinstance(domain[0], (list, tuple))
                        and len(domain[0]) == 3):
                    field, op, val = domain[0]
                    val_repr = f"'{val}'" if isinstance(val, str) else str(val)
                    expr = f"{field} {op} {val_repr}"
                    result_parts.append(f'{prop}="{expr}"')
                else:
                    result_parts.append(
                        f'{prop}="True" '
                        f'<!-- TODO: complex attrs from {domain} -->'
                    )
        except Exception:
            result_parts.append('<!-- TODO: fix attrs manually -->')
        return ' '.join(result_parts) if result_parts else ''

    code = _re.sub(
        r'\battrs=["\'](\{[^"\']+\})["\']',
        convert_attrs, code,
    )
    code = _re.sub(r'\battrs=["\'][^"\']*["\']', '', code)
    return code


def _fix_states_attr(code: str) -> str:
    """Remove deprecated states='...' attribute (removed Odoo 17+)."""
    return _re.sub(r'\bstates=["\'][^"\']*["\']', '', code)


def _fix_object_buttons(code: str) -> str:
    """
    Replace type='object' with type='action'.
    type='object' crashes in data modules — no Python method to call.
    """
    return (
        code
        .replace("type='object'", "type='action'")
        .replace('type="object"', 'type="action"')
    )


def _fix_noupdate_in_views(code: str) -> str:
    """
    Remove noupdate='1' from views_code.
    Views should never have noupdate — it prevents updates on reinstall.
    """
    return code.replace('noupdate="1"', '').replace("noupdate='1'", '')


def _fix_missing_cdata(code: str) -> str:
    """
    Wrap Python code inside <field name='code'> with CDATA if missing.
    Without CDATA, characters like < > & crash the XML parser.
    """
    def wrap_cdata(match):
        inner = match.group(1).strip()
        if inner.startswith('<![CDATA['):
            return match.group(0)
        return f'<field name="code"><![CDATA[\n{inner}\n]]></field>'

    return _re.sub(
        r'<field\s+name=["\']code["\']>((?:(?!</field>).)+)</field>',
        wrap_cdata, code, flags=_re.DOTALL,
    )


def _fix_html_entities_in_domain(code: str) -> str:
    """
    Fix unescaped & in domain/filter attributes.
    Bare & in XML attributes must be &amp; for valid XML.
    """
    def fix_domain_attr(match):
        attr_name = match.group(1)
        value     = match.group(2)
        value = _re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)', '&amp;', value)
        return f'{attr_name}="{value}"'

    return _re.sub(
        r'(domain|filter_domain|help)="([^"]*)"',
        fix_domain_attr, code,
    )


def _fix_remove_invalid_view_modes(code: str) -> str:
    """
    Remove view_mode entries that have no matching view record.
    Prevents install crash when Odoo tries to render a missing view type.
    """
    invalid = []
    if 'calendar' in code and 'date_start=' not in code:
        invalid.append('calendar')
    if '<pivot' not in code and _re.search(r'view_mode["\']>[^<]*pivot', code):
        invalid.append('pivot')
    if '<graph' not in code and _re.search(r'view_mode["\']>[^<]*graph', code):
        invalid.append('graph')

    if not invalid:
        return code

    def clean_vm(match):
        modes   = [m.strip() for m in match.group(1).split(',')]
        cleaned = [m for m in modes if m not in invalid]
        if not cleaned:
            cleaned = ['list', 'form']
        return f'<field name="view_mode">{",".join(cleaned)}</field>'

    return _re.sub(
        r'<field\s+name=["\']view_mode["\']>([^<]+)</field>',
        clean_vm, code,
    )


def _fix_missing_state_manual(code: str) -> str:
    """
    Inject <field name='state'>manual</field> into every ir.model record
    that doesn't have one.  Without state=manual Odoo ignores the model.
    """
    def inject_state(match):
        block = match.group(0)
        if "name='state'" in block or 'name="state"' in block:
            return block
        # Insert right before </record>
        return block.replace(
            '</record>',
            '  <field name="state">manual</field>\n</record>',
            1,
        )

    return _re.sub(
        r'<record[^>]+model=["\']ir\.model["\'][^>]*>.*?</record>',
        inject_state, code, flags=_re.DOTALL,
    )


def _fix_ondelete_required_m2o(code: str) -> str:
    """
    Remove ALL <field name="ondelete">...</field> lines from ir.model.fields
    records.  ondelete is a Python-only ORM parameter — it is NOT a valid
    column in ir.model.fields and causes
    ``ValueError: Invalid field 'ondelete' in 'ir.model.fields'``
    when loaded via XML data files.

    Also strips required=True from relational fields (many2one/many2many)
    because no data exists during first install → NOT NULL constraint fails.
    """
    def fix_record(match):
        block = match.group(0)
        # Strip ALL ondelete lines unconditionally
        block = _re.sub(
            r'\s*<field\s+name=["\']on_?delete["\'][^>]*>.*?</field>',
            '', block, flags=_re.IGNORECASE | _re.DOTALL,
        )
        # Strip required=True from relational fields
        is_relational = bool(_re.search(
            r'<field\s+name=["\']ttype["\']>(?:many2one|many2many)</field>',
            block,
        ))
        if is_relational:
            block = _re.sub(
                r'\s*<field\s+name=["\']required["\']\s+eval=["\']True["\']\s*/?\>',
                '', block,
            )
        return block

    return _re.sub(
        r'<record[^>]+model=["\']ir\.model\.fields["\'][^>]*>.*?</record>',
        fix_record, code, flags=_re.DOTALL,
    )


def _fix_chatter_without_mail(code: str, has_mail_dep: bool) -> str:
    """
    Remove <div class="oe_chatter"> blocks from views_code when the module
    does NOT depend on 'mail'.  Data-only models don't inherit mail.thread,
    so chatter fields (message_follower_ids, activity_ids, message_ids) don't
    exist, causing a crash at view load.
    """
    if has_mail_dep:
        return code
    # Remove chatter blocks: <div class="oe_chatter">...</div>
    code = _re.sub(
        r'<div\s+class=["\']oe_chatter["\'][^>]*>.*?</div>',
        '<!-- chatter removed: module does not depend on mail -->',
        code, flags=_re.DOTALL,
    )
    # Also remove standalone chatter fields
    for fld in ('message_follower_ids', 'activity_ids', 'message_ids'):
        code = _re.sub(
            rf'<field\s+name=["\']' + fld + rf'["\'][^/]*/?>',
            '', code,
        )
    return code

def _fix_search_view_issues(views_code: str, models_code: str = '') -> str:
    """
    Fix Odoo 19 search view issues that cause install/load crashes:

    1. filter_domain= → domain=  (wrong attribute name)
    2. Remove non-relational fields from <searchpanel>
       Only many2one and selection are valid — char/text/integer/date crash with
       ValueError: Invalid field <name> for searchpanel element
    3. Remove group_by context entries for non-relational fields
       (not a crash but produces empty groups and console errors)
    4. Fix select= attribute values: must be 'one' or 'multi' (not True/False)
    """
    if not views_code:
        return views_code

    code = views_code

    # Fix 1: filter_domain → domain
    code = code.replace(' filter_domain=', ' domain=')
    code = code.replace('\tfilter_domain=', '\tdomain=')

    # Build field type map
    field_types = _get_field_types(models_code)
    VALID_SEARCHPANEL = {'many2one', 'selection'}
    NON_RELATIONAL    = {
        'char', 'text', 'html', 'integer', 'float', 'monetary',
        'boolean', 'date', 'datetime', 'binary',
    }

    # Fix 2: Remove invalid fields from <searchpanel> blocks
    def fix_searchpanel_block(match):
        panel = match.group(0)

        def check_field(field_match):
            fname = field_match.group(1)
            ftype = field_types.get(fname)

            if ftype and ftype in NON_RELATIONAL:
                return (
                    f'<!-- removed: field "{fname}" (type={ftype}) '
                    f'is not valid in searchpanel — '
                    f'only many2one and selection are supported -->'
                )

            # Also detect by naming: fields NOT ending in _id/_ids
            # and NOT named like x_state/x_status/x_type/x_gender/x_priority
            # are probably non-relational — warn but don't remove if type unknown
            if ftype is None:
                LIKELY_SELECTION = {
                    'x_state', 'x_status', 'x_type', 'x_gender',
                    'x_priority', 'x_stage', 'x_category', 'x_blood_group',
                    'x_level',
                }
                is_m2o      = fname.endswith('_id') or fname.endswith('_ids')
                is_sel_name = fname in LIKELY_SELECTION or fname.endswith('_type')
                if not is_m2o and not is_sel_name:
                    return (
                        f'<!-- WARNING: field "{fname}" may not be valid in searchpanel. '
                        f'Only many2one and selection fields are supported. -->'
                    )

            return field_match.group(0)

        panel = _re.sub(
            r'<field\s+name=["\']([^"\']+)["\'][^/]*/?>',
            check_field,
            panel,
        )
        return panel

    code = _re.sub(
        r'<searchpanel\b[^>]*>.*?</searchpanel>',
        fix_searchpanel_block,
        code,
        flags=_re.DOTALL,
    )

    # Fix 3: Remove group_by context filters for non-relational fields
    def fix_groupby_filter(match):
        filter_str = match.group(0)
        gm = _re.search(r"['\"]group_by['\"]\s*:\s*['\"]([^'\"]+)['\"]", filter_str)
        if not gm:
            return filter_str
        fname = gm.group(1)
        ftype = field_types.get(fname)
        if ftype and ftype in NON_RELATIONAL:
            return (
                f'<!-- removed group_by "{fname}" ({ftype}): '
                f'only many2one/selection fields are valid for group by -->'
            )
        return filter_str

    code = _re.sub(
        r"<filter\b[^>]+context=[\"'][^\"']*group_by[^\"']*[\"'][^/]*/?>",
        fix_groupby_filter,
        code,
    )

    # Fix 4: select="True"/"False" → select="one"/"multi"
    code = code.replace('select="True"',  'select="multi"')
    code = code.replace("select='True'",  "select='multi'")
    code = code.replace('select="False"', 'select="one"')
    code = code.replace("select='False'", "select='one'")

    return code

def _get_field_types(models_code: str) -> dict:
    """
    Build a map of {field_name: ttype} from models_code XML.
    Used to validate search view field restrictions.
    Returns e.g. {'x_name': 'char', 'x_doctor_id': 'many2one', 'x_state': 'selection'}
    """
    field_types = {}
    if not models_code:
        return field_types

    for match in _re.finditer(
        r'<record[^>]+model=["\']ir\.model\.fields["\'][^>]*>(.*?)</record>',
        models_code, flags=_re.DOTALL,
    ):
        block  = match.group(1)
        name_m = _re.search(r'<field\s+name=["\']name["\']>([^<]+)</field>', block)
        type_m = _re.search(r'<field\s+name=["\']ttype["\']>([^<]+)</field>', block)
        if name_m and type_m:
            field_types[name_m.group(1).strip()] = type_m.group(1).strip()

    return field_types

def _extract_model_record_ids(models_code: str) -> dict:
    """
    INDUSTRIAL helper: extract ALL ir.model record IDs from models_code XML.

    Uses 3 independent regex strategies to handle every possible XML
    attribute ordering that LLMs and Odoo tooling produce.

    Returns: dict of {record_id: model_technical_name}
    """
    valid_model_ids = {}

    # Strategy A: id="X" BEFORE model="ir.model" in the opening tag
    for m in _re.finditer(
        r'<record[^>]+id=["\']([^"\']+)["\'][^>]+model=["\']ir\.model["\'][^>]*>'
        r'.*?<field\s+name=["\']model["\']>([^<]+)</field>',
        models_code, flags=_re.DOTALL,
    ):
        valid_model_ids[m.group(1).strip()] = m.group(2).strip()

    # Strategy B: model="ir.model" BEFORE id="X" in the opening tag
    for m in _re.finditer(
        r'<record[^>]+model=["\']ir\.model["\'][^>]+id=["\']([^"\']+)["\'][^>]*>'
        r'.*?<field\s+name=["\']model["\']>([^<]+)</field>',
        models_code, flags=_re.DOTALL,
    ):
        valid_model_ids[m.group(1).strip()] = m.group(2).strip()

    # Strategy C: scan record blocks by finding model field first,
    # then look backward for the record id — catches wrapped/indented XML
    for m in _re.finditer(
        r'<field\s+name=["\']model["\']>(x_[^<\s]+)</field>',
        models_code,
    ):
        model_name  = m.group(1).strip()
        search_back = models_code[:m.start()]
        # Find the nearest <record ... > opening before this field
        rec_m = None
        for rm in _re.finditer(r'<record\s[^>]*>', search_back):
            rec_m = rm  # keep the last (closest) match
        if rec_m:
            id_m = _re.search(r'id=["\']([^"\']+)["\']', rec_m.group(0))
            mod_m = _re.search(r'model=["\']ir\.model["\']', rec_m.group(0))
            if id_m and mod_m:
                valid_model_ids[id_m.group(1).strip()] = model_name

    return valid_model_ids


def _build_correction_map(valid_model_ids: dict) -> dict:
    """
    Build a comprehensive correction map from valid_model_ids.
    Covers every naming variant an LLM might generate for a model record ref.
    """
    corrections = {}
    for record_id, model_name in valid_model_ids.items():
        # Already correct
        corrections[record_id] = record_id

        # Standard: model_x_foo_bar
        plain = 'model_' + model_name.replace('.', '_')
        corrections[plain] = record_id

        if model_name.startswith('x_'):
            no_x = model_name[2:]
            # Without x_ prefix: model_foo_bar
            corrections['model_' + no_x.replace('.', '_')] = record_id
            # Compressed no underscores: model_foobar
            corrections['model_' + no_x.replace('_', '')] = record_id
            # Just the name: model_foo (short names)
            corrections['model_' + no_x] = record_id
            # With double underscore: model_x__foo
            corrections['model_x__' + no_x] = record_id

        # CamelCase variants some LLMs generate
        parts = model_name.lstrip('x_').split('_')
        if parts:
            camel = ''.join(p.title() for p in parts if p)
            corrections[f'model_{camel}']   = record_id
            corrections[f'model_x{camel}']  = record_id
            corrections[f'model_X{camel}']  = record_id

        # Handle dotted names: x_home.room → model_x_home_room
        if '.' in model_name:
            corrections['model_' + model_name.replace('.', '_')] = record_id

    return corrections


def _fix_security_csv_model_refs(csv_str: str, models_code: str) -> str:
    """
    INDUSTRIAL REWRITE — Fix security CSV model_id:id references.

    Uses _extract_model_record_ids (3 strategies) + _build_correction_map
    (10+ naming variants) + fuzzy fallback match.

    Guarantees: NEVER returns a CSV with broken model refs when models_code
    has valid ir.model records. Falls back to full regeneration if needed.
    """
    if not csv_str or not models_code:
        return csv_str

    valid_model_ids = _extract_model_record_ids(models_code)
    if not valid_model_ids:
        return csv_str

    corrections = _build_correction_map(valid_model_ids)

    # ── Stage 1: In-place correction with fuzzy fallback ──────────────
    lines  = csv_str.splitlines()
    header = lines[0] if lines else ''
    result = [header]
    has_unresolved = False

    for line in lines[1:]:
        if not line.strip() or line.strip().startswith('#'):
            result.append(line)
            continue

        cols = line.split(',')
        if len(cols) >= 3:
            ref = cols[2].strip()

            if ref in corrections:
                if corrections[ref] != ref:
                    _logger.info(
                        "mcp_module: correcting CSV ref '%s' → '%s'",
                        ref, corrections[ref],
                    )
                    cols[2] = corrections[ref]
            elif ref not in valid_model_ids:
                # Fuzzy fallback: find model whose technical name is contained
                # in the ref or vice versa
                found = False
                ref_lower = ref.lower().replace('model_', '').replace('x_', '').replace('_', '')
                for rec_id, mod_name in valid_model_ids.items():
                    mod_lower = mod_name.lower().replace('x_', '').replace('_', '').replace('.', '')
                    if ref_lower == mod_lower or ref_lower in mod_lower or mod_lower in ref_lower:
                        _logger.info(
                            "mcp_module: fuzzy-matched CSV ref '%s' → '%s' (model=%s)",
                            ref, rec_id, mod_name,
                        )
                        cols[2] = rec_id
                        found = True
                        break
                if not found:
                    has_unresolved = True

            line = ','.join(cols)
        result.append(line)

    if not has_unresolved:
        return '\n'.join(result)

    # ── Stage 2: Full regeneration — guaranteed correct ────────────────
    _logger.warning(
        "mcp_module: security CSV has unresolved refs — "
        "regenerating from %d models in models_code.",
        len(valid_model_ids),
    )
    new_lines = [
        'id,name,model_id:id,group_id:id,'
        'perm_read,perm_write,perm_create,perm_unlink'
    ]
    for record_id, model_name in valid_model_ids.items():
        safe = model_name.replace('.', '_')
        new_lines.append(
            f'access_{safe},access_{safe},'
            f'{record_id},base.group_user,1,1,1,1'
        )
    return '\n'.join(new_lines)


def _auto_generate_security_csv(models_code: str) -> str:
    """
    Auto-generate a complete security CSV from models_code when security_code
    is missing entirely. Prevents AccessError when users open the module.

    Returns complete CSV string or empty string if no models found.
    """
    model_records = _extract_model_record_ids(models_code)
    if not model_records:
        return ''

    lines = [
        'id,name,model_id:id,group_id:id,'
        'perm_read,perm_write,perm_create,perm_unlink'
    ]
    for record_id, model_name in model_records.items():
        safe = model_name.replace('.', '_')
        lines.append(
            f'access_{safe},access_{safe},'
            f'{record_id},base.group_user,1,1,1,1'
        )
    return '\n'.join(lines) + '\n'


def _auto_generate_security_xml(models_code: str) -> str:
    """
    Auto-generate XML access rights from models_code.  Uses <record> + ref()
    instead of CSV model_id:id — refs resolve in the same XML transaction,
    avoiding 'unknown model' errors during base_import_module install.
    """
    model_records = _extract_model_record_ids(models_code)
    if not model_records:
        return ''

    lines = ['<odoo><data noupdate="0">']
    for record_id, model_name in model_records.items():
        safe = model_name.replace('.', '_')
        lines += [
            '',
            f'  <record id="access_{safe}" model="ir.model.access">',
            f'    <field name="name">{model_name} access</field>',
            f'    <field name="model_id" ref="{record_id}"/>',
            f'    <field name="group_id" eval="False"/>',
            f'    <field name="perm_read" eval="1"/>',
            f'    <field name="perm_write" eval="1"/>',
            f'    <field name="perm_create" eval="1"/>',
            f'    <field name="perm_unlink" eval="1"/>',
            f'  </record>',
        ]
    lines += ['', '</data></odoo>']
    return '\n'.join(lines)


def _pre_install_cross_validate(models_code: str, security_code: str) -> tuple:
    """
    INDUSTRIAL PRE-INSTALL VALIDATOR — final safety net before ZIP build.

    Cross-validates every security CSV model_id:id ref against the ACTUAL
    ir.model record IDs in models_code. Called right before writing the CSV
    into the ZIP so Odoo never sees a broken reference.

    Returns:
        (is_valid: bool, fixed_csv: str, error_report: str)
    """
    if not models_code or not security_code:
        return True, security_code or '', ''

    actual_ids = _extract_model_record_ids(models_code)
    if not actual_ids:
        return True, security_code, ''

    lines = security_code.strip().splitlines()
    broken = []
    for i, line in enumerate(lines[1:], 2):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        cols = line.split(',')
        if len(cols) >= 3:
            ref = cols[2].strip()
            if ref and ref not in actual_ids:
                broken.append((i, ref))

    if not broken:
        return True, security_code, ''

    # Auto-fix via regeneration
    error_lines = [f"  Line {i}: '{r}' not in models_code" for i, r in broken]
    error_report = (
        f"Security CSV: {len(broken)} broken ref(s):\n"
        + '\n'.join(error_lines)
        + f'\nAuto-regenerated from {len(actual_ids)} model(s).'
    )

    new_lines = [
        'id,name,model_id:id,group_id:id,'
        'perm_read,perm_write,perm_create,perm_unlink'
    ]
    for record_id, model_name in actual_ids.items():
        safe = model_name.replace('.', '_')
        new_lines.append(
            f'access_{safe},access_{safe},'
            f'{record_id},base.group_user,1,1,1,1'
        )
    return False, '\n'.join(new_lines), error_report



def _fix_add_depends(manifest: str, dep: str) -> str:
    """Add a dependency to manifest depends list if not already present."""
    if f"'{dep}'" in manifest or f'"{dep}"' in manifest:
        return manifest
    patched = _re.sub(
        r"('depends'\s*:\s*\[)",
        f"\\1'{dep}', ",
        manifest, count=1,
    )
    if patched == manifest:
        patched = _re.sub(
            r'("depends"\s*:\s*\[)',
            f'\\1"{dep}", ',
            manifest, count=1,
        )
    return patched


# ═══════════════════════════════════════════════════════════════════════════
# MASTER AUTO-FIX — runs all fixers in the correct order
# ═══════════════════════════════════════════════════════════════════════════

def _apply_all_fixes(mod) -> list:
    """
    Apply every auto-fixer to the module record.
    Returns list of human-readable descriptions of fixes applied.
    Called by action='fix' and automatically on create/update.
    """
    applied = []

    # ── models_code ───────────────────────────────────────────────────────
    if mod.models_code:
        mc = mod.models_code

        f = _fix_wrong_closing_tags(mc)
        if f != mc:
            mc = f
            applied.append(
                "Fixed wrong XML closing tags "
                "(e.g. </field_description> → </field>)."
            )

        f = _fix_inline_selection(mc)
        if f != mc:
            mc = f
            applied.append(
                "Fixed inline selection format "
                "(key:Label → [('key','Label')])."
            )

        f = _fix_missing_cdata(mc)
        if f != mc:
            mc = f
            applied.append("Wrapped Python code blocks in CDATA in models_code.")

        f = _fix_missing_state_manual(mc)
        if f != mc:
            mc = f
            applied.append(
                "Injected state='manual' into ir.model records. "
                "Without state=manual, Odoo ignores data-only models."
            )

        f = _fix_ondelete_required_m2o(mc)
        if f != mc:
            mc = f
            applied.append(
                "Removed ondelete='set null' from required Many2one fields. "
                "PostgreSQL rejects NOT NULL + set null together."
            )

        if mc != mod.models_code:
            mod.write({'models_code': mc})

    # Fix: noupdate="0" → noupdate="1" in models_code
    if mod.models_code:
        mc = mod.models_code
        if 'noupdate="0"' in mc or "noupdate='0'" in mc:
            fixed = mc.replace('noupdate="0"', 'noupdate="1"').replace(
                "noupdate='0'", "noupdate='1'"
            )
            mod.write({'models_code': fixed})
            mc = fixed
            applied.append(
                "Changed noupdate='0' → noupdate='1' in models_code. "
                "Model definitions must use noupdate='1'."
            )

    # Fix: remove duplicate inline selection= when ir.model.fields.selection
    # records also exist — using BOTH causes ParseError
    if mod.models_code:
        mc = mod.models_code
        has_sel_records = 'ir.model.fields.selection' in mc
        has_inline_sel = bool(_re.search(
            r'<field\s+name=["\']selection["\']>[^<\[]+</field>', mc
        ))
        if has_sel_records and has_inline_sel:
            def remove_inline_sel(match):
                block = match.group(0)
                # Only remove selection= if this field block has NO Python list format
                # i.e. it is the wrong format alongside separate records
                cleaned = _re.sub(
                    r'\s*<field\s+name=["\']selection["\']>'
                    r'(?!\s*\[)[^<]*</field>',
                    '', block,
                )
                return cleaned

            fixed = _re.sub(
                r'<record[^>]+model=["\']ir\.model\.fields["\'][^>]*>'
                r'.*?</record>',
                remove_inline_sel, mc, flags=_re.DOTALL,
            )
            if fixed != mc:
                mod.write({'models_code': fixed})
                applied.append(
                    "Removed duplicate inline selection= attribute. "
                    "ir.model.fields.selection records are already defined — "
                    "using both causes ParseError."
                )

    # ── views_code ────────────────────────────────────────────────────────
    if mod.views_code:
        vc = mod.views_code

        f = _fix_wrong_closing_tags(vc)
        if f != vc:
            vc = f
            applied.append("Fixed wrong XML closing tags in views_code.")

        f = _fix_tree_to_list(vc)
        if f != vc:
            vc = f
            applied.append("Replaced <tree> with <list> in views_code.")

        f = _fix_attrs_to_inline(vc)
        if f != vc:
            vc = f
            applied.append(
                "Converted deprecated attrs='{...}' to inline "
                "invisible/readonly/required."
            )

        f = _fix_states_attr(vc)
        if f != vc:
            vc = f
            applied.append("Removed deprecated states= attribute.")

        f = _fix_object_buttons(vc)
        if f != vc:
            vc = f
            applied.append(
                "Changed type='object' buttons to type='action'. "
                "Ensure matching ir.actions.server records exist."
            )

        f = _fix_noupdate_in_views(vc)
        if f != vc:
            vc = f
            applied.append("Removed noupdate='1' from views_code.")

        # NOTE: _fix_missing_cdata is intentionally NOT applied to views_code.
        # View arch XML and ir.ui.menu/ir.actions records must NOT be CDATA-wrapped.
        # If OWL/JSX code needs CDATA, it only applies to ir.actions.server
        # <field name="code"> blocks inside models_code, handled above.

        f = _fix_html_entities_in_domain(vc)
        if f != vc:
            vc = f
            applied.append("Fixed unescaped & in domain attributes.")

        f = _fix_remove_invalid_view_modes(vc)
        if f != vc:
            vc = f
            applied.append(
                "Removed view_mode entries without matching view records "
                "(calendar/pivot/graph)."
            )

        if mod.views_code:
            vc = mod.views_code
            f = _fix_search_view_issues(vc, mod.models_code or '')
            if f != vc:
                vc = f
                applied.append(
                    "Fixed search view issues: removed non-relational fields from "
                    "<searchpanel> (only many2one/selection valid), "
                    "fixed filter_domain → domain, fixed select= values."
                )
            if vc != mod.views_code:
                mod.write({'views_code': vc})

        if vc != mod.views_code:
            mod.write({'views_code': vc})

    # ── chatter without mail dependency ────────────────────────────────
    # Must run AFTER views_code fixes above and AFTER manifest
    # Check if module has mail dependency
    all_code = (mod.views_code or '') + (mod.models_code or '') + (mod.manifest_code or '')
    has_mail = (
        "'mail'" in all_code or
        '"mail"' in all_code
    )
    if mod.views_code:
        vc = mod.views_code
        f = _fix_chatter_without_mail(vc, has_mail)
        if f != vc:
            mod.write({'views_code': f})
            applied.append(
                "Removed chatter blocks (oe_chatter, message_follower_ids, etc.) "
                "from views. Data-only models don't inherit mail.thread — "
                "chatter fields don't exist without 'mail' dependency."
            )

    # ── security_code model refs — ALWAYS runs if models exist ───────────
    # INDUSTRIAL FIX: Run even when security_code is present AND fix or
    # auto-generate when it is missing entirely.
    if mod.models_code:
        if mod.security_code:
            sc = mod.security_code
            f  = _fix_security_csv_model_refs(sc, mod.models_code)
            if f != sc:
                mod.write({'security_code': f})
                applied.append(
                    "Fixed security CSV model_id:id references to match "
                    "actual ir.model record IDs from models_code."
                )
        else:
            # No security CSV at all — auto-generate from models_code
            auto_csv = _auto_generate_security_csv(mod.models_code)
            if auto_csv:
                mod.write({'security_code': auto_csv})
                applied.append(
                    "Auto-generated security CSV from models_code. "
                    "Without this users would get AccessError when opening the module."
                )

    # ── manifest_code ─────────────────────────────────────────────────────
    if mod.manifest_code:
        mf  = mod.manifest_code
        vc  = mod.views_code or ''
        mc2 = mod.models_code or ''

        needs_auto = (
            'base.automation' in vc or
            'ir.actions.server' in vc or
            'ir.cron' in vc or
            'ir.cron' in mc2
        )
        needs_mail = (
            '<chatter' in vc or
            'mail.template' in vc or
            'message_post' in vc
        )

        if needs_auto:
            f = _fix_add_depends(mf, 'base_automation')
            if f != mf:
                mf = f
                applied.append("Added 'base_automation' to manifest depends.")

        if needs_mail:
            f = _fix_add_depends(mf, 'mail')
            if f != mf:
                mf = f
                applied.append("Added 'mail' to manifest depends.")

        if mf != mod.manifest_code:
            mod.write({'manifest_code': mf})

    return applied


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATE — comprehensive Odoo 19 checks
# ═══════════════════════════════════════════════════════════════════════════

def _validate_module_code(mod):
    """
    Validate all code fields before install.
    Returns list of issue strings.
    ERROR: prefix = blocks install.
    WARNING: prefix = advisory only.
    """
    issues     = []
    models_ids = _get_defined_ids(mod.models_code or '')
    views_ids = _get_defined_ids(mod.views_code or '')
    report_ids = _get_defined_ids(mod.report_code or '')
    data_ids = _get_defined_ids(mod.data_files_code or '')
    all_ids = models_ids | views_ids | report_ids | data_ids  # was: models_ids | views_ids only

    # ═════════════════════════════════════════════════════════════════════
    # MODELS_CODE
    # ═════════════════════════════════════════════════════════════════════
    if mod.models_code and mod.models_code.strip():
        mc = mod.models_code.strip()

        # Python class check — must be first, all other checks are XML-specific
        if _re.search(r'\bclass\s+\w+\s*\(', mc) or 'from odoo import' in mc:
            issues.append(
                "ERROR: models_code contains Python class code. "
                "base_import_module never executes Python files — "
                "it only reads XML/CSV from the 'data' list. "
                "Replace the Python class with ir.model + ir.model.fields XML records. "
                "See the module creation prompt for examples."
            )

        # 1. Wrong closing tags  </field_description>
        wrong_tags = _re.findall(r'</field_[a-zA-Z_]+>', mc)
        wrong_tags += _re.findall(r'</field[A-Z][a-zA-Z_]*>', mc)
        if wrong_tags:
            issues.append(
                f"ERROR: Wrong XML closing tags in models_code: "
                f"{list(set(wrong_tags))[:5]}. "
                f"ALL <field> records close with </field> — never "
                f"</field_description> or </field_ttype>. "
                f"Call action='fix' to auto-correct."
            )

        # 2. Python class definition — wrong for data modules
        if 'class ' in mc and 'models.Model' in mc:
            issues.append(
                "ERROR: models_code contains a Python class. "
                "Data modules use ir.model XML records only — no Python. "
                "Replace 'class X(models.Model):' with "
                "<record model='ir.model'>."
            )

        # 3. Wrong selection format
        for bad in _re.findall(
            r'<field\s+name=["\']selection["\']>([^<\[]+)</field>', mc
        ):
            if ':' in bad and not bad.strip().startswith('['):
                issues.append(
                    f"ERROR: Wrong selection '{bad.strip()}'. "
                    f"Must be Python list: [('key','Label'),...]. "
                    f"Call action='fix' to auto-correct."
                )

        has_sel_records = 'ir.model.fields.selection' in mc
        has_inline_sel = bool(_re.search(
            r'<field\s+name=["\']selection["\']>[^<\[]+</field>', mc
        ))
        if has_sel_records and has_inline_sel:
            issues.append(
                "ERROR: models_code uses BOTH inline selection= attribute AND "
                "ir.model.fields.selection records. "
                "Use ONE approach only — never both. "
                "Official Odoo 19 approach: no selection= on the field record, "
                "use separate ir.model.fields.selection records only. "
                "Call action='fix' to auto-remove the duplicate."
            )

        # 3c. noupdate must be '1' in models_code
        if 'noupdate="0"' in mc or "noupdate='0'" in mc:
            issues.append(
                "ERROR: models_code has noupdate='0'. "
                "Must be noupdate='1' — Odoo tries to UPDATE selection records "
                "on reinstall when noupdate='0' which causes ParseError. "
                "Call action='fix' to auto-correct."
            )

        # 4. Missing CDATA on code fields
        for cf in _re.findall(
            r'<field\s+name=["\']code["\']>((?:(?!</field>).)+)</field>',
            mc, flags=_re.DOTALL,
        ):
            if '<![CDATA[' not in cf:
                issues.append(
                    "ERROR: Python code in models_code <field name='code'> "
                    "not wrapped in <![CDATA[ ... ]]>. "
                    "Call action='fix' to auto-wrap."
                )
                break

        # 5. Missing state='manual' on ir.model records
        for rec in _re.findall(
            r'<record[^>]+model=["\']ir\.model["\'][^>]*>(.*?)</record>',
            mc, flags=_re.DOTALL,
        ):
            if 'state' not in rec or 'manual' not in rec:
                m = _re.search(
                    r'<field\s+name=["\']model["\']>([^<]+)</field>', rec
                )
                name = m.group(1) if m else '?'
                issues.append(
                    f"ERROR: ir.model record '{name}' missing "
                    f"<field name='state'>manual</field>. "
                    f"Without state=manual Odoo ignores the model."
                )

        # 6. Custom model names must start with x_
        for mn in _re.findall(
            r'<field\s+name=["\']model["\']>([^<]+)</field>', mc
        ):
            mn = mn.strip()
            if mn and not mn.startswith('x_') and '.' not in mn:
                issues.append(
                    f"ERROR: Custom model '{mn}' must start with x_. "
                    f"Odoo reserves non-prefixed names for official modules."
                )

        # 7. Custom field names must start with x_
        for fn in _re.findall(
            r'<record[^>]+model=["\']ir\.model\.fields["\'][^>]*>'
            r'.*?<field\s+name=["\']name["\']>([^<]+)</field>',
            mc, flags=_re.DOTALL,
        ):
            fn = fn.strip()
            _BUILTIN = {'id', 'name', 'display_name', 'create_date',
                        'write_date', 'create_uid', 'write_uid',
                        '__last_update', 'active'}
            if fn and not fn.startswith('x_') and fn not in _BUILTIN:
                issues.append(
                    f"ERROR: Field name '{fn}' must start with x_. "
                    f"Custom fields require x_ prefix."
                )

        # 8. XML parse — catches remaining syntax errors
        try:
            _ET.fromstring(_wrap_xml(mc))
        except _ET.ParseError as e:
            issues.append(
                f"ERROR: models_code XML parse error: {e}. "
                f"Common causes: wrong closing tags, unescaped &, "
                f"missing quotes, unclosed elements. "
                f"Call action='fix' to auto-correct common issues."
            )

    # ═════════════════════════════════════════════════════════════════════
    # VIEWS_CODE
    # ═════════════════════════════════════════════════════════════════════
    if mod.views_code and mod.views_code.strip():
        vc = mod.views_code.strip()

        # 1. Wrong closing tags
        wrong_tags_v = _re.findall(r'</field_[a-zA-Z_]+>', vc)
        wrong_tags_v += _re.findall(r'</field[A-Z][a-zA-Z_]*>', vc)
        if wrong_tags_v:
            issues.append(
                f"ERROR: Wrong XML closing tags in views_code: "
                f"{list(set(wrong_tags_v))[:5]}. "
                f"Call action='fix' to auto-correct."
            )

        # 2. <tree> removed in Odoo 19
        if '<tree' in vc or '</tree>' in vc:
            issues.append(
                "ERROR: <tree> removed in Odoo 19. "
                "Use <list> instead. "
                "Call action='fix' to auto-replace."
            )

        # 3. type='object' buttons
        obj_btns = _re.findall(
            r'<button[^>]+type=["\']object["\'][^>]*/?>',
            vc
        )
        if obj_btns:
            names = _re.findall(
                r'name=["\']([^"\']+)["\']', ' '.join(obj_btns)
            )
            issues.append(
                f"ERROR: type='object' buttons: {names}. "
                f"Data modules have no Python methods. "
                f"Use type='action' name='%(action_server_id)d'. "
                f"Call action='fix' to auto-convert."
            )

        # 4. attrs= removed Odoo 17+
        if ' attrs=' in vc:
            count = len(_re.findall(r'\battrs=', vc))
            issues.append(
                f"ERROR: 'attrs' attribute ({count} occurrence(s)) "
                f"removed since Odoo 17. "
                f"Use invisible=\"field == 'value'\" directly. "
                f"Call action='fix' to auto-convert simple cases."
            )

        # 5. states= removed Odoo 17+
        if ' states=' in vc:
            issues.append(
                "ERROR: 'states' attribute removed since Odoo 17. "
                "Use invisible=\"x_state not in ('a','b')\" instead. "
                "Call action='fix' to auto-remove."
            )

        # 6. view_mode vs actual view records
        for vm_str in _re.findall(
            r'<field\s+name=["\']view_mode["\']>([^<]+)</field>', vc
        ):
            for mode in [m.strip() for m in vm_str.split(',')]:
                if mode == 'calendar':
                    if 'date_start=' not in vc:
                        issues.append(
                            "ERROR: view_mode has 'calendar' but no "
                            "<calendar date_start='x_field'> view record. "
                            "Add the calendar view record or remove 'calendar'. "
                            "Call action='fix' to auto-remove."
                        )
                elif mode == 'pivot':
                    if '<pivot' not in vc:
                        issues.append(
                            "ERROR: view_mode has 'pivot' but no <pivot> record. "
                            "Add a pivot view record or remove 'pivot'. "
                            "Call action='fix' to auto-remove."
                        )
                elif mode == 'graph':
                    if '<graph' not in vc:
                        issues.append(
                            "ERROR: view_mode has 'graph' but no <graph> record. "
                            "Add a graph view record or remove 'graph'. "
                            "Call action='fix' to auto-remove."
                        )
                elif mode == 'activity':
                    if '<activity' not in vc:
                        issues.append(
                            "WARNING: view_mode has 'activity' but no "
                            "activity view record. Requires mail module."
                        )
                elif mode not in ('list', 'form', 'kanban', 'search',
                                  'calendar', 'pivot', 'graph', 'activity',
                                  'map', 'cohort', 'gantt'):
                    issues.append(
                        f"WARNING: Unknown view_mode value '{mode}'. "
                        f"Valid: list, form, kanban, search, calendar, "
                        f"pivot, graph, activity."
                    )

        # 7. Button %(ref)d → ir.actions.server must exist
        for ref in _re.findall(r'name=["\']%\(([^)]+)\)d["\']', vc):
            if ref not in all_ids:
                issues.append(
                    f"ERROR: Button references '%(${ref})d' but no record "
                    f"id='{ref}' found in models_code or views_code. "
                    f"Add <record id='{ref}' model='ir.actions.server'>."
                )

        # 8. ref= values must exist
        for ref in _re.findall(r'\bref=["\']([^"\']+)["\']', vc):
            if '.' in ref:
                continue  # cross-module ref — OK
            if ref not in all_ids:
                issues.append(
                    f"ERROR: ref='{ref}' in views_code not found as a "
                    f"record id in models_code or views_code."
                )

        # 9. ir.ui.view records must have arch
        for vr in _re.findall(
            r'<record[^>]+model=["\']ir\.ui\.view["\'][^>]*>(.*?)</record>',
            vc, flags=_re.DOTALL,
        ):
            if 'arch' not in vr:
                issues.append(
                    "ERROR: An ir.ui.view record is missing "
                    "<field name='arch' type='xml'>. "
                    "Every view record requires an arch field."
                )
                break

        # 10. act_window without view records
        act_models = _re.findall(
            r'<record[^>]+model=["\']ir\.actions\.act_window["\'][^>]*>'
            r'.*?<field\s+name=["\']res_model["\']>([^<]+)</field>',
            vc, flags=_re.DOTALL,
        )
        view_models = _re.findall(
            r'<record[^>]+model=["\']ir\.ui\.view["\'][^>]*>'
            r'.*?<field\s+name=["\']model["\']>([^<]+)</field>',
            vc, flags=_re.DOTALL,
        )
        for am in act_models:
            am = am.strip()
            if am not in [v.strip() for v in view_models]:
                issues.append(
                    f"WARNING: act_window for model '{am}' exists but "
                    f"no ir.ui.view records found for that model in views_code. "
                    f"Add at least list and form view records."
                )

        # 11. Missing CDATA on code fields
        # NOTE: views_code CDATA check removed — ir.actions.server code fields
        # with Python should be placed in models_code, not views_code.
        # The auto-fixer no longer applies CDATA to views_code to avoid
        # wrapping view arch content as text nodes.

        # 12. noupdate in views
        if 'noupdate="1"' in vc or "noupdate='1'" in vc:
            issues.append(
                "WARNING: noupdate='1' in views_code. "
                "Views should never use noupdate — it prevents updates. "
                "Call action='fix' to auto-remove."
            )

        # 13. XML parse
        try:
            _ET.fromstring(_wrap_xml(vc))
        except _ET.ParseError as e:
            issues.append(
                f"ERROR: views_code XML parse error: {e}. "
                f"Common causes: wrong closing tags, unescaped &, "
                f"unclosed elements, Python code outside CDATA. "
                f"Call action='fix' to auto-correct common issues."
            )

        # 14. searchpanel field type validation
        # Odoo 19: only many2one and selection fields are valid in searchpanel
        field_types = _get_field_types(mod.models_code or '')
        NON_RELATIONAL = {
            'char', 'text', 'html', 'integer', 'float', 'monetary',
            'boolean', 'date', 'datetime', 'binary',
        }
        for panel_match in _re.finditer(
                r'<searchpanel\b[^>]*>(.*?)</searchpanel>', vc, flags=_re.DOTALL
        ):
            panel = panel_match.group(1)
            for field_match in _re.finditer(
                    r'<field\s+name=["\']([^"\']+)["\']', panel
            ):
                fname = field_match.group(1)
                ftype = field_types.get(fname)
                if ftype and ftype in NON_RELATIONAL:
                    issues.append(
                        f"ERROR: <searchpanel> field '{fname}' has type '{ftype}'. "
                        f"searchpanel only supports many2one and selection. "
                        f"Remove '{fname}' or change it to a many2one/selection field. "
                        f"Call action='fix' to auto-remove."
                    )

        # 15. group_by non-relational field warning
        for gm in _re.finditer(
                r"context=[\"'][^\"']*'group_by'\s*:\s*'([^']+)'[^\"']*[\"']", vc
        ):
            fname = gm.group(1)
            ftype = field_types.get(fname)
            if ftype and ftype in NON_RELATIONAL:
                issues.append(
                    f"WARNING: group_by field '{fname}' has type '{ftype}'. "
                    f"Group By should only use many2one or selection fields. "
                    f"Call action='fix' to auto-remove."
                )

    # ═════════════════════════════════════════════════════════════════════
    # SECURITY_CODE
    # ═════════════════════════════════════════════════════════════════════
    if mod.security_code and mod.security_code.strip():
        sc    = mod.security_code.strip()
        # XML security format — no CSV validation needed
        if not sc.lstrip().startswith('<'):
            # Legacy CSV format — validate structure
            lines = [l for l in sc.splitlines()
                     if l.strip() and not l.startswith('#')]
            if lines:
                # 1. Header check
                if 'model_id' not in lines[0].lower():
                    issues.append(
                        "ERROR: security_code missing CSV header. "
                        "First line must be: "
                        "id,name,model_id:id,group_id:id,"
                        "perm_read,perm_write,perm_create,perm_unlink"
                    )

                # 2. Column count
                for i, line in enumerate(lines[1:], 2):
                    cols = line.split(',')
                    if len(cols) < 8:
                        issues.append(
                            f"ERROR: security_code line {i} has {len(cols)} "
                            f"columns — need 8. Line: '{line}'"
                        )
                        break

                # 3. Permission values must be 0 or 1
                for i, line in enumerate(lines[1:], 2):
                    cols = line.split(',')
                    if len(cols) >= 8:
                        for p in cols[4:8]:
                            if p.strip() not in ('0', '1'):
                                issues.append(
                                    f"ERROR: security_code line {i} has "
                                    f"invalid permission '{p.strip()}'. "
                                    f"Permissions must be 0 or 1."
                                )
                                break

    # ═════════════════════════════════════════════════════════════════════
    # MANIFEST_CODE
    # ═════════════════════════════════════════════════════════════════════
    if mod.manifest_code and mod.manifest_code.strip():
        mc_clean = '\n'.join(
            l for l in mod.manifest_code.strip().splitlines()
            if not l.strip().startswith('#')
        )
        try:
            parsed = ast.literal_eval(mc_clean)
            if not isinstance(parsed, dict):
                issues.append("ERROR: manifest_code must be a Python dict {}.")
            else:
                deps = parsed.get('depends', [])
                vc   = mod.views_code or ''
                mc2  = mod.models_code or ''

                if 'base' not in deps:
                    issues.append(
                        "ERROR: 'base' missing from manifest depends. "
                        "'base' is always required."
                    )

                needs_auto = (
                    'base.automation' in vc or
                    'ir.actions.server' in vc or
                    'ir.cron' in vc or
                    'ir.cron' in mc2
                )
                if needs_auto and 'base_automation' not in deps:
                    issues.append(
                        "ERROR: 'base_automation' missing from manifest depends. "
                        "Required for ir.actions.server, base.automation, ir.cron. "
                        "Call action='fix' to auto-add."
                    )

                needs_mail = (
                    '<chatter' in vc or
                    'mail.template' in vc or
                    'message_post' in vc
                )
                if needs_mail and 'mail' not in deps:
                    issues.append(
                        "ERROR: 'mail' missing from manifest depends. "
                        "Required for <chatter/>, mail.template, message_post. "
                        "Call action='fix' to auto-add."
                    )

                if ('sale.order' in vc or 'sale.order' in mc2) and 'sale' not in deps:
                    issues.append(
                        "WARNING: Code references 'sale.order' but 'sale' "
                        "not in manifest depends."
                    )
                if ('account.move' in vc or 'account.move' in mc2) and 'account' not in deps:
                    issues.append(
                        "WARNING: Code references 'account.move' but 'account' "
                        "not in manifest depends."
                    )
                if ('hr.employee' in vc or 'hr.employee' in mc2) and 'hr' not in deps:
                    issues.append(
                        "WARNING: Code references 'hr.employee' but 'hr' "
                        "not in manifest depends."
                    )

                if parsed.get('installable') is False:
                    issues.append(
                        "ERROR: manifest 'installable' is False. "
                        "Set installable=True."
                    )

        except Exception as e:
            issues.append(
                f"ERROR: manifest_code syntax error: {e}. "
                f"Must be a valid Python dict literal."
            )

    # ═════════════════════════════════════════════════════════════════════
    # EMPTINESS
    # ═════════════════════════════════════════════════════════════════════
    if not mod.models_code or not mod.models_code.strip():
        issues.append("WARNING: models_code is empty — no models defined.")
    if not mod.security_code or not mod.security_code.strip():
        issues.append(
            "WARNING: security_code is empty. "
            "Users will get AccessError when opening the module."
        )
    if not mod.views_code or not mod.views_code.strip():
        issues.append(
            "WARNING: views_code is empty. "
            "Module will install but no UI will be visible."
        )

    # Check Many2one circular reference ordering
    if mod.models_code:
        mc = mod.models_code
        model_names_in_order = _re.findall(
            r'<field\s+name=["\']model["\']>([^<]+)</field>', mc
        )
        defined_so_far = set()
        for i, mn in enumerate(model_names_in_order):
            mn = mn.strip()
            # Find all relation= fields that appear BEFORE this model is fully defined
            # by checking if any relation points to a model not yet seen
            # (simplified check — look for relations defined before the model)
            defined_so_far.add(mn)

        # Check: any Many2one relation= pointing to a custom model
        # that appears AFTER the referencing model in the file
        relations = _re.findall(
            r'<record[^>]+model=["\']ir\.model\.fields["\'][^>]*>'
            r'.*?<field\s+name=["\']relation["\']>([^<]+)</field>',
            mc, flags=_re.DOTALL,
        )
        for rel in relations:
            rel = rel.strip()
            if rel.startswith('x_') and rel not in model_names_in_order[
                :model_names_in_order.index(rel) if rel in model_names_in_order else 0]:
                pass  # complex to check statically — warn generally

        # Simpler: warn if two models reference each other
        for mn in model_names_in_order:
            mn = mn.strip()
            if not mn.startswith('x_'):
                continue

    return issues


# ═══════════════════════════════════════════════════════════════════════════
# INSTALL ERROR HINTS
# ═══════════════════════════════════════════════════════════════════════════

def _parse_install_error_hints(error_str: str) -> list:
    hints = []
    e = (error_str or '').lower()

    if 'unknown module' in e or 'missing dependencies' in e:
        hints.append(
            "Add missing module to manifest depends. "
            "Common: 'base_automation', 'mail', 'sale', 'account', 'stock', 'hr'."
        )
    if 'mismatch' in e or 'opening and ending tag' in e:
        hints.append(
            "XML tag mismatch — wrong closing tag like </field_description>. "
            "All <field> records must close with </field>. "
            "Call action='fix' to auto-correct."
        )
    if 'read_group' in e and '_read_group' not in e:
        hints.append(
            "read_group() removed in Odoo 19 — use _read_group() instead."
        )
    if 'tree' in e and ('invalid' in e or 'unknown' in e):
        hints.append(
            "<tree> removed in Odoo 19. Call action='fix' to auto-replace with <list>."
        )
    if 'selection' in e and ('literal_eval' in e or 'parseerror' in e):
        hints.append(
            "Wrong selection format. "
            "Use [('key','Label')] not key:Label. "
            "Call action='fix' to auto-fix."
        )
    if 'xmlid' in e or 'external id' in e or ('ref' in e and 'not found' in e):
        hints.append(
            "A ref= or external ID is wrong. "
            "Check all ref= values match record id= attributes exactly."
        )
    if 'attrs' in e:
        hints.append(
            "'attrs' removed since Odoo 17. "
            "Use invisible=\"field != 'value'\" directly. "
            "Call action='fix' to auto-convert."
        )
    if 'calendar' in e and ('date_start' in e or 'date_stop' in e):
        hints.append(
            "Calendar view requires date_start= on a real date field. "
            "Remove 'calendar' from view_mode or add a proper calendar view record."
        )
    if 'pivot' in e and 'view' in e:
        hints.append(
            "view_mode has 'pivot' but no pivot view record exists. "
            "Call action='fix' to auto-remove from view_mode."
        )
    if 'only administrator' in e or 'access denied' in e:
        hints.append(
            "Permission denied. Log in as an Odoo administrator and retry."
        )
    if 'constraint' in e and 'violation' in e:
        hints.append(
            "Database constraint violated. "
            "Check field names start with x_ and are unique per model."
        )
    if 'state' in e and 'manual' in e:
        hints.append(
            "ir.model record missing state='manual'. "
            "Add <field name='state'>manual</field> to every ir.model record."
        )
    if not hints:
        hints.append(
            "Read install_log carefully. "
            "Common fixes: check XML syntax, verify all ref= ids exist, "
            "ensure depends includes all required modules, "
            "check view_mode matches actual view records. "
            "Call action='fix' then action='install' again."
        )
    return hints



# ═══════════════════════════════════════════════════════════════════════════
# SPEC-TO-XML GENERATOR
# Converts a structured JSON spec into guaranteed-correct Odoo 19 XML.
# The LLM provides a small JSON object; the server writes all the XML.
# This eliminates the most common LLM errors: <tree>, wrong selection format,
# missing state='manual', wrong security CSV refs, etc.
# ═══════════════════════════════════════════════════════════════════════════

_FIELD_TYPE_DEFAULTS = {
    'char':      {'required': False},
    'text':      {'required': False},
    'html':      {'required': False},
    'integer':   {'required': False},
    'float':     {'required': False},
    'monetary':  {'required': False},
    'boolean':   {'required': False},
    'date':      {'required': False},
    'datetime':  {'required': False},
    'selection': {'required': False},
    'many2one':  {'required': False},
    'many2many': {'required': False},
    'one2many':  {'required': False},
    'binary':    {'required': False},
}


_SPEC_NAME_RE = re.compile(r'^x_[a-z0-9_]+$')


def _validate_spec_contract(spec: dict) -> None:
    """Validate the spec JSON contract before generating XML."""
    models = spec.get('models', [])
    if not models:
        raise ValueError("spec.models must contain at least one model.")

    for idx, model in enumerate(models, start=1):
        model_name = (model.get('name') or '').strip()
        if not _SPEC_NAME_RE.match(model_name):
            raise ValueError(
                f"models[{idx}].name must match ^x_[a-z0-9_]+$ (got {model_name!r}). Use underscore names like 'x_furniture_item'."
            )

        fields = model.get('fields', [])
        if not fields:
            raise ValueError(f"models[{idx}].fields must contain at least one field.")

        for fidx, field in enumerate(fields, start=1):
            field_name = (field.get('name') or '').strip()
            field_type = (field.get('type') or 'char').strip()
            if not _SPEC_NAME_RE.match(field_name):
                raise ValueError(
                    f"models[{idx}].fields[{fidx}].name must match ^x_[a-z0-9_]+$ (got {field_name!r})."
                )
            if field_type in ('many2one', 'many2many') and not (field.get('relation') or '').strip():
                raise ValueError(
                    f"models[{idx}].fields[{fidx}] ({field_name}) requires 'relation' for {field_type}."
                )
            if field_type == 'one2many':
                relation = (field.get('relation') or '').strip()
                inverse_name = (field.get('inverse_name') or '').strip()
                if not relation or not inverse_name:
                    raise ValueError(
                        f"models[{idx}].fields[{fidx}] ({field_name}) requires both 'relation' and 'inverse_name' for one2many."
                    )
            if field_type == 'selection' and not field.get('options'):
                raise ValueError(
                    f"models[{idx}].fields[{fidx}] ({field_name}) requires non-empty 'options' for selection."
                )


def _preprocess_spec_models(models: list) -> list:
    """
    Pre-process spec models to guarantee first-attempt install success.

    Fixes applied automatically:
      1. Auto-add x_name field to models missing one (Odoo uses x_name
         for display_name on custom models — without it, many2one
         dropdowns show 'x_model,ID' instead of a human name).
      2. Auto-create inverse many2one fields for one2many relationships.
         If model A has one2many x_line_ids → x_line (inverse x_a_id),
         but x_line doesn't have x_a_id, we auto-add it.
      3. Topological sort so parent models (referenced by many2one)
         load BEFORE children. Without this, Odoo fails with
         'relation x_parent does not exist' during XML load.
    """
    if not models:
        return models

    import copy as _copy
    models = _copy.deepcopy(models)  # don't mutate the original spec

    model_names = {m.get('name', '').strip() for m in models}
    model_by_name = {m.get('name', '').strip(): m for m in models}

    # ── 1. Auto-add x_name if missing ─────────────────────────────────────
    for m in models:
        field_names = {f.get('name', '').strip() for f in m.get('fields', [])}
        if 'x_name' not in field_names:
            label = m.get('label', '') or (
                m.get('name', '').replace('x_', '').replace('_', ' ').title()
            )
            m.setdefault('fields', []).insert(0, {
                'name': 'x_name',
                'type': 'char',
                'label': label,
                'required': True,
            })

    # ── 2. Auto-create inverse many2one for one2many ──────────────────────
    for m in models:
        model_name = m.get('name', '').strip()
        for fld in m.get('fields', []):
            if fld.get('type') != 'one2many':
                continue
            rel = fld.get('relation', '').strip()
            inv = fld.get('inverse_name', '').strip()
            if not rel or not inv or rel not in model_by_name:
                continue  # external model or incomplete — skip
            target = model_by_name[rel]
            target_names = {
                f.get('name', '').strip() for f in target.get('fields', [])
            }
            if inv not in target_names:
                parent_label = m.get('label', '') or (
                    model_name.replace('x_', '').replace('_', ' ').title()
                )
                target.setdefault('fields', []).append({
                    'name': inv,
                    'type': 'many2one',
                    'label': parent_label,
                    'relation': model_name,
                })

    # ── 3. Topological sort — parents before children ─────────────────────
    #   If model A has many2one to model B, then B must load first.
    #   one2many is EXCLUDED — it creates circular deps and is deferred.
    deps = {}
    for m in models:
        mn = m.get('name', '').strip()
        deps[mn] = set()
        for fld in m.get('fields', []):
            if fld.get('type') in ('many2one', 'many2many'):
                rel = fld.get('relation', '').strip()
                if rel in model_names and rel != mn:
                    deps[mn].add(rel)

    sorted_models = []
    defined = set()
    remaining = list(models)
    safety = len(models) ** 2 + len(models) + 1

    while remaining and safety > 0:
        safety -= 1
        progress = False
        still_remaining = []
        for m in remaining:
            mn = m.get('name', '').strip()
            if deps.get(mn, set()).issubset(defined):
                sorted_models.append(m)
                defined.add(mn)
                progress = True
            else:
                still_remaining.append(m)
        remaining = still_remaining
        if not progress:
            # Circular dependency — append remaining as-is (fixers handle it)
            sorted_models.extend(remaining)
            break

    return sorted_models


def _spec_to_xml(spec: dict) -> dict:
    """
    Convert a module JSON spec into models_code, views_code, security_code,
    manifest_code strings — all guaranteed correct for Odoo 19.

    Spec format:
    {
      "name": "Hospital Management",
      "technical_name": "x_hospital",          # optional, fallback to name
      "depends": ["base"],                      # optional, auto-detected
      "description": "...",                     # optional
      "models": [
        {
          "name": "x_patient",                  # REQUIRED, must start with x_
          "label": "Patient",                   # REQUIRED, human name
          "views": ["list", "form"],            # optional, default: list + form
          "fields": [
            {"name": "x_name",   "type": "char",      "label": "Name",    "required": true},
            {"name": "x_status", "type": "selection",  "label": "Status",
             "options": [["draft","Draft"],["done","Done"]]},
            {"name": "x_partner_id", "type": "many2one", "label": "Partner",
             "relation": "res.partner"},
            {"name": "x_line_ids", "type": "one2many", "label": "Lines",
             "relation": "x_patient_line", "inverse_name": "x_patient_id"}
          ]
        }
      ]
    }
    Returns dict: {models_code, views_code, security_code, manifest_code, description}
    """
    _validate_spec_contract(spec)
    models = _preprocess_spec_models(spec.get('models', []))

    mod_name    = spec.get('name', '')
    tech_name   = spec.get('technical_name', '').strip()
    extra_deps  = spec.get('depends', [])
    description = spec.get('description', mod_name)

    # ── Models XML ────────────────────────────────────────────────────────
    mc_lines = ['<odoo><data noupdate="1">']
    has_monetary = False
    has_automation = False
    deferred_o2m = []  # one2many fields emitted AFTER all models exist

    for m in models:
        model_tech = m.get('name', '').strip()
        model_label = m.get('label', model_tech.replace('x_', '').replace('_', ' ').title())
        fields = m.get('fields', [])

        if not model_tech:
            continue

        record_id = 'model_' + model_tech.replace('.', '_')

        mc_lines += [
            '',
            f'  <!-- ── {model_label} ── -->',
            f'  <record id="{record_id}" model="ir.model">',
            f'    <field name="name">{model_label}</field>',
            f'    <field name="model">{model_tech}</field>',
            f'    <field name="state">manual</field>',
            f'  </record>',
        ]

        # Track if we need a currency companion
        monetary_fields = [f for f in fields if f.get('type') == 'monetary']
        has_currency_field = any(f.get('name') == 'x_currency_id' for f in fields)
        if monetary_fields and not has_currency_field:
            has_monetary = True
            mc_lines += [
                '',
                f'  <record id="field_{model_tech}__x_currency_id" model="ir.model.fields">',
                f'    <field name="model_id" ref="{record_id}"/>',
                f'    <field name="name">x_currency_id</field>',
                f'    <field name="field_description">Currency</field>',
                f'    <field name="ttype">many2one</field>',
                f'    <field name="relation">res.currency</field>',
                f'  </record>',
            ]

        for fld in fields:
            fname  = fld.get('name', '').strip()
            ftype  = fld.get('type', 'char').strip()
            flabel = fld.get('label', fname)
            freq   = fld.get('required', False)
            freadonly = fld.get('readonly', False)
            frel   = fld.get('relation', '').strip()
            finv   = fld.get('inverse_name', '').strip()
            fopts  = fld.get('options', [])
            fhelp  = fld.get('help', '').strip()

            if not fname:
                continue

            # DEFER one2many fields — child model must exist first.
            # They are emitted in a second pass after ALL models are created.
            if ftype == 'one2many':
                deferred_o2m.append({
                    'model_tech': model_tech,
                    'record_id': record_id,
                    'fname': fname,
                    'flabel': flabel,
                    'frel': frel,
                    'finv': finv,
                })
                continue

            field_record_id = f'field_{model_tech}__{fname}'
            mc_lines += [
                '',
                f'  <record id="{field_record_id}" model="ir.model.fields">',
                f'    <field name="model_id" ref="{record_id}"/>',
                f'    <field name="name">{fname}</field>',
                f'    <field name="field_description">{flabel}</field>',
                f'    <field name="ttype">{ftype}</field>',
            ]

            # NEVER set required on relational fields — no data exists during install
            if freq and ftype not in ('many2one', 'many2many', 'one2many'):
                mc_lines.append('    <field name="required" eval="True"/>')
            if freadonly:
                mc_lines.append('    <field name="readonly" eval="True"/>')
            if fhelp:
                mc_lines.append(f'    <field name="help">{fhelp}</field>')

            if ftype == 'selection' and fopts:
                sel_str = str([(o[0], o[1]) for o in fopts]).replace('"', "'")
                mc_lines.append(f'    <field name="selection">{sel_str}</field>')

            if ftype in ('many2one', 'many2many') and frel:
                mc_lines.append(f'    <field name="relation">{frel}</field>')
                # NOTE: ondelete is a Python-only ORM param — NEVER put it in XML.
                # ir.model.fields has no 'ondelete' column → ValueError at install.

            if ftype == 'monetary':
                mc_lines.append('    <field name="currency_field">x_currency_id</field>')

            mc_lines.append('  </record>')

    # ── DEFERRED one2many fields (child models now guaranteed to exist) ────
    if deferred_o2m:
        mc_lines += ['', '  <!-- one2many fields (deferred — child models exist) -->']
        for o2m in deferred_o2m:
            frid = f"field_{o2m['model_tech']}__{o2m['fname']}"
            mc_lines += [
                '',
                f'  <record id="{frid}" model="ir.model.fields">',
                f'    <field name="model_id" ref="{o2m["record_id"]}"/>',
                f'    <field name="name">{o2m["fname"]}</field>',
                f'    <field name="field_description">{o2m["flabel"]}</field>',
                f'    <field name="ttype">one2many</field>',
            ]
            if o2m['frel']:
                mc_lines.append(f'    <field name="relation">{o2m["frel"]}</field>')
            if o2m['finv']:
                mc_lines.append(f'    <field name="relation_field">{o2m["finv"]}</field>')
            mc_lines.append('  </record>')

    mc_lines.append('')
    mc_lines.append('</data></odoo>')
    models_code = '\n'.join(mc_lines)

    # ── Views XML ─────────────────────────────────────────────────────────
    vc_lines = ['<odoo><data>']

    # Detect if any server actions are needed
    for m in models:
        model_tech  = m.get('name', '').strip()
        model_label = m.get('label', model_tech.replace('x_', '').replace('_', ' ').title())
        view_types  = m.get('views', ['list', 'form'])
        fields      = m.get('fields', [])
        record_id   = 'model_' + model_tech.replace('.', '_')

        if not model_tech:
            continue

        # ── Simple field names for views (exclude o2m in list, binary, etc.) ──
        list_fields  = [f for f in fields
                        if f.get('type') not in ('one2many', 'binary', 'html', 'text')
                        and not f.get('hide_in_list')]
        form_fields  = fields  # all fields in form

        # ── List view ─────────────────────────────────────────────────────
        if 'list' in view_types:
            vc_lines += [
                '',
                f'  <record id="view_{model_tech}_list" model="ir.ui.view">',
                f'    <field name="name">{model_tech}.list</field>',
                f'    <field name="model">{model_tech}</field>',
                f'    <field name="arch" type="xml">',
                f'      <list string="{model_label}">',
            ]
            for fld in list_fields[:8]:  # limit list columns to 8
                fname = fld.get('name', '')
                if fname:
                    vc_lines.append(f'        <field name="{fname}"/>')
            vc_lines += [
                f'      </list>',
                f'    </field>',
                f'  </record>',
            ]

        # ── Form view ─────────────────────────────────────────────────────
        if 'form' in view_types:
            vc_lines += [
                '',
                f'  <record id="view_{model_tech}_form" model="ir.ui.view">',
                f'    <field name="name">{model_tech}.form</field>',
                f'    <field name="model">{model_tech}</field>',
                f'    <field name="arch" type="xml">',
                f'      <form string="{model_label}">',
                f'        <sheet>',
                f'          <group>',
            ]
            for fld in form_fields:
                fname = fld.get('name', '')
                ftype = fld.get('type', 'char')
                if fname:
                    if ftype in ('text', 'html'):
                        vc_lines.append(f'            <field name="{fname}" colspan="2"/>')
                    elif ftype == 'one2many':
                        pass  # handled separately below
                    else:
                        vc_lines.append(f'            <field name="{fname}"/>')
            vc_lines.append('          </group>')

            # ── One2many notebook ──────────────────────────────────────────
            o2m_fields = [f for f in form_fields if f.get('type') == 'one2many']
            if o2m_fields:
                vc_lines.append('          <notebook>')
                for fld in o2m_fields:
                    fname  = fld.get('name', '')
                    flabel = fld.get('label', fname)
                    frel   = fld.get('relation', '')
                    if fname:
                        vc_lines += [
                            f'            <page string="{flabel}">',
                            f'              <field name="{fname}">',
                            f'                <list>',
                        ]
                        # Add visible fields of the related model
                        rel_model = next(
                            (rm for rm in models
                             if rm.get('name') == frel), {}
                        )
                        for rf in rel_model.get('fields', [])[:5]:
                            rfname = rf.get('name', '')
                            rftype = rf.get('type', 'char')
                            if rfname and rftype not in ('one2many', 'binary'):
                                vc_lines.append(f'                  <field name="{rfname}"/>')
                        vc_lines += [
                            f'                </list>',
                            f'              </field>',
                            f'            </page>',
                        ]
                vc_lines.append('          </notebook>')

            vc_lines += [
                f'        </sheet>',
                f'      </form>',
                f'    </field>',
                f'  </record>',
            ]

        # ── Kanban view ────────────────────────────────────────────────────
        if 'kanban' in view_types:
            name_field = next(
                (f.get('name') for f in fields
                 if f.get('type') == 'char'), 'id'
            )
            vc_lines += [
                '',
                f'  <record id="view_{model_tech}_kanban" model="ir.ui.view">',
                f'    <field name="name">{model_tech}.kanban</field>',
                f'    <field name="model">{model_tech}</field>',
                f'    <field name="arch" type="xml">',
                f'      <kanban>',
                f'        <field name="{name_field}"/>',
                f'        <templates>',
                f'          <t t-name="card">',
                f'            <field name="{name_field}" class="fw-bold"/>',
                f'          </t>',
                f'        </templates>',
                f'      </kanban>',
                f'    </field>',
                f'  </record>',
            ]

        # ── Search view ────────────────────────────────────────────────────
        if 'search' in view_types:
            char_fields = [f for f in fields if f.get('type') == 'char']
            vc_lines += [
                '',
                f'  <record id="view_{model_tech}_search" model="ir.ui.view">',
                f'    <field name="name">{model_tech}.search</field>',
                f'    <field name="model">{model_tech}</field>',
                f'    <field name="arch" type="xml">',
                f'      <search>',
            ]
            for fld in char_fields[:3]:
                vc_lines.append(f'        <field name="{fld["name"]}"/>')
            vc_lines += [
                f'      </search>',
                f'    </field>',
                f'  </record>',
            ]

        # ── Window Action ──────────────────────────────────────────────────
        view_mode_parts = [v for v in view_types if v in
                           ('list', 'form', 'kanban', 'calendar', 'pivot', 'graph', 'search')]
        if 'list' not in view_mode_parts:
            view_mode_parts.insert(0, 'list')
        if 'form' not in view_mode_parts:
            view_mode_parts.insert(1, 'form')
        view_mode = ','.join(dict.fromkeys(view_mode_parts))  # deduplicate, keep order

        vc_lines += [
            '',
            f'  <record id="action_{model_tech}" model="ir.actions.act_window">',
            f'    <field name="name">{model_label}</field>',
            f'    <field name="res_model">{model_tech}</field>',
            f'    <field name="view_mode">{view_mode}</field>',
            f'  </record>',
        ]

    # ── Menu items ────────────────────────────────────────────────────────
    first_model = models[0] if models else {}
    root_label  = mod_name or first_model.get('label', 'App')
    vc_lines += [
        '',
        f'  <menuitem id="menu_{tech_name}_root" name="{root_label}"/>',
    ]
    for m in models:
        model_tech  = m.get('name', '').strip()
        model_label = m.get('label', model_tech)
        if not model_tech:
            continue
        vc_lines += [
            f'  <menuitem id="menu_{model_tech}"',
            f'            name="{model_label}"',
            f'            parent="menu_{tech_name}_root"',
            f'            action="action_{model_tech}"/>',
        ]

    vc_lines += ['', '</data></odoo>']
    views_code = '\n'.join(vc_lines)

    # ── Security XML (NOT CSV — XML refs resolve in same transaction) ────
    sc_lines = ['<odoo><data noupdate="0">']
    for m in models:
        model_tech = m.get('name', '').strip()
        if not model_tech:
            continue
        record_id = 'model_' + model_tech.replace('.', '_')
        safe_name = model_tech.replace('.', '_')
        sc_lines += [
            '',
            f'  <record id="access_{safe_name}" model="ir.model.access">',
            f'    <field name="name">{model_tech} access</field>',
            f'    <field name="model_id" ref="{record_id}"/>',
            f'    <field name="group_id" eval="False"/>',
            f'    <field name="perm_read" eval="1"/>',
            f'    <field name="perm_write" eval="1"/>',
            f'    <field name="perm_create" eval="1"/>',
            f'    <field name="perm_unlink" eval="1"/>',
            f'  </record>',
        ]
    sc_lines += ['', '</data></odoo>']
    security_code = '\n'.join(sc_lines)

    # ── Manifest ──────────────────────────────────────────────────────────
    # Auto-detect dependencies
    all_field_relations = []
    for m in models:
        for f in m.get('fields', []):
            rel = f.get('relation', '')
            if rel and '.' in rel:
                all_field_relations.append(rel.split('.')[0])

    auto_deps = {'base'}
    if has_monetary:
        auto_deps.add('base')  # res.currency is in base
    if has_automation:
        auto_deps.add('base_automation')
    for rel_prefix in all_field_relations:
        dep_map = {
            'sale': 'sale', 'account': 'account', 'stock': 'stock',
            'hr': 'hr', 'project': 'project', 'crm': 'crm',
            'purchase': 'purchase', 'helpdesk': 'helpdesk',
        }
        if rel_prefix in dep_map:
            auto_deps.add(dep_map[rel_prefix])
    for d in extra_deps:
        auto_deps.add(d)

    deps_str = ', '.join(f"'{d}'" for d in sorted(auto_deps))
    manifest_code = (
        f"{{\n"
        f"    'name': '{mod_name}',\n"
        f"    'version': '19.0.1.0.0',\n"
        f"    'summary': '{description}',\n"
        f"    'category': 'Technical',\n"
        f"    'author': 'MCP Builder',\n"
        f"    'depends': [{deps_str}],\n"
        f"    'installable': True,\n"
        f"    'application': True,\n"
        f"    'auto_install': False,\n"
        f"    'license': 'LGPL-3',\n"
        f"}}"
    )

    return {
        'models_code':   models_code,
        'views_code':    views_code,
        'security_code': security_code,
        'manifest_code': manifest_code,
        'description':   description,
    }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN TOOL
# ═══════════════════════════════════════════════════════════════════════════

def _tool_manage_module(env, params, user=None):
    """
    Odoo 19 data module builder — final production version.

    Actions:
      create      — create or update module (idempotent)
      update      — update specific code fields of existing module
      get         — retrieve module code fields
      list        — list all modules
      delete      — delete module record
      install     — validate + generate ZIP + install via base_import_module
      preview     — validate without installing
      duplicate   — clone with new technical_name
      add_feature — append a feature to existing module (iterative build)
      fix         — auto-fix ALL common issues then re-validate
      export      — export module as CSV attachment via chatter
    """
    action = (params.get('action') or '').strip().lower()
    Mod    = _sudo_env(env, 'mcp.module')

    # ── LIST ──────────────────────────────────────────────────────────────
    if action == 'list':
        rows = Mod.search_read(
            [],
            ['id', 'name', 'technical_name', 'state', 'write_date'],
            order='write_date desc',
        )
        return {"count": len(rows), "modules": rows}

    # ── GET ───────────────────────────────────────────────────────────────
    if action == 'get':
        tech = (params.get('technical_name') or '').strip()
        if not tech:
            raise ValueError("'technical_name' required.")
        mod = Mod.search([('technical_name', '=', tech)], limit=1)
        if not mod:
            raise ValueError(f"Module '{tech}' not found.")
        return {
            "id":             mod.id,
            "name":           mod.name,
            "technical_name": mod.technical_name,
            "state":          mod.state,
            "models_code":    mod.models_code or '',
            "views_code":     mod.views_code or '',
            "security_code":  mod.security_code or '',
            "manifest_code":  mod.manifest_code or '',
            "report_code":    mod.report_code or '',
            "js_code":        mod.js_code or '',
            "scss_code":      mod.scss_code or '',
            "owl_code":       mod.owl_code or '',
            "install_log":    mod.install_log or '',
        }

    # ── DELETE ────────────────────────────────────────────────────────────
    if action == 'delete':
        tech = (params.get('technical_name') or '').strip()
        if not tech:
            raise ValueError("'technical_name' required.")
        mod = Mod.search([('technical_name', '=', tech)], limit=1)
        if not mod:
            raise ValueError(f"Module '{tech}' not found.")
        name = mod.name
        mod.unlink()
        return {"message": f"Module '{name}' ({tech}) deleted."}

    # ── PREVIEW ───────────────────────────────────────────────────────────
    if action == 'preview':
        tech = (params.get('technical_name') or '').strip()
        if not tech:
            raise ValueError("'technical_name' required.")
        mod = Mod.search([('technical_name', '=', tech)], limit=1)
        if not mod:
            raise ValueError(f"Module '{tech}' not found.")
        issues = _validate_module_code(mod)
        errors = [i for i in issues if i.startswith('ERROR')]
        warns  = [i for i in issues if i.startswith('WARNING')]
        return {
            "technical_name": tech,
            "valid":    len(errors) == 0,
            "errors":   errors,
            "warnings": warns,
            "message":  (
                "No errors — safe to install."
                if not errors else
                f"{len(errors)} error(s) must be fixed before install."
            ),
        }

    # ── DUPLICATE ─────────────────────────────────────────────────────────
    if action == 'duplicate':
        src  = (params.get('technical_name') or '').strip()
        dest = (params.get('new_technical_name') or '').strip()
        name = (params.get('new_name') or '').strip()
        if not src or not dest:
            raise ValueError(
                "'technical_name' and 'new_technical_name' required."
            )
        src_mod = Mod.search([('technical_name', '=', src)], limit=1)
        if not src_mod:
            raise ValueError(f"Source module '{src}' not found.")
        if Mod.search([('technical_name', '=', dest)], limit=1):
            raise ValueError(f"Module '{dest}' already exists.")
        new_mod = src_mod.copy({
            'technical_name': dest,
            'name':  name or dest,
            'state': 'draft',
        })
        return {
            "id":             new_mod.id,
            "technical_name": dest,
            "message":        f"Module duplicated as '{dest}'.",
        }

    # ── ADD_FEATURE ───────────────────────────────────────────────────────
    if action == 'add_feature':
        """
        Append a single feature to an existing module without replacing everything.
        Build complex modules incrementally — one model/view/automation at a time.
        feature_type: model | view | automation | security_row
        """
        tech         = (params.get('technical_name') or '').strip()
        feature_type = (params.get('feature_type') or '').strip().lower()
        code         = (params.get('code') or '').strip()

        if not tech:
            raise ValueError("'technical_name' required.")
        if not feature_type:
            raise ValueError(
                "'feature_type' required: model | view | automation | security_row"
            )
        if not code:
            raise ValueError("'code' required — XML or CSV to append.")

        mod = Mod.search([('technical_name', '=', tech)], limit=1)
        if not mod:
            raise ValueError(
                f"Module '{tech}' not found. Call action='create' first."
            )

        if feature_type == 'model':
            base = mod.models_code or '<odoo><data noupdate="1">\n</data></odoo>'
            mod.write({
                'models_code': base.replace(
                    '</data></odoo>',
                    f'\n\n  {code}\n</data></odoo>'
                )
            })
        elif feature_type in ('view', 'automation'):
            base = mod.views_code or '<odoo><data>\n</data></odoo>'
            mod.write({
                'views_code': base.replace(
                    '</data></odoo>',
                    f'\n\n{code}\n</data></odoo>'
                )
            })
        elif feature_type == 'security_row':
            header = (
                'id,name,model_id:id,group_id:id,'
                'perm_read,perm_write,perm_create,perm_unlink\n'
            )
            base = mod.security_code or header
            mod.write({
                'security_code': base.rstrip() + '\n' + code + '\n'
            })
        else:
            raise ValueError(
                f"Unknown feature_type '{feature_type}'. "
                f"Use: model | view | automation | security_row"
            )

        # Auto-fix after appending
        _apply_all_fixes(mod)
        issues = _validate_module_code(mod)
        errors = [i for i in issues if i.startswith('ERROR')]
        return {
            "technical_name": tech,
            "feature_type":   feature_type,
            "errors":         errors,
            "message": (
                f"Feature ({feature_type}) appended to '{tech}'. "
                + (
                    f"⚠ {len(errors)} error(s) — fix before install."
                    if errors else
                    "No errors. Call action='install' when ready."
                )
            ),
        }

    # ── FIX ───────────────────────────────────────────────────────────────
    if action == 'fix':
        tech = (params.get('technical_name') or '').strip()
        if not tech:
            raise ValueError("'technical_name' required.")
        mod = Mod.search([('technical_name', '=', tech)], limit=1)
        if not mod:
            raise ValueError(f"Module '{tech}' not found.")

        # Run ALL fixers via master function
        applied = _apply_all_fixes(mod)

        if not applied:
            return {
                "technical_name": tech,
                "fixes_applied":  [],
                "message": (
                    "No auto-fixable issues found. "
                    "Call action='preview' to see all errors, "
                    "then action='update' to fix manually."
                ),
            }

        issues  = _validate_module_code(mod)
        errors  = [i for i in issues if i.startswith('ERROR')]
        return {
            "technical_name":   tech,
            "fixes_applied":    applied,
            "remaining_errors": errors,
            "message": (
                f"Applied {len(applied)} fix(es): "
                + "; ".join(applied)
                + (
                    f" ⚠ {len(errors)} error(s) remain — fix manually."
                    if errors else
                    " No remaining errors. Call action='install'."
                )
            ),
        }

    # ── EXPORT ─────────────────────────────────────────────────────────────
    if action == 'export':
        tech = (params.get('technical_name') or '').strip()
        if not tech:
            raise ValueError("'technical_name' required.")
        mod = Mod.search([('technical_name', '=', tech)], limit=1)
        if not mod:
            raise ValueError(f"Module '{tech}' not found.")
        mod.action_export_csv()
        return {
            "technical_name": tech,
            "message": (
                f"Module '{tech}' exported as CSV. "
                f"Check the chatter on the mcp.module record for the attachment."
            ),
        }

    # ── CREATE / UPDATE ───────────────────────────────────────────────────
    if action in ('create', 'update'):
        tech = (params.get('technical_name') or '').strip()
        if not tech:
            raise ValueError("'technical_name' required.")

        safe = tech.replace('_', 'a')
        if not safe.isalnum() or not safe[0].isalpha():
            raise ValueError(
                f"technical_name '{tech}' is invalid. "
                f"Use only letters, digits, underscores, starting with a letter. "
                f"Example: 'x_hospital_management'."
            )
        if keyword.iskeyword(tech):
            raise ValueError(f"'{tech}' is a Python keyword.")

        # BUG 6 FIX: action='create' ALWAYS saves without auto-installing.
        # The MCP client must call action='install' separately after review.
        # This prevents the create→install→fail→fix→install token-wasting loop.
        skip_install = True if action == 'create' else (
            str(params.get('skip_install', '')).lower() in ('true', '1', 'yes')
        )

        mod  = Mod.search([('technical_name', '=', tech)], limit=1)
        vals = {}

        # ── SPEC-BASED GENERATION ──────────────────────────────────────────
        # If 'spec' is provided (JSON object), generate all XML server-side.
        # This eliminates LLM XML errors: <tree>, wrong selection format,
        # missing state='manual', wrong CSV refs etc. are impossible.
        spec = params.get('spec')
        spec_used = bool(spec and action == 'create')
        if spec_used:
            try:
                if isinstance(spec, str):
                    import json as _json2
                    spec = _json2.loads(spec)
                # Inject tech name into spec if not set
                if not spec.get('name'):
                    spec['name'] = tech.replace('_', ' ').title()
                spec.setdefault('technical_name', tech)
                _validate_spec_contract(spec)
                generated = _spec_to_xml(spec)
                vals.update(generated)
                vals.setdefault('name', spec.get('name', tech.replace('_', ' ').title()))
                vals.setdefault('description', spec.get('description', ''))
                _logger.info(
                    "mcp.module [%s]: spec-based generation — "
                    "models=%d, views=%d, security=%d chars",
                    tech,
                    len(vals.get('models_code', '')),
                    len(vals.get('views_code', '')),
                    len(vals.get('security_code', '')),
                )
            except Exception as e:
                _logger.error("spec-to-xml failed [%s]: %s", tech, _tb.format_exc())
                _log(env, tool='odoo_manage_module', model='mcp.module',
                     operation='module', log_level='error', state='error',
                     error=e, tb=_tb.format_exc(),
                     payload={'action': 'create', 'technical_name': tech})
                raise ValueError(
                    f"spec-to-xml generation failed: {e}. "
                    f"Check your spec format — models[].name must start with x_, "
                    f"each field needs name, type, label."
                )

        # ── MANUAL XML FIELDS (only if spec was NOT used) ─────────────────
        # IMPORTANT: For action='update', views_code and models_code are MERGED
        # (new content appended) rather than overwritten. This prevents losing
        # spec-generated menus/actions when the AI sends a partial update
        # (e.g. only a dashboard OWL component in views_code).
        for k in _MOD_FIELDS:
            v = params.get(k)
            if v is not None:
                v = v.strip() if isinstance(v, str) else v
                if action == 'update' and mod and k in ('views_code', 'models_code'):
                    # Merge: append new XML records to existing content.
                    # Strip outer odoo/data wrappers from both sides before merging.
                    existing = (getattr(mod, k) or '').strip()
                    new_part = _re.sub(
                        r'^<\?xml[^\?]*\?>\s*', '', v, flags=_re.DOTALL
                    ).strip()
                    new_part = _re.sub(
                        r'^<odoo[^>]*>\s*(?:<data[^>]*>)?', '', new_part, flags=_re.DOTALL
                    ).strip()
                    new_part = _re.sub(
                        r'(?:</data>)?\s*</odoo>\s*$', '', new_part, flags=_re.DOTALL
                    ).strip()
                    existing_inner = _re.sub(
                        r'^<\?xml[^\?]*\?>\s*', '', existing, flags=_re.DOTALL
                    ).strip()
                    existing_inner = _re.sub(
                        r'^<odoo[^>]*>\s*(?:<data[^>]*>)?', '', existing_inner, flags=_re.DOTALL
                    ).strip()
                    existing_inner = _re.sub(
                        r'(?:</data>)?\s*</odoo>\s*$', '', existing_inner, flags=_re.DOTALL
                    ).strip()
                    if new_part and new_part not in existing_inner:
                        vals[k] = existing_inner + '\n\n' + new_part if existing_inner else new_part
                    # If new content is already present or empty, keep existing
                elif v is not None:
                    vals[k] = v


        created_new = False
        if action == 'create':
            if not mod:
                vals['technical_name'] = tech
                vals.setdefault('name', tech.replace('_', ' ').title())
                mod = Mod.create(vals)
                created_new = True
            elif mod.state in ('error', 'draft'):
                # BUG 5 FIX: Auto-delete broken/draft module before recreating.
                # Prevents stale-state loops where broken records block clean installs.
                _logger.info(
                    "mcp.module [%s]: deleting stale %s module before recreate.",
                    tech, mod.state,
                )
                mod.unlink()
                vals['technical_name'] = tech
                vals.setdefault('name', tech.replace('_', ' ').title())
                mod = Mod.create(vals)
                created_new = True
            else:
                mod.write(vals)
        else:
            if not mod:
                raise ValueError(
                    f"Module '{tech}' not found. "
                    f"Use action='create' first."
                )
            mod.write(vals)

        mod.write({'state': 'generated'})

        # Auto-fix everything immediately after save
        _apply_all_fixes(mod)

        issues   = _validate_module_code(mod)
        errors   = [i for i in issues if i.startswith('ERROR')]
        warnings = [i for i in issues if i.startswith('WARNING')]

        next_msg = " No errors — call action='install' to install."
        if skip_install:
            next_msg = (
                " No errors — skip_install=true so module is saved but NOT installed. "
                "Review the code, then call action='install' when ready."
            )

        if errors and spec_used and created_new:
            mod.unlink()
            return {
                "technical_name": tech,
                "state": "error",
                "errors": errors,
                "warnings": warnings,
                "message": (
                    f"Module '{tech}' was NOT saved because spec validation produced {len(errors)} error(s). "
                    "Fix the spec and recreate from scratch."
                ),
            }

        return {
            "id":             mod.id,
            "technical_name": tech,
            "state":          mod.state,
            "errors":         errors,
            "warnings":       warnings,
            "message": (
                f"Module '{tech}' saved."
                + (
                    f" ⚠ {len(errors)} error(s): {errors[0]}"
                    if errors else next_msg
                )
            ),
        }

    # ── INSTALL ───────────────────────────────────────────────────────────
    if action == 'install':
        tech = (params.get('technical_name') or '').strip()
        if not tech:
            raise ValueError("'technical_name' required.")
        mod = Mod.search([('technical_name', '=', tech)], limit=1)
        if not mod:
            raise ValueError(f"Module '{tech}' not found.")

        force = str(params.get('force', '')).lower() in ('true', '1', 'yes')
        uninstall_first = str(params.get('uninstall_first', '')).lower() in (
            'true', '1', 'yes',
        )

        # Auto-fix before validation
        _apply_all_fixes(mod)

        # Block on remaining errors
        issues  = _validate_module_code(mod)
        errors  = [i for i in issues if i.startswith('ERROR')]
        if errors:
            return {
                "technical_name": tech,
                "state":  "error",
                "errors": errors,
                "message": (
                    f"Cannot install — {len(errors)} error(s) must be fixed:\n"
                    + "\n".join(errors)
                    + "\n\nCall action='update' to fix manually, "
                    "then action='install' again."
                ),
            }

        # Optional: uninstall first for clean reinstall
        if uninstall_first:
            IrMod = _sudo_env(env, 'ir.module.module')
            existing = IrMod.search([
                ('name', '=', tech), ('state', '=', 'installed'),
            ], limit=1)
            if existing:
                try:
                    existing.module_uninstall()
                    _logger.info(
                        "Module '%s' uninstalled for clean reinstall.", tech
                    )
                except Exception as e:
                    _logger.warning(
                        "Could not uninstall '%s': %s", tech, e
                    )
                    _log(env, tool='odoo_manage_module', model='mcp.module',
                         operation='module', log_level='warning', state='error',
                         error=e, payload={'action': 'install', 'uninstall_first': True,
                                           'technical_name': tech})

        # Attempt install
        try:
            mod.action_install_module()
        except Exception as e:
            _logger.error(
                "Module install failed [%s]: %s", tech, e, exc_info=True
            )
            _log(env, tool='odoo_manage_module', model='mcp.module',
                 operation='module', log_level='error', state='error',
                 error=e, tb=_tb.format_exc(),
                 payload={'action': 'install', 'technical_name': tech})

        install_log = mod.install_log or ''
        state       = mod.state

        if state == 'installed':
            return {
                "technical_name": tech,
                "state":          "installed",
                "message":        install_log,
                "next_step": (
                    "✅ Module installed successfully. "
                    "Reload browser (Ctrl+Shift+R) to see new menus. "
                    "To update: call action='update' then action='install' again."
                ),
            }

        # Install failed — give actionable hints
        hints = _parse_install_error_hints(install_log)
        return {
            "technical_name": tech,
            "state":          "error",
            "install_log":    install_log[:1000],
            "hints":          hints,
            "message": (
                f"Installation failed.\n\n"
                f"Error: {install_log[:400]}\n\n"
                f"Hints:\n" + "\n".join(f"  • {h}" for h in hints) +
                "\n\nNext: call action='fix' for auto-fixes, "
                "or action='update' to correct manually, "
                "then action='install' again."
            ),
        }

    raise ValueError(
        f"Unknown action '{action}'. " 
        "Use: create | update | get | list | delete | "
        "install | preview | duplicate | add_feature | fix | export"
    )
