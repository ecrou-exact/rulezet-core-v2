"""
tags_core.py — Business logic for the Tags feature.
"""
import hashlib
import json
import os
from datetime import datetime

from sqlalchemy import case as sa_case
from ... import db
from ...core.db_class.tag import Tag
from ...core.utils.logger import log_action
from ...core.utils.job_runner import register_handler, enqueue_job

TAXONOMY_DIR    = os.path.join(os.getcwd(), 'modules', 'misp-taxonomies')
GALAXY_DIR      = os.path.join(os.getcwd(), 'modules', 'misp-galaxy', 'clusters')
GALAXY_DEFS_DIR = os.path.join(os.getcwd(), 'modules', 'misp-galaxy', 'galaxies')

SOURCE_ICONS = {
    'custom':        'fa-user-tag',
    'taxonomy':      'fa-tag',
    'galaxy':        'fa-globe',
    'vulnerability': 'fa-bug',
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _galaxy_color(value: str) -> str:
    """Generate a deterministic HSL color from a string (MD5 hash)."""
    h = hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()
    hue = int(h[:2], 16) / 255 * 360
    return f"hsl({hue:.0f}, 72%, 52%)"


def _hsl_to_hex(hsl: str) -> str:
    """Convert hsl(...) string to #rrggbb for storage."""
    import re
    m = re.match(r'hsl\((\d+\.?\d*),\s*(\d+)%,\s*(\d+)%\)', hsl)
    if not m:
        return '#6c757d'
    h, s, l = float(m.group(1)) / 360, float(m.group(2)) / 100, float(m.group(3)) / 100

    def hue_to_rgb(p, q, t):
        if t < 0: t += 1
        if t > 1: t -= 1
        if t < 1/6: return p + (q - p) * 6 * t
        if t < 1/2: return q
        if t < 2/3: return p + (q - p) * (2/3 - t) * 6
        return p

    if s == 0:
        r = g = b = l
    else:
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = hue_to_rgb(p, q, h + 1/3)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1/3)
    return '#{:02x}{:02x}{:02x}'.format(int(r * 255), int(g * 255), int(b * 255))


def _galaxy_icon(cluster_name: str) -> str:
    """Read the predefined icon from the galaxy definition file."""
    path = os.path.join(GALAXY_DEFS_DIR, f'{cluster_name}.json')
    if os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            icon = data.get('icon')
            if icon:
                return icon if icon.startswith('fa-') else f'fa-{icon}'
        except Exception:
            pass
    return 'fa-globe'


def _list_taxonomies() -> list[dict]:
    """Return available taxonomy namespaces from submodule."""
    if not os.path.isdir(TAXONOMY_DIR):
        return []
    result = []
    for name in sorted(os.listdir(TAXONOMY_DIR)):
        path = os.path.join(TAXONOMY_DIR, name, 'machinetag.json')
        if os.path.isfile(path):
            result.append({'name': name, 'path': path})
    return result


def _list_galaxies() -> list[dict]:
    """Return available galaxy cluster files from submodule."""
    if not os.path.isdir(GALAXY_DIR):
        return []
    result = []
    for fname in sorted(os.listdir(GALAXY_DIR)):
        if fname.endswith('.json'):
            result.append({'name': fname[:-5], 'path': os.path.join(GALAXY_DIR, fname)})
    return result


# ── Read ──────────────────────────────────────────────────────────────────────

def list_tags(source=None, namespace=None, is_active=None, is_public=None,
              viewer_id=None, is_admin=False) -> list[Tag]:
    q = Tag.query
    if source:
        q = q.filter_by(source=source)
    if namespace:
        q = q.filter_by(namespace=namespace)
    if is_active is not None:
        q = q.filter_by(is_active=is_active)
    if is_public is not None:
        q = q.filter_by(is_public=is_public)
    if not is_admin and viewer_id:
        # Non-admins see: public tags + their own custom tags
        q = q.filter(
            db.or_(
                Tag.is_public == True,
                db.and_(Tag.source == 'custom', Tag.created_by == viewer_id)
            )
        )
    return q.order_by(Tag.namespace, Tag.name).all()


