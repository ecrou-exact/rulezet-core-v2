from ..db_class.user import User, Role, db
from ..db_class.config import UserConfig
from .utils import generate_api_key


def _create_config(user):
    config = UserConfig(user_id=user.id, created_by=user.id)
    db.session.add(config)
    db.session.commit()


def _seed_roles():
    admin_role = Role.query.filter_by(name='Admin').first()
    if not admin_role:
        admin_role = Role(
            name='Admin',
            description='Full access — bypasses all permission checks.',
            admin=True,
            read_only=False,
            protected=True,
            color='brand',
            icon='fa-shield-halved',
        )
        db.session.add(admin_role)

    editor_role = Role.query.filter_by(name='Editor').first()
    if not editor_role:
        editor_role = Role(
            name='Editor',
            description='Can create and edit content.',
            admin=False,
            read_only=False,
            protected=False,
            color='blue',
            icon='fa-pen',
        )
        db.session.add(editor_role)

    read_only_role = Role.query.filter_by(name='Read Only').first()
    if not read_only_role:
        read_only_role = Role(
            name='Read Only',
            description='View-only access. Default fallback role.',
            admin=False,
            read_only=True,
            protected=True,
            color='gray',
            icon='fa-eye',
        )
        db.session.add(read_only_role)

    db.session.commit()
    return admin_role, editor_role, read_only_role


def create_admin():
    admin_role, _, _ = _seed_roles()

    user = User(
        first_name='admin',
        last_name='admin',
        email='admin@admin.admin',
        password='admin',
        role_id=admin_role.id,
        api_key=generate_api_key(),
        is_superadmin=True,
    )
    db.session.add(user)
    db.session.commit()
    _create_config(user)


def create_user_test():
    admin_role, editor_role, read_only_role = _seed_roles()

    admin = User(
        first_name='admin', last_name='admin',
        email='admin@admin.admin', password='admin',
        role_id=admin_role.id, api_key='admin_api_key',
        is_superadmin=True,
    )
    db.session.add(admin)
    db.session.commit()
    _create_config(admin)

    editor = User(
        first_name='editor', last_name='editor',
        email='editor@editor.editor', password='editor',
        role_id=editor_role.id, api_key='editor_api_key',
    )
    db.session.add(editor)
    db.session.commit()
    _create_config(editor)

    reader = User(
        first_name='read', last_name='read',
        email='read@read.read', password='read',
        role_id=read_only_role.id, api_key='read_api_key',
    )
    db.session.add(reader)
    db.session.commit()
    _create_config(reader)
