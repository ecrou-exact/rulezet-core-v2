"""connectors_core.py — Business logic for the Connectors feature."""
from datetime import datetime

from ... import db
from ...core.db_class.connector import Connector, CONNECTOR_DIRECTIONS
from ...core.db_class.tag import Tag
from ...core.utils.logger import log_action
from ...core.utils.job_runner import register_handler, enqueue_job


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_namespace(name: str) -> str | None:
    if ':' in name:
        return name.split(':')[0]
    return None


def _upsert_remote_tag(item: dict, connector: Connector):
    """Insert or update a tag received from a remote connector. Does NOT commit."""
    name = (item.get('name') or '').strip()
    if not name:
        return

    tag_meta = {
        'connector_uuid': connector.uuid,
        'connector_name': connector.name,
    }
    if item.get('meta'):
        tag_meta.update(item['meta'])

    existing = Tag.query.filter_by(name=name).first()
    if existing:
        existing.color       = item.get('color') or existing.color
        existing.description = item.get('description') or existing.description
        existing.icon        = item.get('icon') or existing.icon
        existing.is_active   = True
        existing.is_public   = True
        existing.meta        = tag_meta
    else:
        tag = Tag(
            name=name,
            description=item.get('description'),
            color=item.get('color') or '#6c757d',
            icon=item.get('icon'),
            source=item.get('source', 'custom'),
            namespace=item.get('namespace') or _parse_namespace(name),
            external_id=item.get('external_id'),
            is_public=True,
            meta=tag_meta,
        )
        db.session.add(tag)


# ── Read ──────────────────────────────────────────────────────────────────────

def list_connectors(status=None, is_active=True,
                    page=1, per_page=25, search='', sort='name', direction='asc'):
    q = Connector.query
    if is_active is not None:
        q = q.filter_by(is_active=is_active)
    if status:
        q = q.filter_by(status=status)
    if search:
        pattern = f'%{search}%'
        q = q.filter(
            db.or_(Connector.name.ilike(pattern), Connector.url.ilike(pattern),
                   Connector.description.ilike(pattern))
        )
    sort_col = {
        'name':         Connector.name,
        'status':       Connector.status,
        'direction':    Connector.direction,
        'last_sync_at': Connector.last_sync_at,
        'created_at':   Connector.created_at,
    }.get(sort, Connector.name)

    if direction == 'desc':
        q = q.order_by(sort_col.desc())
    else:
        q = q.order_by(sort_col.asc())

    total       = q.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    items       = q.offset((page - 1) * per_page).limit(per_page).all()
    return items, total, total_pages


def get_connector_by_uuid(uuid: str) -> Connector | None:
    return Connector.query.filter_by(uuid=uuid, is_active=True).first()


def get_connector_by_incoming_key(key: str) -> Connector | None:
    return Connector.query.filter_by(incoming_key=key, is_active=True).first()


# ── Create / Edit ─────────────────────────────────────────────────────────────

def create_connector_core(data: dict, user_id: int) -> tuple[Connector | None, str]:
    name = (data.get('name') or '').strip()
    url  = (data.get('url') or '').strip().rstrip('/')
    if not name:
        return None, 'Connector name is required.'
    if not url:
        return None, 'Remote URL is required.'
    if data.get('direction') not in CONNECTOR_DIRECTIONS:
        return None, f'Invalid direction. Must be one of: {", ".join(CONNECTOR_DIRECTIONS)}.'

    connector = Connector(
        name=name,
        description=data.get('description'),
        url=url,
        outgoing_key=data.get('outgoing_key') or None,
        direction=data.get('direction', 'pull'),
        sync_tags=bool(data.get('sync_tags', True)),
        created_by=user_id,
    )
    db.session.add(connector)
    db.session.commit()
    log_action(
        title=f'Connector created: {connector.name}',
        action='create',
        category='connectors',
        level='success',
        object_type='connector',
        object_id=connector.id,
        is_public=False,
        meta={'url': url, 'direction': connector.direction},
    )
    return connector, 'Connector created.'


def update_connector_core(uuid: str, data: dict, user_id: int) -> tuple[Connector | None, str]:
    connector = Connector.query.filter_by(uuid=uuid).first()
    if not connector:
        return None, 'Connector not found.'

    if 'name' in data:
        connector.name = (data['name'] or '').strip() or connector.name
    if 'description' in data:
        connector.description = data['description']
    if 'url' in data and data['url']:
        connector.url = data['url'].strip().rstrip('/')
    if 'outgoing_key' in data and data['outgoing_key'] and data['outgoing_key'] != '***':
        connector.outgoing_key = data['outgoing_key']
    if 'direction' in data and data['direction'] in CONNECTOR_DIRECTIONS:
        connector.direction = data['direction']
    if 'sync_tags' in data:
        connector.sync_tags = bool(data['sync_tags'])

    connector.updated_at = datetime.utcnow()
    db.session.commit()
    log_action(
        title=f'Connector updated: {connector.name}',
        action='edit',
        category='connectors',
        level='success',
        object_type='connector',
        object_id=connector.id,
        is_public=False,
        meta={'changed': list(data.keys())},
    )
    return connector, 'Connector updated.'


def delete_connector_core(uuid: str, user_id: int) -> tuple[bool, str]:
    connector = Connector.query.filter_by(uuid=uuid).first()
    if not connector:
        return False, 'Connector not found.'
    connector.is_active  = False
    connector.deleted_at = datetime.utcnow()
    connector.deleted_by = user_id
    db.session.commit()
    log_action(
        title=f'Connector deleted: {connector.name}',
        action='delete',
        category='connectors',
        level='warning',
        object_type='connector',
        object_id=connector.id,
        is_public=False,
    )
    return True, 'Connector deleted.'


