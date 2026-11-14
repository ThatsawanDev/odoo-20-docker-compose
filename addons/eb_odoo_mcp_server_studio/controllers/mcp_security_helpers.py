# -*- coding: utf-8 -*-
"""
MCP security helpers: tool allowlist, model/field restrictions.
"""
import logging

_logger = logging.getLogger(__name__)

# Tools that require allowlist (Write/Code/Execute). Read tools auto-enabled.
TOOL_CATEGORY = {
    # Read - auto for all MCP users
    'odoo_list_models': 'read',
    'odoo_get_model_info': 'read',
    'odoo_get_fields': 'read',
    'odoo_search_read': 'read',
    'odoo_get_record': 'read',
    'odoo_aggregate': 'read',
    'odoo_read_group': 'read',
    # Write - allowlist
    'odoo_create': 'write',
    'odoo_write': 'write',
    'odoo_unlink': 'write',
    'odoo_import_data': 'write',
    'odoo_call_method': 'write',
    'odoo_execute_action': 'write',
    'odoo_add_custom_field': 'write',
    # Code/Execute - allowlist
    'odoo_execute_orm': 'execute',
    'odoo_code_search': 'execute',
    'odoo_code_read': 'execute',
    'odoo_search_webapp_code': 'execute',
    'odoo_search_module_code': 'execute',
    # Builder tools - allowlist
    'odoo_manage_echart': 'execute',
    'odoo_manage_webapp': 'execute',
    'odoo_manage_module': 'execute',
    'odoo_manage_report': 'execute',
}

# Tools NOT restricted by model/field restrictions (arbitrary code execution)
MODEL_RESTRICTION_EXCLUDED = {
    'odoo_execute_orm', 'odoo_manage_echart', 'odoo_manage_webapp',
    'odoo_manage_module',
}

def is_mcp_admin(user):
    """Check if user has MCP Admin group."""
    if not user:
        return False
    try:
        return user.has_group('eb_odoo_mcp_server_studio.group_mcp_admin')
    except Exception:
        pass
    try:
        return getattr(user, '_is_admin', lambda: False)()
    except Exception:
        pass
    return user.id == 2  # SUPERUSER_ID fallback


def check_tool_allowed(env, user, tool_name):
    """Raise PermissionError if user cannot use the tool."""
    cat = TOOL_CATEGORY.get(tool_name, 'read')
    if cat == 'read':
        return  # Read tools auto-enabled
    if is_mcp_admin(user):
        return  # Admin bypasses
    Allowlist = env['mcp.tool.allowlist'].sudo()
    rec = Allowlist.search([('tool_name', '=', tool_name)], limit=1)
    if not rec:
        raise PermissionError(
            f"Tool '{tool_name}' requires allowlist membership. Contact MCP Admin."
        )
    if user.id not in rec.user_ids.ids:
        raise PermissionError(
            f"You are not allowed to use '{tool_name}'. Contact MCP Admin."
        )


def get_visible_tools(env, user, tools, client_name=''):
    """
    Return the subset of TOOLS that should be advertised to this client/user.

    This complements check_tool_allowed(): only tools the user can actually run
    are advertised to the client.
    """
    visible = []
    for tool in tools:
        tool_name = tool.get('name', '')
        try:
            check_tool_allowed(env, user, tool_name)
        except PermissionError:
            continue
        visible.append(tool)
    return visible


def check_model_restriction(env, user, model_name, operation):
    """Raise PermissionError if model/operation is restricted for this user."""
    if not model_name:
        return
    if is_mcp_admin(user):
        return  # Admin bypasses model restrictions
    operation_map = {
        'read': 'block_read',
        'create': 'block_create',
        'write': 'block_write',
        'unlink': 'block_unlink',
        'execute': 'block_execute',
    }
    block_attr = operation_map.get(operation)
    if not block_attr:
        return
    ir_model = env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)
    if not ir_model:
        return
    Group = env['mcp.model.group'].sudo()
    groups = Group.search([('active', '=', True)])
    for g in groups:
        if g.user_ids and user.id not in g.user_ids.ids:
            continue
        for line in g.line_ids:
            if line.model_id.id == ir_model.id:
                if getattr(line, block_attr, False):
                    raise PermissionError(
                        f"Access to model '{model_name}' ({operation}) is restricted by "
                        f"security policy '{g.name}'. Contact your MCP administrator."
                    )
                return  # Found matching group
    return


def get_restricted_field_names(env, user, model_name, operation='read'):
    """
    Return a set of field names that are restricted for this user/model/operation.
    Used by tools to pre-filter fields before querying Odoo.
    """
    if not model_name:
        return set()
    if is_mcp_admin(user):
        return set()  # Admin sees everything
    ir_model = env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)
    if not ir_model:
        return set()

    hidden = set()
    op_attr = f'block_{operation}' if operation != 'unlink' else 'block_write'

    Group = env['mcp.model.group'].sudo()
    for g in Group.search([('active', '=', True)]):
        # Skip groups that don't apply to this user
        if g.user_ids and user.id not in g.user_ids.ids:
            continue
        for line in g.line_ids:
            if line.model_id.id == ir_model.id:
                for fr in line.field_ids:
                    if getattr(fr, op_attr, True):
                        hidden.add(fr.field_name)
                break  # Only process first matching model line per group
    return hidden


def apply_field_restrictions(env, user, model_name, data, operation='read'):
    """Remove restricted fields from data (list of dicts or single dict)."""
    if not data:
        return data

    hidden = get_restricted_field_names(env, user, model_name, operation)
    if not hidden:
        return data

    single = isinstance(data, dict)
    items = [data] if single else data
    for item in items:
        if isinstance(item, dict):
            for k in hidden:
                item.pop(k, None)
    return data


def check_field_write_restrictions(env, user, model_name, values, operation='create'):
    """
    Raise PermissionError if the values dict contains any restricted fields.
    Called before create/write to block AI from setting restricted fields.
    """
    if not values or not model_name:
        return
    if is_mcp_admin(user):
        return

    hidden = get_restricted_field_names(env, user, model_name, operation)
    if not hidden:
        return

    blocked = hidden & set(values.keys())
    if blocked:
        raise PermissionError(
            f"Cannot {operation} the following restricted field(s) on "
            f"'{model_name}': {', '.join(sorted(blocked))}. "
            f"Contact your MCP administrator to adjust field restrictions."
        )


def check_field_aggregation_restrictions(env, user, model_name, field_names):
    """
    Raise PermissionError if any aggregation/groupby field is restricted.
    """
    if not field_names or not model_name:
        return
    if is_mcp_admin(user):
        return

    hidden = get_restricted_field_names(env, user, model_name, 'read')
    if not hidden:
        return

    # Extract base field names (strip :sum, :count etc.)
    base_names = {f.split(':')[0] for f in field_names}
    blocked = hidden & base_names
    if blocked:
        raise PermissionError(
            f"Cannot aggregate on restricted field(s) in '{model_name}': "
            f"{', '.join(sorted(blocked))}. Contact your MCP administrator."
        )
