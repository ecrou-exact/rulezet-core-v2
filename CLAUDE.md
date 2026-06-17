# Flask Launchpad — Codebase Guide

## Rules

- No DB in routes. No logs in routes. Route calls core, core does everything.
- Every route has a decorator. No naked route ever.
- Every feature has a flag to enable/disable it without a deploy.
- Every feature works with the role system: read-only users can only view, edit-role users can create/edit/delete. Always enforce this via `hasPerm()` on every page and every API endpoint.
- Every action that changes data gets a `log_action` call in core: create, edit, delete, restore, hard_delete, every bulk action.
- Reuse existing components before creating anything new. Check `static/js/components/` and `static/css/` first.
- Every feature and every route gets tests. Tests must cover all roles: admin, editor, read-only, anonymous. Read-only must be blocked from write actions.
- Every HTML route that reads or writes data has a matching API endpoint. Register it in `api.py`.
- Soft delete only from user actions. Hard delete from admin trash only.
- No hardcoded colors. No `console.log`. No `{{ var | safe }}` on user data.
- Run `bandit -r app/` and `./launch.sh --test` before declaring done.
- Update `CLAUDE.md` after every new feature.
- Write code so the next change is simple: logic in core, access in decorators, config in flags.
- Before writing a feature, ask: can I update it without touching the route or template? If no, rethink.

---

## Environment

The app loads `.env` at startup via `python-dotenv`. If `.env` doesn't exist, the app still runs with defaults. Admins can edit SMTP config and regenerate the session key live from `/admin/settings` — SMTP takes effect immediately, SECRET_KEY requires a restart.

```
.env keys (project root):
  SECRET_KEY         — Flask session secret (auto-generated on first setup)
  FLASK_HOST         — Bind address (default 127.0.0.1); 0.0.0.0 = all interfaces
  FLASK_PORT         — Listen port (default 7009)
  SMTP_HOST          — SMTP server hostname
  SMTP_PORT          — SMTP port (default 587)
  SMTP_USER          — SMTP username / sender address
  SMTP_PASSWORD      — SMTP password (never committed, managed via admin UI)
  SMTP_SENDER        — Optional override sender address
  SMTP_USE_TLS       — 1 = STARTTLS (default), 0 = SSL
```

---

## Commands

| Command | What it does |
|---|---|
| `./launch.sh --setup` | First run: venv, deps, config, init DB |
| `./launch.sh --start` | Start dev server |
| `./launch.sh --test` | Run all tests |
| `./launch.sh --test -v tests/<feature>/` | Targeted tests |
| `./launch.sh --migrate "message"` | Create migration |
| `./launch.sh --upgrade` | Apply migrations |
| `./launch.sh --reload-db` | Drop + recreate DB |

Dev server: `http://127.0.0.1:7009` — Admin: `admin@admin.admin` / `admin`

Never call `python app.py` or `flask` directly.

---

## Architecture

