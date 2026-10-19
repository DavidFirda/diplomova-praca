"""úlohy (samoštúdium s POMDP): task_assignments, task_attempts, task_events

  - task_assignments: úloha pridelená študentovi + jej stav (open/solved/failed/void)
  - task_attempts:    každý započítaný pokus (aj nesprávny) s poradovým číslom
  - task_events:      log všetkých interakcií (pokusy, agent, riešenie, POMDP odmena, ...)

Migrácia je idempotentná (ak tabuľky vznikli skôr cez db.create_all()).

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table("task_assignments"):
        op.create_table(
            "task_assignments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
            sa.Column("category", sa.String(100), nullable=False),
            sa.Column("strategy", sa.String(20), nullable=False, server_default="pomdp"),
            sa.Column("status", sa.String(20), nullable=False, server_default="open"),
            sa.Column("attempts_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("wrong_attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("agent_opened", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("solution_shown", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_correct", sa.Boolean()),
            sa.Column("solved_on_attempt", sa.Integer()),
            sa.Column("reward", sa.Float()),
            sa.Column("pomdp_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("assigned_at", sa.DateTime()),
            sa.Column("finished_at", sa.DateTime()),
        )
        op.create_index("ix_task_assignments_student_id", "task_assignments", ["student_id"])
    # poistka v DB: študent má najviac jednu otvorenú úlohu
    op.create_index(
        "uq_task_one_open", "task_assignments", ["student_id"],
        unique=True, if_not_exists=True,
        postgresql_where=sa.text("status = 'open'"),
        sqlite_where=sa.text("status = 'open'"),
    )

    if not inspector.has_table("task_attempts"):
        op.create_table(
            "task_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("task_assignments.id"), nullable=False),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
            sa.Column("attempt_no", sa.Integer(), nullable=False),
            sa.Column("code", sa.Text(), nullable=False),
            sa.Column("is_correct", sa.Boolean(), nullable=False),
            sa.Column("student_output", sa.Text()),
            sa.Column("error", sa.Text()),
            sa.Column("feedback_kind", sa.String(30)),
            sa.Column("feedback_json", sa.Text()),
            sa.Column("created_at", sa.DateTime()),
            sa.UniqueConstraint("assignment_id", "attempt_no", name="uq_task_attempt_no"),
        )
        op.create_index("ix_task_attempts_assignment_id", "task_attempts", ["assignment_id"])
        op.create_index("ix_task_attempts_student_id", "task_attempts", ["student_id"])

    if not inspector.has_table("task_events"):
        op.create_table(
            "task_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
            sa.Column("assignment_id", sa.Integer()),
            sa.Column("question_id", sa.Integer()),
            sa.Column("event_type", sa.String(40), nullable=False),
            sa.Column("payload_json", sa.Text()),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_task_events_student_id", "task_events", ["student_id"])
        op.create_index("ix_task_events_assignment_id", "task_events", ["assignment_id"])
        op.create_index("ix_task_events_created_at", "task_events", ["created_at"])


def downgrade():
    op.drop_table("task_events")
    op.drop_table("task_attempts")
    op.drop_index("uq_task_one_open", table_name="task_assignments")
    op.drop_table("task_assignments")