def list_tags_paginated(source=None, namespace=None, is_active=None, is_public=None,
                        viewer_id=None, is_admin=False,
                        page=1, per_page=25, search='', sort='name', direction='asc'):
    """Return (items, total, total_pages) with pagination, search, and sort."""
    q = Tag.query

    if source:
        q = q.filter_by(source=source)
    if namespace:
        q = q.filter_by(namespace=namespace)
    if is_active is not None:
        q = q.filter_by(is_active=is_active)
    if is_public is not None:
        q = q.filter_by(is_public=is_public)
    if not is_admin and viewer_id:
        q = q.filter(
            db.or_(
                Tag.is_public == True,
                db.and_(Tag.source == 'custom', Tag.created_by == viewer_id)
            )
        )
    if search:
        pattern = f'%{search}%'
        q = q.filter(
            db.or_(Tag.name.ilike(pattern), Tag.description.ilike(pattern),
                   Tag.namespace.ilike(pattern))
        )

    sort_col = {
        'name':       Tag.name,
        'namespace':  Tag.namespace,
        'source':     Tag.source,
        'created_at': Tag.created_at,
        'is_active':  Tag.is_active,
    }.get(sort, Tag.name)

    if search:
        # Namespace-exact match first, then namespace-prefix, then rest
        ns_priority = sa_case(
            (Tag.namespace.ilike(search), 0),
            (Tag.namespace.ilike(f'{search}%'), 1),
            else_=2,
        )
        if direction == 'desc':
            q = q.order_by(ns_priority, sort_col.desc())
        else:
            q = q.order_by(ns_priority, sort_col.asc())
    else:
        if direction == 'desc':
            q = q.order_by(sort_col.desc())
        else:
            q = q.order_by(sort_col.asc())

    total = q.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return items, total, total_pages


def get_tag_by_uuid(uuid: str) -> Tag | None:
    return Tag.query.filter_by(uuid=uuid, is_active=True).first()


def get_available_namespaces() -> list[str]:
    rows = db.session.query(Tag.namespace).filter(
        Tag.is_active == True, Tag.namespace.isnot(None)
    ).distinct().order_by(Tag.namespace).all()
    return [r[0] for r in rows]


# ── Create / Edit ─────────────────────────────────────────────────────────────

def create_tag_core(data: dict, user_id: int) -> tuple[Tag | None, str]:
    name = (data.get('name') or '').strip()
    if not name:
        return None, 'Tag name is required.'
    if Tag.query.filter_by(name=name).first():
        return None, f'Tag "{name}" already exists.'

    color = data.get('color') or '#6c757d'
    source = data.get('source', 'custom')
    icon = data.get('icon') or SOURCE_ICONS.get(source, 'fa-tag')

    tag = Tag(
        name=name,
        description=data.get('description'),
        color=color,
        icon=icon,
        source=source,
        namespace=data.get('namespace') or _parse_namespace(name),
        external_id=data.get('external_id'),
        is_public=bool(data.get('is_public', False)),
        created_by=user_id,
        meta=data.get('meta'),
    )
    db.session.add(tag)
    db.session.commit()
    log_action(
        title=f'Tag created: {tag.name}',
        action='create',
        category='tags',
        level='success',
        object_type='tag',
        object_id=tag.id,
        is_public=tag.is_public,
        meta={'source': tag.source, 'namespace': tag.namespace},
    )
    return tag, 'Tag created.'


