# ============================================================
# AdaptPy - modely pre CVIČENIA (Jupyter notebooky) a progres.
#
# Tento súbor NIJAKO nemení tvoj models.py - iba doňho pridáva
# ďalšie tabuľky cez ten istý `db` (SQLAlchemy). Stačí, aby sa
# tento modul niekde naimportoval PRED `db.create_all()` v app.py
# (návod je v INTEGRACIA.md), a tabuľky sa vytvoria automaticky.
# ============================================================
from datetime import datetime, timezone
from models import db


# Jedno cvičenie = jeden .ipynb notebook v priečinku EXERCISES_DIR.
class Exercise(db.Model):
    __tablename__ = "exercises"
    id = db.Column(db.Integer, primary_key=True)

    # stabilný identifikátor odvodený z názvu súboru (napr. "lab01-setting-up")
    slug = db.Column(db.String(160), unique=True, nullable=False)
    # názov .ipynb súboru v priečinku s cvičeniami
    filename = db.Column(db.String(255), nullable=False)

    # poradie (sekvenčné odomykanie) - menšie číslo = skôr
    order_index = db.Column(db.Integer, default=0)

    # nadpis a popis (dvojjazyčne, ako zvyšok appky)
    title_sk = db.Column(db.String(255), nullable=False, default="")
    title_en = db.Column(db.String(255), nullable=False, default="")
    description_sk = db.Column(db.Text, default="")
    description_en = db.Column(db.Text, default="")

    # "čo sa preberá / aké časti" - JSON pole reťazcov (nadpisy sekcií z notebooku)
    topics_json = db.Column(db.Text, default="[]")

    # počet code-buniek (na výpočet % vypracovania)
    code_cells = db.Column(db.Integer, default=0)

    # admin flagy
    published = db.Column(db.Boolean, default=False)     # dokončené/finálne
    accessible = db.Column(db.Boolean, default=False)    # sprístupnené študentom k nahliadnutiu

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


# Progres konkrétneho študenta na konkrétnom cvičení.
class ExerciseProgress(db.Model):
    __tablename__ = "exercise_progress"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercises.id"), nullable=False)

    # indexy code-buniek, ktoré študent spustil bez chyby - JSON pole čísel
    done_cells_json = db.Column(db.Text, default="[]")
    percent = db.Column(db.Integer, default=0)  # 0..100

    # "not_started" | "in_progress" | "completed"
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
