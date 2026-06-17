"""template_studio_core.py — CRUD for PageDefinition (Template Studio)."""
import re
from datetime import datetime
from flask_login import current_user
from ... import db
from ...core.db_class.page_definition import PageDefinition
from ...core.db_class.comment import Comment
from ...core.utils.logger import log_action


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')


def get_page_or_none(uuid_val: str) -> PageDefinition | None:
    return PageDefinition.query.filter_by(uuid=uuid_val, is_active=True).first()


def get_page_by_slug(slug: str) -> PageDefinition | None:
    return PageDefinition.query.filter_by(slug=slug, is_active=True, is_published=True).first()


def list_pages_core() -> list[PageDefinition]:
    return (
        PageDefinition.query
        .filter_by(is_active=True)
        .order_by(PageDefinition.created_at.desc())
        .all()
    )


def create_page_core(data: dict) -> tuple[PageDefinition | None, str]:
    name = (data.get('name') or '').strip()
    if not name:
        return None, 'Name is required'

    slug = _slugify((data.get('slug') or '').strip() or name)
    if not slug:
        return None, 'Invalid slug'

    if PageDefinition.query.filter_by(slug=slug, is_active=True).first():
        return None, f"A page with slug '{slug}' already exists"

    page = PageDefinition(
        name=name,
        description=(data.get('description') or '').strip(),
        slug=slug,
        nav_group=data.get('nav_group') or None,
        nav_label=(data.get('nav_label') or name).strip(),
        nav_icon=(data.get('nav_icon') or 'fa-file').strip(),
        required_permission=data.get('required_permission') or None,
        sections=data.get('sections') or [],
        is_published=False,
        created_by=current_user.id,
    )
    db.session.add(page)
    db.session.commit()

    log_action(
        title=f"Page '{name}' created",
        action='create',
        category='template_studio',
        level='success',
        object_type='page_definition',
        object_id=page.id,
        is_public=False,
    )
    return page, 'Page created'


def update_page_core(uuid_val: str, data: dict) -> tuple[PageDefinition | None, str]:
    page = get_page_or_none(uuid_val)
    if not page:
        return None, 'Page not found'

    name = (data.get('name') or '').strip()
    if not name:
        return None, 'Name is required'

    slug = _slugify((data.get('slug') or '').strip() or name)
    if not slug:
        return None, 'Invalid slug'

    conflict = (
        PageDefinition.query
        .filter_by(slug=slug, is_active=True)
        .filter(PageDefinition.uuid != uuid_val)
        .first()
    )
    if conflict:
        return None, f"A page with slug '{slug}' already exists"

    page.name                = name
    page.description         = (data.get('description') or '').strip()
    page.slug                = slug
    page.nav_group           = data.get('nav_group') or None
    page.nav_label           = (data.get('nav_label') or name).strip()
    page.nav_icon            = (data.get('nav_icon') or 'fa-file').strip()
    page.required_permission = data.get('required_permission') or None
    page.sections            = data.get('sections') or []
    db.session.commit()

    log_action(
        title=f"Page '{name}' updated",
        action='edit',
        category='template_studio',
        level='success',
        object_type='page_definition',
        object_id=page.id,
        is_public=False,
    )
    return page, 'Page saved'


def publish_page_core(uuid_val: str) -> tuple[bool, str]:
    page = get_page_or_none(uuid_val)
    if not page:
        return False, 'Page not found'
    page.is_published = True
    db.session.commit()
    log_action(
        title=f"Page '{page.name}' published",
        action='edit',
        category='template_studio',
        level='success',
        object_type='page_definition',
        object_id=page.id,
        is_public=False,
    )
    return True, 'Page published'


def unpublish_page_core(uuid_val: str) -> tuple[bool, str]:
    page = get_page_or_none(uuid_val)
    if not page:
        return False, 'Page not found'
    page.is_published = False
    db.session.commit()
    log_action(
        title=f"Page '{page.name}' unpublished",
        action='edit',
        category='template_studio',
        level='warning',
        object_type='page_definition',
        object_id=page.id,
        is_public=False,
    )
    return True, 'Page unpublished'


def delete_page_core(uuid_val: str) -> tuple[bool, str]:
    page = get_page_or_none(uuid_val)
    if not page:
        return False, 'Page not found'
    page.is_active  = False
    page.deleted_at = datetime.utcnow()
    page.deleted_by = current_user.id
    db.session.commit()
    log_action(
        title=f"Page '{page.name}' deleted",
        action='delete',
        category='template_studio',
        level='warning',
        object_type='page_definition',
        object_id=page.id,
        is_public=False,
    )
    return True, 'Page deleted'


def hard_delete_page_core(uuid_val: str) -> tuple[bool, str]:
    """Permanently removes the page and any comments attached to its comment sections."""
    page = PageDefinition.query.filter_by(uuid=uuid_val).first()
    if not page:
        return False, 'Page not found'

    name    = page.name
    page_id = page.id

    # Cascade: remove comments bound to any comments section on this page
    for section in (page.sections or []):
        if section.get('type') == 'comments':
            cfg = section.get('config') or {}
            ot  = cfg.get('object_type')
            oid = cfg.get('object_id')
            if ot and oid:
                Comment.query.filter_by(object_type=ot, object_id=int(oid)).delete()

    log_action(
        title=f"Page '{name}' permanently deleted",
        action='hard_delete',
        category='template_studio',
        level='warning',
        object_type='page_definition',
        object_id=page_id,
        is_public=False,
    )
    db.session.delete(page)
    db.session.commit()
    return True, f"Page '{name}' permanently deleted"