def update_tag_core(uuid: str, data: dict, user_id: int) -> tuple[Tag | None, str]:
    tag = Tag.query.filter_by(uuid=uuid).first()
    if not tag:
        return None, 'Tag not found.'

    if 'name' in data and data['name'] != tag.name:
        if Tag.query.filter_by(name=data['name']).first():
            return None, f'Tag "{data["name"]}" already exists.'
        tag.name = data['name']
        tag.namespace = _parse_namespace(tag.name)

    if 'description' in data:
        tag.description = data['description']
    if 'color' in data:
        tag.color = data['color']
    if 'icon' in data:
        tag.icon = data['icon']
    if 'is_public' in data:
        tag.is_public = bool(data['is_public'])
    if 'is_active' in data:
        tag.is_active = bool(data['is_active'])
        if not tag.is_active:
            tag.deleted_at = datetime.utcnow()
            tag.deleted_by = user_id

    tag.updated_at = datetime.utcnow()
    db.session.commit()
    log_action(
        title=f'Tag updated: {tag.name}',
        action='edit',
        category='tags',
        level='success',
        object_type='tag',
        object_id=tag.id,
        is_public=False,
        meta={'changed': list(data.keys())},
    )
    return tag, 'Tag updated.'


def delete_tag_core(uuid: str, user_id: int) -> tuple[bool, str]:
    tag = Tag.query.filter_by(uuid=uuid).first()
    if not tag:
        return False, 'Tag not found.'
    tag.is_active  = False
    tag.deleted_at = datetime.utcnow()
    tag.deleted_by = user_id
    db.session.commit()
    log_action(
        title=f'Tag deleted: {tag.name}',
        action='delete',
        category='tags',
        level='warning',
        object_type='tag',
        object_id=tag.id,
        is_public=False,
    )
    return True, 'Tag deleted.'


def bulk_action_core(action: str, uuids: list[str], user_id: int) -> tuple[int, str]:
    tags = Tag.query.filter(Tag.uuid.in_(uuids)).all()
    count = 0
    for tag in tags:
        if action == 'activate':
            tag.is_active  = True
            tag.deleted_at = None
            tag.deleted_by = None
        elif action == 'deactivate':
            tag.is_active  = False
            tag.deleted_at = datetime.utcnow()
            tag.deleted_by = user_id
        elif action == 'delete':
            tag.is_active  = False
            tag.deleted_at = datetime.utcnow()
            tag.deleted_by = user_id
        count += 1

    if count:
        db.session.commit()
        log_action(
            title=f'Bulk {action}: {count} tag(s)',
            action=f'bulk_{action}',
            category='tags',
            level='warning' if action != 'activate' else 'success',
            is_public=False,
            meta={'count': count, 'uuids': uuids[:50]},
        )
    return count, f'{count} tag(s) {action}d.'


# ── Namespace parsing ─────────────────────────────────────────────────────────

def _parse_namespace(name: str) -> str | None:
    """Extract namespace from tag name: 'tlp:red' → 'tlp'."""
    if ':' in name:
        return name.split(':')[0]
    return None


# ── Available imports ─────────────────────────────────────────────────────────

def get_import_sources() -> dict:
    return {
        'taxonomies': _list_taxonomies(),
        'galaxies':   _list_galaxies(),
    }


# ── Import jobs ───────────────────────────────────────────────────────────────

def enqueue_taxonomy_import(namespace: str, user_id: int):
    """Enqueue a background job to import a taxonomy namespace."""
    job = enqueue_job(
        'tags.import_taxonomy',
        title=f'Import taxonomy: {namespace}',
        meta={'namespace': namespace},
        user_id=user_id,
    )
    return job


def enqueue_galaxy_import(cluster_name: str, user_id: int):
    """Enqueue a background job to import a galaxy cluster."""
    job = enqueue_job(
        'tags.import_galaxy',
        title=f'Import galaxy: {cluster_name}',
        meta={'cluster_name': cluster_name},
        user_id=user_id,
    )
    return job


def enqueue_all_taxonomies_import(user_id: int):
    job = enqueue_job(
        'tags.import_all_taxonomies',
        title='Import all taxonomies',
        meta={},
        user_id=user_id,
    )
    return job


def enqueue_all_galaxies_import(user_id: int):
    job = enqueue_job(
        'tags.import_all_galaxies',
        title='Import all galaxy clusters',
        meta={},
        user_id=user_id,
    )
    return job


