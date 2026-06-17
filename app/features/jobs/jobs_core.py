"""jobs_core.py — CRUD and control operations for background jobs."""
from datetime import datetime
from flask_login import current_user
from ... import db
from ...core.db_class.job import Job, JOB_STATUSES
from ...core.utils.logger import log_action


def get_job_or_none(uuid: str) -> Job | None:
    return Job.query.filter_by(uuid=uuid, is_active=True).first()


def list_jobs_core(page=1, per_page=10, search='', sort='created_at', direction='desc',
                   status_filter='', admin_view=False, user_id=None):
    q = Job.query.filter_by(is_active=True)

    if not admin_view and user_id:
        q = q.filter_by(created_by=user_id)

    if status_filter == 'active':
        q = q.filter(Job.status.in_(['pending', 'running', 'paused']))
    elif status_filter and status_filter in JOB_STATUSES:
        q = q.filter_by(status=status_filter)

    if search:
        term = f'%{search}%'
        q = q.filter(db.or_(Job.title.ilike(term), Job.type.ilike(term)))

    sort_col = getattr(Job, sort, Job.created_at)
    if direction == 'desc':
        q = q.order_by(sort_col.desc())
    else:
        q = q.order_by(sort_col.asc())

    total       = q.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    items       = q.offset((page - 1) * per_page).limit(per_page).all()
    return items, total, total_pages


def cancel_job_core(uuid: str, user_id: int) -> tuple[bool, str]:
    job = get_job_or_none(uuid)
    if not job:
        return False, "Job not found"
    if job.status not in ('pending', 'running', 'paused'):
        return False, f"Cannot cancel a job with status '{job.status}'"
    job.status      = 'cancelled'
    job.finished_at = datetime.utcnow()
    db.session.commit()
    log_action(f"Job '{job.title}' cancelled", "edit", category="jobs",
               level="warning", object_type="job", object_id=job.id, is_public=False)
    return True, "Job cancelled"


def pause_job_core(uuid: str, user_id: int) -> tuple[bool, str]:
    job = get_job_or_none(uuid)
    if not job:
        return False, "Job not found"
    if job.status != 'running':
        return False, f"Cannot pause a job with status '{job.status}'"
    job.status = 'paused'
    db.session.commit()
    log_action(f"Job '{job.title}' paused", "edit", category="jobs",
               level="info", object_type="job", object_id=job.id, is_public=False)
    return True, "Job paused"


def resume_job_core(uuid: str, user_id: int) -> tuple[bool, str]:
    job = get_job_or_none(uuid)
    if not job:
        return False, "Job not found"
    if job.status != 'paused':
        return False, f"Cannot resume a job with status '{job.status}'"
    job.status = 'running'
    db.session.commit()
    log_action(f"Job '{job.title}' resumed", "edit", category="jobs",
               level="info", object_type="job", object_id=job.id, is_public=False)
    return True, "Job resumed"


def retry_job_core(uuid: str, user_id: int) -> tuple[Job | None, str]:
    job = get_job_or_none(uuid)
    if not job:
        return None, "Job not found"
    if job.status not in ('failed', 'cancelled'):
        return None, f"Can only retry failed or cancelled jobs (current: '{job.status}')"
    from ...core.utils.job_runner import enqueue_job
    new_job = enqueue_job(job.type, title=job.title, meta=job.meta, user_id=user_id)
    log_action(f"Job '{job.title}' retried (new id {new_job.id})", "create", category="jobs",
               level="info", object_type="job", object_id=new_job.id, is_public=False)
    return new_job, "Job queued for retry"


def delete_job_core(uuid: str, user_id: int) -> tuple[bool, str]:
    job = get_job_or_none(uuid)
    if not job:
        return False, "Job not found"
    if job.status == 'running':
        return False, "Cannot delete a running job — cancel it first"
    job.is_active  = False
    job.deleted_at = datetime.utcnow()
    job.deleted_by = user_id
    db.session.commit()
    log_action(f"Job '{job.title}' deleted", "delete", category="jobs",
               level="warning", object_type="job", object_id=job.id, is_public=False)
    return True, "Job deleted"


def bulk_cancel_jobs_core(uuids: list[str], user_id: int) -> tuple[int, int]:
    ok = 0
    fail = 0
    for uuid in uuids:
        success, _ = cancel_job_core(uuid, user_id)
        if success:
            ok += 1
        else:
            fail += 1
    if ok:
        log_action(f"Bulk cancel: {ok} jobs cancelled", "bulk_cancel", category="jobs",
                   level="warning", object_type="job", is_public=False)
    return ok, fail


def bulk_delete_jobs_core(uuids: list[str], user_id: int) -> tuple[int, int]:
    ok = 0
    fail = 0
    for uuid in uuids:
        success, _ = delete_job_core(uuid, user_id)
        if success:
            ok += 1
        else:
            fail += 1
    if ok:
        log_action(f"Bulk delete: {ok} jobs deleted", "bulk_delete", category="jobs",
                   level="warning", object_type="job", is_public=False)
    return ok, fail
