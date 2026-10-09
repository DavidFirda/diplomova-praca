# ============================================================
# AdaptPy - modely pre CVIČENIA (Jupyter notebooky) a progres.
#
# Schému spravujú migrácie (backend/migrations).
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

    # časový limit na spustenie bunky (s). None/0 = použi default runnera
    run_timeout = db.Column(db.Integer, nullable=True)

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

    done_cells_json = db.Column(db.Text, default="[]")
    answers_json = db.Column(db.Text, default="{}")

    percent = db.Column(db.Integer, default=0)
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