```
app/
  __init__.py
  api/
    api.py                   # namespace registry
    <feature>_api.py
  core/
    db_class/                # models: user.py, log.py, config.py, site_config.py
    utils/
      decorators.py          # require_permission(key, public=False) — public=True bypasses all auth/perms
      utils.py               # form_to_dict, get_by_id_or_uuid
      logger.py              # log_action()
      mailer.py              # send_verification_email(), send_test_email() — reads SMTP from os.environ
      permissions.py         # all permission keys
      nav_registry.py        # nav + search (the only two files to edit for nav)
  features/
    account/                 # login, register, profile, verify (/account/verify), email-change verify
    admin/                   # user list, user detail, roles, logs (/admin/*)
    comments/                # forum + comment system (/comments/)
      comment.py             # route — comments.view
      comment_core.py        # CRUD + reactions + stats + profanity filter (better-profanity)
    site_settings/           # server settings admin page (/admin/settings)
      site_settings.py       # route — admin_only
        site_settings_core.py  # .env read/write, system info, SMTP/server config, session key regen, packages
                             # git submodule management: list, validate, add/update/remove (all via background jobs)
    config/                  # user preferences + Theme Studio (/settings)
    home/
    jobs/                    # background jobs (/jobs/, /jobs/<uuid>)
      jobs.py                # route — jobs.view / jobs.manage
      jobs_core.py           # CRUD, cancel, pause, resume, retry, bulk operations
    tags/                    # tag management (/tags/)
      tags.py                # route — tags.view
      tags_core.py           # CRUD, taxonomy import, galaxy import, bulk actions
                             # Job handlers: tags.import_taxonomy, tags.import_galaxy
                             #               tags.import_all_taxonomies, tags.import_all_galaxies
                             # Sources: modules/misp-taxonomies/, modules/misp-galaxy/clusters/
  core/
    db_class/
      comment.py             # Comment (threading: parent_id/depth/root_id, soft-delete) + CommentReaction
      custom_theme.py        # CustomTheme — custom + built-in overrides, is_public visibility
      job.py                 # Job — status, progress, logs, result, duration
      tag.py                 # Tag — source(custom|taxonomy|galaxy|vulnerability), color, icon, is_public
    utils/
      job_runner.py          # ThreadPoolExecutor daemon, JobContext, register_handler(), enqueue_job()
  api/
    api.py                   # namespace registry
    comment_api.py           # GET/POST /comments, PUT/DELETE /comments/<uuid>, /react, /restore, /stats/user/<id>
    site_settings_api.py     # GET/POST /server (host+port, triggers os.execv restart)
                             # GET /system, GET/POST /smtp, POST /smtp/test, POST /session-key
                             # GET /packages, POST /packages/update, POST /packages/install
                             # GET/POST /submodules, POST /submodules/update, POST /submodules/remove
    config_api.py            # GET/PATCH /config, GET/POST /config/themes, /themes/vars, /themes/builtin/<key>
                             # PUT/DELETE /themes/<uuid>, PATCH /themes/<uuid>/visibility
    jobs_api.py              # GET/POST /jobs, GET /jobs/types, GET/DELETE /jobs/<uuid>
                             # POST /jobs/<uuid>/cancel|pause|resume|retry, POST /jobs/bulk
    tags_api.py              # GET/POST /tags/, GET/PUT/DELETE /tags/<uuid>, POST /tags/bulk
                             # GET /tags/namespaces, GET /tags/import/sources
                             # POST /tags/import/taxonomy, POST /tags/import/galaxy
  templates/
    tags/index.html          # Tag admin page: data-table, source filter chips, import panel, create modal
    comments/forum.html      # Community Forum page using <comment-thread> Vue component
    site_settings/index.html # includes Python Packages + Git Submodules (add/update/remove via jobs)
    account/verify.html      # email verification code entry page
    account/verify_email_change.html  # email change confirmation page
    jobs/index.html          # Job list with data-table, status filter chips, inline actions
    jobs/detail.html         # Job detail: progress bar, live log panel (2s polling), action buttons
  static/
    css/comments/comments.css
    css/site_settings/site_settings.css
    css/jobs/jobs.css        # status badges, progress bars, log panel, detail grid
    css/tags/tags.css        # split pill, source chips, import panel, create modal
    css/themes/theme.css     # built-in theme overrides (static)
    css/themes/custom-themes.css  # auto-generated from DB (regenerated on every theme change)
    css/core.css             # includes .admin-tabs-bar / .admin-tab (inner nav for all admin pages)
    js/
      constants.js           # TOAST, CSRF_TOKEN, apiFetch()
      toaster.js             # create_message(text, type, not_hide, link) — link={href,label,target}
      job-monitor.js         # global floating job widget (separate Vue app on #job-monitor-widget)
      components/            # loading-bar.js, pagination.js, data-table.js
                             # comment-thread.js — recursive Vue component (infinite scroll, reactions, collapse)
                             # tag-pill.js — split pill display (left: dark icon+namespace, right: colored label, YIQ contrast)
    css/components/
      job-monitor.css        # floating widget: .jm-panel, .jm-header, .jm-body, .jm-logs

tests/<feature>/test_<feature>.py
```

---

## Core rules — never break these

**Routes never touch the DB.**
```python
# Route: parse input, call core, flash, redirect
data = form_to_dict(request.form)
obj, msg = create_item_core(data)
flash(msg)
return redirect(url_for('...'))

# Core: all DB logic, returns (obj, msg), logs here
def create_item_core(data):
    item = Item(**data)
    db.session.add(item)
    db.session.commit()
    log_action(...)
    return item, "Item created"
```

