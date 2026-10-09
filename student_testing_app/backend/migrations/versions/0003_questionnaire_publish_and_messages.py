"""zverejnenie dotazníka (app_settings) + voľná spätná väzba (feedback_messages)

  - app_settings:      nastavenia aplikácie (kľúč-hodnota), napr. questionnaire_published
  - feedback_messages: správy z feedback formulára (dostupný vždy)

Dotazník je po tejto migrácii predvolene nezverejnený (chýba riadok
questionnaire_published = "true"); zverejní ho admin v administrácii.
Migrácia je idempotentná.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table("app_settings"):
        op.create_table(
            "app_settings",
            sa.Column("key", sa.String(60), primary_key=True),
            sa.Column("value", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime()),
        )

    if not inspector.has_table("feedback_messages"):
        op.create_table(
            "feedback_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
            sa.Column("category", sa.String(20), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_feedback_messages_student_id", "feedback_messages", ["student_id"])
        op.create_index("ix_feedback_messages_created_at", "feedback_messages", ["created_at"])


def downgrade():
    op.drop_table("feedback_messages")
    op.drop_table("app_settings")
