"""job.py — Background Job model."""
from datetime import datetime
import uuid as _uuid
from ... import db


def _gen_uuid():
    return str(_uuid.uuid4())


JOB_STATUSES = ('pending', 'running', 'paused', 'completed', 'failed', 'cancelled')


class Job(db.Model):
    __tablename__ = 'job'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid        = db.Column(db.String(36), unique=True, nullable=False, default=_gen_uuid)
    type        = db.Column(db.String(64), nullable=False)
    title       = db.Column(db.String(128), nullable=False)
    status      = db.Column(db.String(16), nullable=False, default='pending')
    progress    = db.Column(db.Integer, default=0, nullable=False)
    logs        = db.Column(db.JSON, nullable=True)      # list of {ts, level, msg}
    result      = db.Column(db.JSON, nullable=True)
    error       = db.Column(db.Text, nullable=True)
    started_at  = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)

    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_active   = db.Column(db.Boolean, default=True, nullable=False)
    deleted_at  = db.Column(db.DateTime, nullable=True)
    deleted_by  = db.Column(db.Integer, nullable=True)
    meta        = db.Column(db.JSON, nullable=True)

    @property
    def duration_seconds(self):
        if self.started_at and self.finished_at:
            return round((self.finished_at - self.started_at).total_seconds(), 2)
        if self.started_at:
            return round((datetime.utcnow() - self.started_at).total_seconds(), 2)
        return None

    def to_json(self):
        return {
            'id':           self.id,
            'uuid':         self.uuid,
            'type':         self.type,
            'title':        self.title,
            'status':       self.status,
            'progress':     self.progress,
            'logs':         self.logs or [],
            'result':       self.result,
            'error':        self.error,
            'duration':     self.duration_seconds,
            'started_at':   self.started_at.isoformat() if self.started_at else None,
            'finished_at':  self.finished_at.isoformat() if self.finished_at else None,
            'created_at':   self.created_at.isoformat() if self.created_at else None,
            'created_by':   self.created_by,
            'is_active':    self.is_active,
            'meta':         self.meta or {},
        }
