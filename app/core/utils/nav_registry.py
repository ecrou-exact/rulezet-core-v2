"""
nav_registry.py — Single source of truth for all navigation items.

To add a new section to the nav + search bar:
  1. Add an entry to NAV below.
  2. That's it. Nav, search bar, and sidebar all update automatically.

Permission values:
  None         → visible to all authenticated users
  'admin_only' → visible only if role.admin = True
  'admin_any'  → visible if is_admin OR has any admin-related permission
  'public'     → visible to everyone including anonymous users
  'key'        → visible if user has that permission key (or is admin)
"""

# Permissions that grant access to at least one admin section
_ADMIN_RELATED_PERMS = {
    'users.view', 'users.edit', 'users.delete',
    'admin.roles', 'admin.site_config',
    'logs.view', 'logs.delete',
    'jobs.manage',
    'tags.view', 'tags.manage',
    'template_studio.manage',
    'connectors.view', 'connectors.manage',
}

NAV: list[dict] = [

    # ── Navigation (all authenticated users) ──────────────────────────────
    {
        'group':      'Navigation',
        'label':      'Home',
        'icon':       'fa-house',
        'href':       '/',
        'permission': None,
    },
    {
        'group':      'Navigation',
        'label':      'Account',
        'icon':       'fa-user',
        'href':       '/account/',
        'permission': None,
    },
    {
        'group':      'Navigation',
        'label':      'Settings',
        'icon':       'fa-gear',
        'href':       '/settings',
        'permission': None,
    },

    # ── Admin (single entry — only shown when user has at least one admin perm) ─
    {
        'group':      'Admin',
        'label':      'Admin',
        'icon':       'fa-shield-halved',
        'href':       '/admin/',
        'permission': 'admin_any',
    },

    # ── Community (public — accessible without login) ──────────────────────────
    {
        'group':      'Community',
        'label':      'Forum',
        'icon':       'fa-comments',
        'href':       '/comments/',
        'permission': 'public',
    },
    {
        'group':      'Community',
        'label':      'Component Lab',
        'icon':       'fa-flask',
        'href':       '/lab/components',
        'permission': 'public',
    },

]


def get_nav_for_user(is_admin: bool, perms: list[str], is_authenticated: bool = True) -> list[dict]:
    """Return the nav items visible to a user with the given permissions."""
    result = []
    for item in NAV:
        p = item.get('permission')
        if p == 'public':
            visible = True
        elif not is_authenticated:
            visible = False
        elif p is None:
            visible = True
        elif p == 'admin_only':
            visible = is_admin
        elif p == 'admin_any':
            visible = is_admin or bool(_ADMIN_RELATED_PERMS & set(perms))
        else:
            visible = is_admin or p in perms
        if visible:
            result.append(item)
    return result
