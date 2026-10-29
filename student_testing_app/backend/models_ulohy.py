# ============================================================
# AdaptPy - modely pre ÚLOHY (samoštúdium personalizované POMDP).
#
#  - TaskAssignment: jedna úloha pridelená študentovi (otázka z tabuľky
#                    questions) a jej stav: open | solved | failed | void
#  - TaskAttempt:    KAŽDÝ započítaný pokus študenta (aj nesprávny) s poradovým
#                    číslom -> admin vidí, na koľký krát študent odpovedal
#  - TaskEvent:      log VŠETKÝCH interakcií (pridelenie, pokusy, odmietnuté
#                    odoslania, agent, riešenie, POMDP odmena, zásahy admina)
#
# Schému spravujú migrácie (backend/migrations). Úlohy zámerne NIE sú v
# student_answers, aby sa výsledky samoštúdia nemiešali s výsledkami testov.
# ============================================================
from datetime import datetime, timezone

from models import db


def _now():
    return datetime.now(timezone.utc)


class TaskAssignment(db.Model):
    __tablename__ = "task_assignments"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    strategy = db.Column(db.String(20), nullable=False, default="pomdp")

    # open = rieši sa | solved = vyriešená | failed = 5 nesprávnych pokusov
    # void = chyba na strane zadania (referenčné riešenie nebeží) - bez POMDP aktualizácie
    status = db.Column(db.String(20), nullable=False, default="open")

    attempts_used = db.Column(db.Integer, nullable=False, default=0)    # započítané pokusy
    wrong_attempts = db.Column(db.Integer, nullable=False, default=0)   # z nich nesprávne
    hints_used = db.Column(db.Integer, nullable=False, default=0)       # nápovedy agenta
    agent_opened = db.Column(db.Boolean, nullable=False, default=False)
    solution_shown = db.Column(db.Boolean, nullable=False, default=False)

    is_correct = db.Column(db.Boolean, nullable=True)          # None kým je úloha otvorená
    solved_on_attempt = db.Column(db.Integer, nullable=True)   # na koľký pokus vyriešil
    reward = db.Column(db.Float, nullable=True)                # odmena odovzdaná POMDP
    pomdp_applied = db.Column(db.Boolean, nullable=False, default=False)

    assigned_at = db.Column(db.DateTime, default=_now)
    finished_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        # poistka na úrovni DB: študent má najviac jednu otvorenú úlohu
        db.Index(
            "uq_task_one_open", "student_id", unique=True,
            postgresql_where=db.text("status = 'open'"),
            sqlite_where=db.text("status = 'open'"),
        ),
    )


class TaskAttempt(db.Model):
    __tablename__ = "task_attempts"
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("task_assignments.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    attempt_no = db.Column(db.Integer, nullable=False)          # 1, 2, 3, ...
    code = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    student_output = db.Column(db.Text, nullable=True)
    error = db.Column(db.Text, nullable=True)                   # chyba pri behu kódu
    feedback_kind = db.Column(db.String(30), nullable=True)
    feedback_json = db.Column(db.Text, nullable=True)           # {"kind", "params", "message"}
    # kontrola originality (services/integrity.py): metriky písania, dôvody, potvrdenie študenta
    integrity_json = db.Column(db.Text, nullable=True)
    integrity_flag = db.Column(db.Boolean, nullable=False, default=False)   # red flag
    flag_dismissed = db.Column(db.Boolean, nullable=False, default=False)   # admin ho zrušil
    created_at = db.Column(db.DateTime, default=_now)

    __table_args__ = (
        db.UniqueConstraint("assignment_id", "attempt_no", name="uq_task_attempt_no"),
    )


class TaskEvent(db.Model):
    __tablename__ = "task_events"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    # bez cudzieho kľúča: log prežije aj zmazanie úlohy adminom
    assignment_id = db.Column(db.Integer, nullable=True, index=True)
    question_id = db.Column(db.Integer, nullable=True)
    event_type = db.Column(db.String(40), nullable=False)
    payload_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=_now, index=True)