# ── Job handlers ──────────────────────────────────────────────────────────────

@register_handler('tags.import_taxonomy')
def _handle_import_taxonomy(ctx, meta):
    namespace = meta.get('namespace')
    path = os.path.join(TAXONOMY_DIR, namespace, 'machinetag.json')
    if not os.path.isfile(path):
        raise FileNotFoundError(f'Taxonomy not found: {namespace}')

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    ns = data.get('namespace', namespace)
    predicates = {p['value']: p for p in data.get('predicates', [])}
    values_map  = {}
    for vblock in data.get('values', []):
        values_map[vblock['predicate']] = vblock.get('entry', [])

    total   = len(predicates)
    created = 0
    skipped = 0

    ctx.log(f'Importing taxonomy "{ns}" — {total} predicates')
    for i, (pred_val, pred) in enumerate(predicates.items()):
        ctx.checkpoint()
        ctx.update_progress(int(i / max(total, 1) * 100))

        entries = values_map.get(pred_val, [])
        if entries:
            for entry in entries:
                tag_name = f'{ns}:{pred_val}="{entry["value"]}"'
                color    = entry.get('colour') or pred.get('colour') or '#6c757d'
                desc     = entry.get('expanded') or entry.get('description') or pred.get('description')
                _upsert_tag(tag_name, desc, color, 'taxonomy', ns, None)
                created += 1
        else:
            tag_name = f'{ns}:{pred_val}'
            color    = pred.get('colour') or '#6c757d'
            desc     = pred.get('expanded') or pred.get('description')
            _upsert_tag(tag_name, desc, color, 'taxonomy', ns, pred.get('uuid'))
            created += 1

    db.session.commit()
    ctx.update_progress(100)
    ctx.log(f'Done: {created} tags imported, {skipped} skipped.')
    log_action(
        title=f'Taxonomy imported: {ns}',
        action='create',
        category='tags',
        level='success',
        is_public=True,
        meta={'namespace': ns, 'count': created},
    )
    return {'created': created, 'skipped': skipped}


@register_handler('tags.import_galaxy')
def _handle_import_galaxy(ctx, meta):
    cluster_name = meta.get('cluster_name')
    path = os.path.join(GALAXY_DIR, f'{cluster_name}.json')
    if not os.path.isfile(path):
        raise FileNotFoundError(f'Galaxy cluster not found: {cluster_name}')

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    galaxy_type = data.get('type', cluster_name)
    values      = data.get('values', [])
    total       = len(values)
    created     = 0
    icon        = _galaxy_icon(cluster_name)

    ctx.log(f'Importing galaxy "{galaxy_type}" — {total} entries')
    for i, entry in enumerate(values):
        ctx.checkpoint()
        ctx.update_progress(int(i / max(total, 1) * 100))

        val      = entry.get('value', '')
        tag_name = f'misp-galaxy:{galaxy_type}="{val}"'
        color    = _hsl_to_hex(_galaxy_color(val))
        desc     = entry.get('description')
        ext_id   = entry.get('uuid')
        galaxy_meta = entry.get('meta', {})

        _upsert_tag(
            tag_name, desc, color, 'galaxy', galaxy_type, ext_id,
            icon=icon,
            meta={'galaxy_meta': galaxy_meta, 'cluster': cluster_name},
        )
        created += 1

    db.session.commit()
    ctx.update_progress(100)
    ctx.log(f'Done: {created} galaxy tags imported.')
    log_action(
        title=f'Galaxy cluster imported: {galaxy_type}',
        action='create',
        category='tags',
        level='success',
        is_public=True,
        meta={'type': galaxy_type, 'count': created},
    )
    return {'created': created}


