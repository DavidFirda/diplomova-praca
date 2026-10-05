# ============================================================
# AdaptPy - POZVÁNKY (model).  Admin pozve používateľa e-mailom,
# ten si cez jednorazový odkaz dokončí registráciu.
# Tabuľka sa vytvorí automaticky (ensure_invite_table v invite_routes.py).
# ============================================================
from datetime import datetime, timezone

from models import db


def utcnow():
    """Naivný UTC čas (rovnako ako ostatné DateTime stĺpce v DB)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Invitation(db.Model):
    __tablename__ = "invitations"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=True)       # voliteľné predvyplnenie
    surname = db.Column(db.String(100), nullable=True)    # voliteľné predvyplnenie
    group_name = db.Column(db.String(100), nullable=True) # voliteľná skupina / trieda

    token_hash = db.Column(db.String(64), nullable=False, index=True)  # SHA-256 tokenu (token sa neukladá)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    created_by = db.Column(db.Integer, nullable=True)     # id admina
    last_sent_at = db.Column(db.DateTime, nullable=True)
    send_count = db.Column(db.Integer, default=0)

    used_at = db.Column(db.DateTime, nullable=True)       # kedy sa zaregistroval
    student_id = db.Column(db.Integer, nullable=True)     # vytvorený účet

    @property
    def status(self):
        if self.used_at:
            return "registered"
        if self.expires_at and self.expires_at < utcnow():
            return "expired"
        return "pending"