**Every route has an access decorator — no naked route.**
```python
@blueprint.route('/')
@login_required
def index(): ...

@blueprint.route('/admin')
@admin_required
def admin_view(): ...

@blueprint.route('/items')
@feature_required('items.view')
def items(): ...
```

**Every route that reads/writes data has a matching API endpoint.**
Edit `app/api/<feature>_api.py` and register the namespace in `api.py`.

**Deletion is always soft from user actions. Hard delete only from `/admin/<feature>/trash`.**
```python
# soft
item.is_active = False; item.deleted_at = now(); item.deleted_by = uid
# hard (admin trash only)
db.session.delete(item)
```

**URLs use UUIDs.** Routes accept both via `get_by_id_or_uuid()`.

---

## Feature flags — enable/disable and access control

SiteConfig keys (DB): `allow_registration`, `allow_login`, `email_verification_enabled`.
Toggle from `/admin/users` or via `POST /api/admin/site-config`.

Every feature must be activatable/deactivatable via a feature flag seeded in the DB.
Nav and access are controlled from two files only — never touch `_nav.html` or `_search_sections.html`:

- `app/core/utils/permissions.py` — add permission keys for the feature
- `app/core/utils/nav_registry.py` — add nav entry with required permission

```python
# nav_registry.py
{ "label": "Items", "url": "items.index", "permission": "items.view" }

# permission values:
# None          -> all authenticated users
# 'items.view'  -> users with that permission (or admins)
# 'admin_only'  -> admins only
```

Every page and feature must define clearly whether the user is read-only or can edit. Use `hasPerm()` in templates to conditionally show actions.

```javascript
const can_edit   = hasPerm('items.edit')
const can_delete = hasPerm('items.delete')
```

---

## Background Jobs

Register a new job type from any `*_core.py` file:

```python
from ...core.utils.job_runner import register_handler, enqueue_job

@register_handler('myfeature.my_task')
def my_task(ctx, meta):
    total = meta.get('total', 100)
    for i in range(total):
        ctx.checkpoint()                    # pause/cancel point — call frequently
        ctx.update_progress(int(i / total * 100))
        ctx.log(f"Processing item {i}")
    return {'processed': total}             # stored in job.result
```

Enqueue from a core function:

```python
job = enqueue_job('myfeature.my_task', title='My Task', meta={'total': 500}, user_id=uid)
```

`JobContext` methods: `ctx.checkpoint()`, `ctx.update_progress(0-100)`, `ctx.log(msg, level)`,
`ctx.is_cancelled()`, `ctx.is_paused()`. Raise `JobCancelled` on cancel, pause via DB flag.

Permissions: `jobs.view` (own jobs list), `jobs.manage` (all jobs + actions, admin nav).

---

## Templates

Every page follows this skeleton — no exceptions:

```jinja
{% extends 'base.html' %}
{% block head_extra %}<link rel="stylesheet" href="{{ url_for('static', filename='css/<feature>/<feature>.css') }}">{% endblock %}
{% block content %}
<div class="page-wrapper" v-cloak>
    <loading-bar :active="!page_is_loading"></loading-bar>
    <div v-if="page_is_loading">
        <div class="page-header">
            <div>
                <nav aria-label="breadcrumb"><ol class="breadcrumb mb-1">...</ol></nav>
                <h1 class="page-title">Title</h1>
            </div>
            <div class="page-actions">...</div>
        </div>
        <div class="page-body">...</div>
    </div>
</div>
{% endblock %}
{% block script %}
<script type="module">
    const { createApp, ref, onMounted } = Vue
    import { TOAST, apiFetch } from '../static/js/constants.js'
    import { create_message, message_list } from '../static/js/toaster.js'
    import LoadingBar from '../static/js/components/loading-bar.js'

    createApp({
        delimiters: ['[[', ']]'],
        components: { LoadingBar },
        setup() {
            const page_is_loading = ref(false)
            onMounted(async () => {
                await Promise.all([])
                page_is_loading.value = true
            })
            return { message_list, page_is_loading }
        }
    }).mount('#main-container')
</script>
{% endblock %}
```

