"""progres testov: test_progress + answer_attempts

  - test_progress:   rozpracovaný/dokončený hlavný test študenta a otázka, na
                     ktorej skončil (po návrate sa zobrazí tá istá)
  - answer_attempts: počet použitých opráv na otázku (prežije reštart aj
                     beh na viacerých workeroch)

Migrácia je idempotentná (ak tabuľky vznikli skôr cez db.create_all()).

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table("test_progress"):
        op.create_table(
            "test_progress",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
            sa.Column("test_type", sa.String(), nullable=False),
            sa.Column("test_session", sa.String(), nullable=False),
            sa.Column("current_question_id", sa.Integer(), sa.ForeignKey("questions.id")),
            sa.Column("total_questions", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
            sa.UniqueConstraint("student_id", "test_type", "test_session",
                                name="uq_progress_student_type_session"),
        )
    # poistka v DB: študent má najviac jeden rozpracovaný test daného typu
    op.create_index(
        "uq_progress_one_active", "test_progress", ["student_id", "test_type"],
        unique=True, if_not_exists=True,
        postgresql_where=sa.text("status = 'in_progress'"),
        sqlite_where=sa.text("status = 'in_progress'"),
    )

    if not inspector.has_table("answer_attempts"):
        op.create_table(
            "answer_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
            sa.Column("test_type", sa.String(), nullable=False),
            sa.Column("test_session", sa.String(), nullable=False),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.UniqueConstraint("student_id", "test_type", "test_session", "question_id",
                                name="uq_attempt_key"),
        )


def downgrade():
    op.drop_table("answer_attempts")
    op.drop_index("uq_progress_one_active", table_name="test_progress")
    op.drop_table("test_progress")
