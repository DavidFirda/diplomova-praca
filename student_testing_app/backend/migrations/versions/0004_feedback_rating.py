"""feedback_messages.rating - hodnotenie 1-5 hviezdičiek (nepovinné)

Idempotentná migrácia (stĺpec sa pridá, len ak ešte neexistuje).

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    cols = {c["name"] for c in inspector.get_columns("feedback_messages")}
    if "rating" not in cols:
        op.add_column("feedback_messages", sa.Column("rating", sa.SmallInteger(), nullable=True))


def downgrade():
    op.drop_column("feedback_messages", "rating")