# ── Incoming push ─────────────────────────────────────────────────────────────

def receive_push_core(incoming_key: str, data: dict) -> tuple[int, str]:
    """Handle an incoming data push from a remote connector."""
    connector = get_connector_by_incoming_key(incoming_key)
    if not connector:
        return -1, 'Invalid connector key.'
    if connector.direction not in ('push', 'bidirectional'):
        return -1, 'This connector is not configured to receive pushes.'

    tags_data = data.get('tags', [])
    count = 0
    for item in tags_data:
        _upsert_remote_tag(item, connector)
        count += 1

    if count:
        db.session.commit()
        connector.last_sync_at = datetime.utcnow()
        db.session.commit()
        log_action(
            title=f'Push received from connector: {connector.name}',
            action='create',
            category='connectors',
            level='info',
            object_type='connector',
            object_id=connector.id,
            is_public=False,
            meta={'tags_received': count, 'remote_name': data.get('source_name')},
        )
    return count, f'{count} tag(s) received.'


# ── Job enqueue ───────────────────────────────────────────────────────────────

def enqueue_connector_test(uuid: str, user_id: int):
    connector = get_connector_by_uuid(uuid)
    if not connector:
        return None
    return enqueue_job(
        'connectors.test',
        title=f'Test connection: {connector.name}',
        meta={'connector_uuid': uuid},
        user_id=user_id,
    )


def enqueue_connector_sync(uuid: str, user_id: int):
    connector = get_connector_by_uuid(uuid)
    if not connector:
        return None
    return enqueue_job(
        'connectors.sync',
        title=f'Sync: {connector.name}',
        meta={'connector_uuid': uuid},
        user_id=user_id,
    )


# ── Job handlers ──────────────────────────────────────────────────────────────

@register_handler('connectors.test')
def _handle_test(ctx, meta):
    import requests as req
    connector_uuid = meta.get('connector_uuid')
    connector = Connector.query.filter_by(uuid=connector_uuid).first()
    if not connector:
        raise ValueError(f'Connector {connector_uuid} not found')

    url = f'{connector.url}/api/tags/?per_page=1&is_active=1'
    headers = {'X-API-KEY': connector.outgoing_key or ''}
    ctx.log(f'Testing connection to {connector.url}…')

    try:
        resp = req.get(url, headers=headers, timeout=15)
        if resp.ok:
            connector.status       = 'online'
            connector.last_check_at = datetime.utcnow()
            db.session.commit()
            ctx.log(f'Connection OK — HTTP {resp.status_code}')
            return {'status': 'online', 'http_status': resp.status_code}
        else:
            connector.status       = 'error'
            connector.last_check_at = datetime.utcnow()
            db.session.commit()
            ctx.log(f'Remote returned HTTP {resp.status_code}', 'warning')
            return {'status': 'error', 'http_status': resp.status_code}
    except req.exceptions.ConnectionError:
        connector.status       = 'offline'
        connector.last_check_at = datetime.utcnow()
        db.session.commit()
        ctx.log(f'Connection refused or unreachable: {connector.url}', 'error')
        raise
    except req.exceptions.Timeout:
        connector.status       = 'offline'
        connector.last_check_at = datetime.utcnow()
        db.session.commit()
        ctx.log(f'Connection timed out after 15s', 'error')
        raise


@register_handler('connectors.sync')
def _handle_sync(ctx, meta):
    import requests as req
    connector_uuid = meta.get('connector_uuid')
    connector = Connector.query.filter_by(uuid=connector_uuid).first()
    if not connector:
        raise ValueError(f'Connector {connector_uuid} not found')

    if connector.direction == 'push':
        ctx.log('Push-only connector: remote initiates sync. Nothing to do on our side.')
        return {'tags_synced': 0, 'note': 'push-only'}

    tags_synced = 0

    if connector.sync_tags:
        ctx.log(f'Pulling tags from {connector.url}…')
        page = 1
        headers = {'X-API-KEY': connector.outgoing_key or ''}
        while True:
            ctx.checkpoint()
            url = f'{connector.url}/api/tags/?is_active=1&per_page=200&page={page}'
            try:
                resp = req.get(url, headers=headers, timeout=30)
            except req.exceptions.RequestException as e:
                connector.status = 'offline'
                db.session.commit()
                raise RuntimeError(f'Network error: {e}') from e

            if not resp.ok:
                connector.status = 'error'
                db.session.commit()
                raise RuntimeError(f'Remote returned HTTP {resp.status_code}')

            data       = resp.json()
            items      = data.get('items', [])
            total_pages = data.get('total_pages', 1)

            for item in items:
                _upsert_remote_tag(item, connector)
                tags_synced += 1

            db.session.commit()
            ctx.update_progress(int(page / max(total_pages, 1) * 100))
            ctx.log(f'Page {page}/{total_pages} — {tags_synced} tags synced so far')

            if page >= total_pages:
                break
            page += 1

    connector.status      = 'online'
    connector.last_sync_at = datetime.utcnow()
    connector.last_check_at = datetime.utcnow()
    db.session.commit()
    ctx.update_progress(100)
    ctx.log(f'Sync complete. {tags_synced} tag(s) imported/updated.')
    log_action(
        title=f'Sync completed: {connector.name}',
        action='create',
        category='connectors',
        level='success',
        object_type='connector',
        object_id=connector.id,
        is_public=False,
        meta={'tags_synced': tags_synced},
    )
    return {'tags_synced': tags_synced}
