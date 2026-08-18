# ============================================================
# AdaptPy - modely pre CVIČENIA (Jupyter notebooky) a progres.
#
# Tento súbor NIJAKO nemení tvoj models.py - iba doňho pridáva
# ďalšie tabuľky cez ten istý `db` (SQLAlchemy). Stačí, aby sa
# tento modul niekde naimportoval PRED `db.create_all()` v app.py,
# a tabuľky sa vytvoria automaticky.
#
# POZN.: stĺpec `answers_json` pribudol dodatočne - ak už tabuľka
# `exercise_progress` existuje, doplní ho migrácia v
# services/exercise_migrate.py (spúšťa sa pri štarte).
# ============================================================
from datetime import datetime, timezone
from models import db


class Exercise(db.Model):
    __tablename__ = "exercises"
    id = db.Column(db.Integer, primary_key=True)

    slug = db.Column(db.String(160), unique=True, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    order_index = db.Column(db.Integer, default=0)

    title_sk = db.Column(db.String(255), nullable=False, default="")
    title_en = db.Column(db.String(255), nullable=False, default="")
    description_sk = db.Column(db.Text, default="")
    description_en = db.Column(db.Text, default="")

    topics_json = db.Column(db.Text, default="[]")
    code_cells = db.Column(db.Integer, default=0)

    published = db.Column(db.Boolean, default=False)
    accessible = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    progress = db.relationship(
        "ExerciseProgress", backref="exercise", lazy=True,
        cascade="all, delete-orphan",
    )


class ExerciseProgress(db.Model):
    __tablename__ = "exercise_progress"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercises.id"), nullable=False)

    # indexy code-buniek spustených bez chyby - JSON pole čísel
    done_cells_json = db.Column(db.Text, default="[]")
    # ODPOVEDE študenta: JSON objekt { "code_index": "kód, ktorý napísal" }
    answers_json = db.Column(db.Text, default="{}")

    percent = db.Column(db.Integer, default=0)  # 0..100
    status = db.Column(db.String(20), default="not_started")

    completed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.UniqueConstraint("student_id", "exercise_id", name="uq_student_exercise"),
    )
