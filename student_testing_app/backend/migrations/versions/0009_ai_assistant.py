"""AI asistent: materiály kurzu (RAG), konverzácie, správy, zdroje; postupné nápovedy v Úlohách

- course_materials          nahraté prednášky a knihy (súbory v MATERIALS_DIR)
- assistant_conversations   konverzácia študenta v kontexte (dashboard / cvičenie / úloha)
- assistant_messages        správy + model, časy, tokeny, zásahy strážcu
- assistant_sources         kúsky materiálov, z ktorých RAG čerpal pri odpovedi
- task_assignments.last_hint_wrong   ďalšia nápoveda až po novom nesprávnom pokuse

Idempotentná migrácia (tabuľky/stĺpce sa vytvoria, len ak ešte neexistujú).

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "course_materials" not in tables:
        op.create_table(
            "course_materials",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("kind", sa.String(20), nullable=False, server_default="prednaska"),
            sa.Column("title", sa.String(255), nullable=False, server_default=""),
            sa.Column("original_name", sa.String(255), nullable=False),
            sa.Column("stored_name", sa.String(255), nullable=False, unique=True),
            sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sha256", sa.String(64), nullable=False),
            sa.Column("lecture_no", sa.Integer(), nullable=True),
            sa.Column("weight", sa.Float(), nullable=True),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("use_in_assistant", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("visible_to_students", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("chunks", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("embed_model", sa.String(100), nullable=True),
            sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("indexed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_course_materials_sha256", "course_materials", ["sha256"])

    if "assistant_conversations" not in tables:
        op.create_table(
            "assistant_conversations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
            sa.Column("mode", sa.String(20), nullable=False),
            sa.Column("context_key", sa.String(60), nullable=False),
            sa.Column("exercise_id", sa.Integer(), nullable=True),
            sa.Column("assignment_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("student_id", "context_key", name="uq_assistant_conv_context"),
        )
        op.create_index("ix_assistant_conversations_student_id", "assistant_conversations", ["student_id"])
        op.create_index("ix_assistant_conversations_exercise_id", "assistant_conversations", ["exercise_id"])
        op.create_index("ix_assistant_conversations_assignment_id", "assistant_conversations", ["assignment_id"])
        op.create_index("ix_assistant_conversations_updated_at", "assistant_conversations", ["updated_at"])

    if "assistant_messages" not in tables:
        op.create_table(
            "assistant_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("assistant_conversations.id"),
                      nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("kind", sa.String(20), nullable=False, server_default="chat"),
            sa.Column("text", sa.Text(), nullable=False, server_default=""),
            sa.Column("hint_level", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="ok"),
            sa.Column("model", sa.String(100), nullable=True),
            sa.Column("think", sa.String(20), nullable=True),
            sa.Column("prompt_version", sa.String(20), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("first_token_ms", sa.Integer(), nullable=True),
            sa.Column("tokens_in", sa.Integer(), nullable=True),
            sa.Column("tokens_out", sa.Integer(), nullable=True),
            sa.Column("guard_json", sa.Text(), nullable=True),
            sa.Column("guard_hits", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("context_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_assistant_messages_conversation_id", "assistant_messages", ["conversation_id"])
        op.create_index("ix_assistant_messages_created_at", "assistant_messages", ["created_at"])

    if "assistant_sources" not in tables:
        op.create_table(
            "assistant_sources",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("message_id", sa.Integer(), sa.ForeignKey("assistant_messages.id"), nullable=False),
            sa.Column("rank", sa.Integer(), nullable=False),
            sa.Column("material_id", sa.Integer(), nullable=True),
            sa.Column("chunk_id", sa.String(40), nullable=False),
            sa.Column("source_type", sa.String(20), nullable=False),
            sa.Column("lecture_no", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(255), nullable=False, server_default=""),
            sa.Column("location", sa.String(120), nullable=False, server_default=""),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("signals", sa.String(255), nullable=True),
            sa.Column("snippet", sa.Text(), nullable=True),
        )
        op.create_index("ix_assistant_sources_message_id", "assistant_sources", ["message_id"])
        op.create_index("ix_assistant_sources_material_id", "assistant_sources", ["material_id"])

    cols = {c["name"] for c in inspector.get_columns("task_assignments")}
    if "last_hint_wrong" not in cols:
        op.add_column("task_assignments",
                      sa.Column("last_hint_wrong", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("task_assignments", "last_hint_wrong")
    op.drop_table("assistant_sources")
    op.drop_table("assistant_messages")
    op.drop_table("assistant_conversations")
    op.drop_table("course_materials")