@register_handler('tags.import_all_taxonomies')
def _handle_import_all_taxonomies(ctx, meta):
    taxonomies = _list_taxonomies()
    total  = len(taxonomies)
    done   = 0
    errors = []

    ctx.log(f'Importing {total} taxonomy namespaces…')
    for i, t in enumerate(taxonomies):
        ctx.checkpoint()
        ctx.update_progress(int(i / max(total, 1) * 100))
        try:
            _import_taxonomy_inline(t['name'], t['path'], ctx)
            done += 1
        except Exception as e:
            errors.append(f'{t["name"]}: {e}')
            ctx.log(f'Error importing {t["name"]}: {e}', 'warning')

    db.session.commit()
    ctx.update_progress(100)
    ctx.log(f'Done: {done}/{total} taxonomies imported. Errors: {len(errors)}')
    return {'done': done, 'total': total, 'errors': errors}


@register_handler('tags.import_all_galaxies')
def _handle_import_all_galaxies(ctx, meta):
    galaxies = _list_galaxies()
    total  = len(galaxies)
    done   = 0
    errors = []

    ctx.log(f'Importing {total} galaxy clusters…')
    for i, g in enumerate(galaxies):
        ctx.checkpoint()
        ctx.update_progress(int(i / max(total, 1) * 100))
        try:
            _import_galaxy_inline(g['name'], g['path'], ctx)
            done += 1
        except Exception as e:
            errors.append(f'{g["name"]}: {e}')
            ctx.log(f'Error importing {g["name"]}: {e}', 'warning')

    db.session.commit()
    ctx.update_progress(100)
    ctx.log(f'Done: {done}/{total} galaxy clusters imported. Errors: {len(errors)}')
    return {'done': done, 'total': total, 'errors': errors}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _upsert_tag(name, description, color, source, namespace, external_id,
                icon=None, meta=None):
    """Insert or update a tag by name. Does NOT commit — caller must commit."""
    existing = Tag.query.filter_by(name=name).first()
    if existing:
        existing.color       = color or existing.color
        existing.description = description or existing.description
        existing.icon        = icon or existing.icon
        existing.is_active   = True
        existing.is_public   = True
        if meta:
            existing.meta = meta
        return existing

    tag = Tag(
        name=name,
        description=description,
        color=color,
        icon=icon or SOURCE_ICONS.get(source, 'fa-tag'),
        source=source,
        namespace=namespace,
        external_id=external_id,
        is_public=True,
        meta=meta,
    )
    db.session.add(tag)
    return tag


def _import_taxonomy_inline(namespace, path, ctx):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    ns         = data.get('namespace', namespace)
    predicates = {p['value']: p for p in data.get('predicates', [])}
    values_map = {}
    for vblock in data.get('values', []):
        values_map[vblock['predicate']] = vblock.get('entry', [])

    for pred_val, pred in predicates.items():
        entries = values_map.get(pred_val, [])
        if entries:
            for entry in entries:
                tag_name = f'{ns}:{pred_val}="{entry["value"]}"'
                color    = entry.get('colour') or pred.get('colour') or '#6c757d'
                desc     = entry.get('expanded') or entry.get('description') or pred.get('description')
                _upsert_tag(tag_name, desc, color, 'taxonomy', ns, None)
        else:
            tag_name = f'{ns}:{pred_val}'
            color    = pred.get('colour') or '#6c757d'
            desc     = pred.get('expanded') or pred.get('description')
            _upsert_tag(tag_name, desc, color, 'taxonomy', ns, pred.get('uuid'))


def _import_galaxy_inline(cluster_name, path, ctx):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    galaxy_type = data.get('type', cluster_name)
    values      = data.get('values', [])
    icon        = _galaxy_icon(cluster_name)
    for entry in values:
        val      = entry.get('value', '')
        tag_name = f'misp-galaxy:{galaxy_type}="{val}"'
        color    = _hsl_to_hex(_galaxy_color(val))
        desc     = entry.get('description')
        ext_id   = entry.get('uuid')
        galaxy_meta = entry.get('meta', {})
        _upsert_tag(
            tag_name, desc, color, 'galaxy', galaxy_type, ext_id,
            icon=icon,
            meta={'galaxy_meta': galaxy_meta, 'cluster': cluster_name},
        )