---

## Components — always reuse before creating

Check `static/js/components/` and `static/css/` before writing anything new.

| Need | Component |
|---|---|
| Table with sort/filter/pagination | `<data-table>` — never build from scratch |
| Chart | Apache ECharts via `chart-<type>.js` component |
| Feedback to user | `create_message(text, TOAST.SUCCESS)` — never `display_toast()` in templates |
| Loading state | `<loading-bar>` |
| Pagination | `<pagination>` |

---

## JS conventions

- Composition API, ES modules, delimiters `[[...]]`
- Import from `constants.js`: `TOAST`, `CSRF_TOKEN`, `apiFetch(url, method, body)`
- Import from `toaster.js`: `create_message(text, TOAST.*, sticky)`
- Always check `res.ok` after `apiFetch`
- Never `console.log`
- Jinja values in scripts always quoted: `const id = '{{ current_user.id }}'`

---

## CSS conventions

- Never hardcode colors — always `var(--bg-body)`, `var(--text-main)`, etc.
- One file per feature: `static/css/<feature>/<feature>.css`
- CSS classes prefixed by feature: `.items-card`, `.items-badge`
- Dark mode via `[data-bs-theme="dark"]` only
- Sections delimited: `/*---SECTION_NAME---*/`

---

## Models — standard fields on every new model

```
id, uuid (auto), title, description, is_public (False),
created_at, updated_at, created_by,
is_active (True), deleted_at, deleted_by,
meta (JSON — IDs only, never plain names)
```

Always filter active records: `Model.query.filter_by(is_active=True)`.

---

## Logs

Call `log_action()` from `*_core.py` only — never from routes or API resources.

```python
log_action(
    title="Item created",
    action="create",           # login|logout|create|edit|delete|restore|hard_delete|bulk_*
    category="items",          # feature name — use "api" for anything in *_api.py
    level="success",           # info|success|warning|error
    object_type="item",
    object_id=item.id,
    is_public=True,            # False for delete/admin actions
    meta={"role_id": user.role_id}
)
```

---

## Security

- Never `{{ var | safe }}` on user data
- Never raw `db.execute()` with string interpolation
- Validate all user input via `app/core/utils/validators.py`
- Run `bandit -r app/` before delivery — no HIGH or MEDIUM issues

---

## Tests

Every feature and every route gets a test file. Tests cover:
- HTML routes: 200 / 302 / 403 / 404 per role (admin, editor, read-only, anonymous)
- API: 200 / 201 / 400 / 403 / 404
- Trash flow: delete -> restore -> hard delete
- Permission boundaries: read-only users cannot trigger write actions

Always run `./launch.sh --test` before declaring done.

```
tests/
  conftest.py                  # admin / editor / read-only fixtures
  <feature>/test_<feature>.py
```

Test users: `admin@admin.admin` / `admin_api_key` — `editor@editor.editor` / `editor_api_key` — `read@read.read` / `read_api_key`

---

## Checklist — every new feature

- [ ] `app/features/<f>/`, `<f>.py`, `<f>_core.py`, `form.py`
- [ ] `app/api/<f>_api.py` + namespace registered in `api.py`
- [ ] `app/static/css/<f>/<f>.css`
- [ ] `app/templates/<f>/` (all pages use the skeleton above)
- [ ] `tests/<f>/test_<f>.py`
- [ ] Model with all standard fields, migration applied
- [ ] Permission keys in `permissions.py`, nav entry in `nav_registry.py`
- [ ] Feature flag seeded to enable/disable the feature
- [ ] Every page: read-only vs edit access defined via `hasPerm()`
- [ ] `log_action` on create, edit, delete, restore, hard_delete, every bulk action
- [ ] Ops on >50 objects or >2s -> background job returning `202 + job_id`
- [ ] `./launch.sh --test` passes
- [ ] `CLAUDE.md` project layout updated
- [ ] `bandit -r app/` clean

---

## Design principle

Every feature must be easy to update later. Before writing code, ask:
- Can I change the business logic without touching the route or template?
- Can I enable/disable this feature without a deploy?
- Can I restrict access to a role without rewriting the view?

If the answer to any of these is no, rethink the structure.
