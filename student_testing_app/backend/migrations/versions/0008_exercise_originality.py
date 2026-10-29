"""kontrola originality aj v cvičeniach: exercise_progress.integrity_json

Podozrivé spustenia buniek (red flagy) po bunkách - pozri services/integrity.py.
Idempotentná migrácia (stĺpec sa pridá, len ak ešte neexistuje).

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    cols = {c["name"] for c in inspector.get_columns("exercise_progress")}
    if "integrity_json" not in cols:
        op.add_column("exercise_progress", sa.Column("integrity_json", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("exercise_progress", "integrity_json")
