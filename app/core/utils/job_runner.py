"""job_runner.py — Background job execution engine.

Usage from any feature:
    from ...core.utils.job_runner import register_handler

    @register_handler('my_feature.my_task')
    def my_task(ctx, meta):
        for i in range(100):
            ctx.checkpoint()              # pause/cancel point
            ctx.update_progress(i)
            ctx.log(f"Step {i}")
        return {'done': True}

Registering a job from a core function:
    from ...core.utils.job_runner import enqueue_job
    job = enqueue_job('my_feature.my_task', title='My Task', meta={...}, user_id=1)
"""
import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Handler registry ──────────────────────────────────────────────────────────

_HANDLERS: dict = {}


def register_handler(type_key: str):
    """Decorator to register a job handler function."""
    def decorator(fn):
        _HANDLERS[type_key] = fn
        return fn
    return decorator


def get_handler(type_key: str):
    return _HANDLERS.get(type_key)


def registered_types() -> list[str]:
    return list(_HANDLERS.keys())


# ── Exceptions ────────────────────────────────────────────────────────────────

class JobCancelled(Exception):
    pass

class JobFailed(Exception):
    pass


# ── JobContext ────────────────────────────────────────────────────────────────

class JobContext:
    """Injected into every handler. Provides progress, logging, and flow control."""

    def __init__(self, job_id: int, app):
        self._job_id = job_id
        self._app    = app

    def _get_job(self, session):
        from ...core.db_class.job import Job
        return session.get(Job, self._job_id)

    def _db_op(self, fn):
        """Run fn(db, Job) inside an app context (uses existing one if active)."""
        try:
            from flask import has_app_context
            if has_app_context():
                from ... import db
                from ...core.db_class.job import Job
                return fn(db, Job)
            else:
                with self._app.app_context():
                    from ... import db
                    from ...core.db_class.job import Job
                    return fn(db, Job)
        except Exception as e:
            logger.warning("JobContext db_op failed: %s", e)
            return None

    def update_progress(self, value: int):
        value = max(0, min(100, int(value)))
        def _fn(db, Job):
            job = db.session.get(Job, self._job_id)
            if job:
                job.progress = value
                db.session.commit()
        self._db_op(_fn)

    def log(self, msg: str, level: str = 'info'):
        def _fn(db, Job):
            job = db.session.get(Job, self._job_id)
            if job:
                entries = list(job.logs or [])
                entries.append({'ts': datetime.utcnow().isoformat(), 'level': level, 'msg': str(msg)})
                job.logs = entries
                db.session.commit()
        self._db_op(_fn)

    def is_cancelled(self) -> bool:
        def _fn(db, Job):
            job = db.session.get(Job, self._job_id)
            return job is None or job.status == 'cancelled'
        return self._db_op(_fn) or False

    def is_paused(self) -> bool:
        def _fn(db, Job):
            job = db.session.get(Job, self._job_id)
            return job is not None and job.status == 'paused'
        return self._db_op(_fn) or False

    def checkpoint(self):
        """Call at regular intervals to support pause and cancel."""
        if self.is_cancelled():
            raise JobCancelled("Job was cancelled")
        while self.is_paused():
            time.sleep(0.5)
            if self.is_cancelled():
                raise JobCancelled("Job was cancelled while paused")

    def wait_if_paused(self):
        """Alias for checkpoint (no cancel check)."""
        while self.is_paused():
            time.sleep(0.5)


# ── Runner ────────────────────────────────────────────────────────────────────

_executor: ThreadPoolExecutor | None = None
_running_job_ids: set[int] = set()
_lock = threading.Lock()
_daemon_thread: threading.Thread | None = None
_app_ref = None


def init_runner(app, max_workers: int = 4):
    """Call once from create_app(). Starts the daemon poller."""
    global _executor, _daemon_thread, _app_ref
    _app_ref = app
    _executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='job-worker')
    _daemon_thread = threading.Thread(target=_poll_loop, args=(app,), daemon=True, name='job-poller')
    _daemon_thread.start()
    logger.info("Job runner started (max_workers=%d)", max_workers)


def _poll_loop(app):
    """Daemon thread: polls for pending jobs every 2 seconds."""
    while True:
        try:
            _dispatch_pending(app)
        except Exception as e:
            logger.error("Job poller error: %s", e)
        time.sleep(2)


def _dispatch_pending(app):
    with app.app_context():
        from ... import db
        from ...core.db_class.job import Job

        with _lock:
            running = set(_running_job_ids)

        pending = (
            Job.query
            .filter_by(status='pending', is_active=True)
            .filter(~Job.id.in_(running) if running else db.true())
            .order_by(Job.created_at)
            .limit(4)
            .all()
        )

        for job in pending:
            handler = get_handler(job.type)
            if not handler:
                job.status  = 'failed'
                job.error   = f"No handler registered for type '{job.type}'"
                job.finished_at = datetime.utcnow()
                db.session.commit()
                continue

            with _lock:
                _running_job_ids.add(job.id)

            job_id   = job.id
            job_meta = job.meta or {}
            future   = _executor.submit(_run_job, app, job_id, handler, job_meta)
            future.add_done_callback(lambda f, jid=job_id: _on_done(jid, f))


def _run_job(app, job_id: int, handler, meta: dict):
    with app.app_context():
        from ... import db
        from ...core.db_class.job import Job

        job = db.session.get(Job, job_id)
        if not job or job.status not in ('pending', 'paused'):
            return

        job.status     = 'running'
        job.started_at = job.started_at or datetime.utcnow()
        job.progress   = 0
        db.session.commit()

        ctx = JobContext(job_id, app)
        try:
            ctx.log("Job started", level='info')
            result = handler(ctx, meta)
            job = db.session.get(Job, job_id)
            if job and job.status == 'running':
                job.status      = 'completed'
                job.progress    = 100
                job.result      = result
                job.finished_at = datetime.utcnow()
                db.session.commit()
            ctx.log("Job completed", level='success')
        except JobCancelled:
            job = db.session.get(Job, job_id)
            if job:
                job.status      = 'cancelled'
                job.finished_at = datetime.utcnow()
                db.session.commit()
        except Exception as e:
            job = db.session.get(Job, job_id)
            if job:
                job.status      = 'failed'
                job.error       = str(e)
                job.finished_at = datetime.utcnow()
                db.session.commit()
            ctx.log(f"Error: {e}", level='error')
            logger.exception("Job %d failed: %s", job_id, e)


def _on_done(job_id: int, future):
    with _lock:
        _running_job_ids.discard(job_id)


# ── Public API ────────────────────────────────────────────────────────────────

def enqueue_job(type_key: str, title: str = '', meta: dict = None, user_id: int = None):
    """Create a Job record and return it. The poller will pick it up."""
    from flask import current_app
    from ... import db
    from ...core.db_class.job import Job

    if not title:
        title = type_key.replace('.', ' ').replace('_', ' ').title()

    job = Job(
        type=type_key,
        title=title,
        status='pending',
        meta=meta or {},
        created_by=user_id,
    )
    db.session.add(job)
    db.session.commit()
    return job
