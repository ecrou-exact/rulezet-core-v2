"""
permissions.py — Central permission registry.

To add a new permission:
  1. Add an entry to PERMISSIONS below.
  2. That's it. It appears in the role editor UI automatically.

To protect a route:
  @permission_required('users.edit')
  def my_view(): ...

Admins (role.admin = True) bypass all permission checks.
"""

PERMISSIONS: dict[str, dict] = {

    # ── Admin ──────────────────────────────────────────────────────────────
    'admin.site_config': {
        'label':       'Manage site settings',
        'description': 'Change site-wide config (registration, login lock…)',
        'group':       'Admin',
        'icon':        'fa-sliders',
    },
    'admin.roles': {
        'label':       'Manage roles',
        'description': 'Create, edit and delete roles and their permissions.',
        'group':       'Admin',
        'icon':        'fa-shield-halved',
    },

    # ── Users ───────────────────────────────────────────────────────────────
    'users.view': {
        'label':       'View users',
        'description': 'See the user list and public profiles.',
        'group':       'Users',
        'icon':        'fa-users',
    },
    'users.edit': {
        'label':       'Edit users',
        'description': 'Edit profiles, roles, and verification status.',
        'group':       'Users',
        'icon':        'fa-user-pen',
    },
    'users.delete': {
        'label':       'Delete users',
        'description': 'Remove user accounts.',
        'group':       'Users',
        'icon':        'fa-user-minus',
    },

    # ── Logs ────────────────────────────────────────────────────────────────
    'logs.view': {
        'label':       'View logs',
        'description': 'Access the application log viewer.',
        'group':       'Logs',
        'icon':        'fa-scroll',
    },
    'logs.delete': {
        'label':       'Delete logs',
        'description': 'Delete individual or bulk log entries.',
        'group':       'Logs',
        'icon':        'fa-trash',
    },

    # ── Jobs ─────────────────────────────────────────────────────────────────
    'jobs.view': {
        'label':       'View jobs',
        'description': 'View background jobs (own jobs only).',
        'group':       'Jobs',
        'icon':        'fa-gears',
    },
    'jobs.manage': {
        'label':       'Manage jobs',
        'description': 'View all jobs, cancel, pause, resume, retry, and delete.',
        'group':       'Jobs',
        'icon':        'fa-sliders',
    },

    # ── Template Studio ──────────────────────────────────────────────────────
    'template_studio.manage': {
        'label':       'Manage Template Studio',
        'description': 'Create, edit, publish and delete dynamic pages (admin only by default).',
        'group':       'Template Studio',
        'icon':        'fa-wand-magic-sparkles',
    },

    # ── Tags ─────────────────────────────────────────────────────────────────
    'tags.view': {
        'label':       'View tags',
        'description': 'Access the tag list.',
        'group':       'Tags',
        'icon':        'fa-tags',
    },
    'tags.manage': {
        'label':       'Manage tags',
        'description': 'Create, edit, delete tags and import taxonomies/galaxies.',
        'group':       'Tags',
        'icon':        'fa-tag',
    },

    # ── Connectors ───────────────────────────────────────────────────────────
    'connectors.view': {
        'label':       'View connectors',
        'description': 'See the connector list and status.',
        'group':       'Connectors',
        'icon':        'fa-plug',
    },
    'connectors.manage': {
        'label':       'Manage connectors',
        'description': 'Create, edit, delete connectors and trigger sync/test jobs.',
        'group':       'Connectors',
        'icon':        'fa-plug',
    },

    # ── Comments ─────────────────────────────────────────────────────────────
    'comments.view': {
        'label':       'View comments',
        'group':       'Comments',
        'icon':        'fa-comments',
    },
    'comments.create': {
        'label':       'Post comments',
        'group':       'Comments',
        'icon':        'fa-comment-medical',
    },
    'comments.edit_own': {
        'label':       'Edit own comments',
        'group':       'Comments',
        'icon':        'fa-pen-to-square',
    },
    'comments.delete_own': {
        'label':       'Delete own comments',
        'group':       'Comments',
        'icon':        'fa-trash',
    },
    'comments.moderate': {
        'label':       'Moderate comments',
        'description': 'Delete/restore any comment, see private comments',
        'group':       'Comments',
        'icon':        'fa-shield-halved',
    },

}


def get_by_group() -> dict[str, list]:
    """Return permissions grouped by their 'group' key, preserving insertion order."""
    groups: dict[str, list] = {}
    for key, perm in PERMISSIONS.items():
        g = perm.get('group', 'Other')
        if g not in groups:
            groups[g] = []
        groups[g].append({'key': key, **perm})
    return groups


def all_keys() -> list[str]:
    return list(PERMISSIONS.keys())
