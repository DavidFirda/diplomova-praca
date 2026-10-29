"""kontrola originality: red flag pri pokusoch úloh a odpovediach testov

  - task_attempts:   integrity_json, integrity_flag, flag_dismissed
  - student_answers: integrity_json, integrity_flag, flag_dismissed
  - answer_attempts: integrity_json (podozrivé odoslania počas opráv v teste)

Idempotentná migrácia (stĺpce sa pridajú, len ak ešte neexistujú).

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

_FLAG_TABLES = ("task_attempts", "student_answers")


def _cols(inspector, table):
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade():
    inspector = sa.inspect(op.get_bind())

    for table in _FLAG_TABLES:
        cols = _cols(inspector, table)
        if "integrity_json" not in cols:
            op.add_column(table, sa.Column("integrity_json", sa.Text(), nullable=True))
        if "integrity_flag" not in cols:
            op.add_column(table, sa.Column("integrity_flag", sa.Boolean(), nullable=False,
                                           server_default=sa.false()))
        if "flag_dismissed" not in cols:
            op.add_column(table, sa.Column("flag_dismissed", sa.Boolean(), nullable=False,
                                           server_default=sa.false()))

    if "integrity_json" not in _cols(inspector, "answer_attempts"):
        op.add_column("answer_attempts", sa.Column("integrity_json", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("answer_attempts", "integrity_json")
    for table in _FLAG_TABLES:
        op.drop_column(table, "flag_dismissed")
        op.drop_column(table, "integrity_flag")
        op.drop_column(table, "integrity_json")
