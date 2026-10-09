"""baseline: schéma aplikácie (cvičenia, pozvánky, testy, dotazník)

Základ migrácií. Je IDEMPOTENTNÝ, aby fungoval na prázdnej DB aj na DB, ktorá
vznikla ešte cez db.create_all() a ručné ALTER TABLE:
  - chýbajúca tabuľka sa vytvorí,
  - existujúcej tabuľke sa doplnia chýbajúce stĺpce
    (students.role, exercises.run_timeout, exercise_progress.answers_json, ...).
Existujúce dáta sa nemenia.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _ensure_table(name, *items, indexes=()):
    """Vytvorí tabuľku, alebo jej doplní chýbajúce stĺpce (items = Column/constraints)."""
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(name):
        op.create_table(name, *items)
        for index_name, columns, unique in indexes:
            op.create_index(index_name, name, columns, unique=unique)
        return
    existing = {c["name"] for c in inspector.get_columns(name)}
    for item in items:
        if isinstance(item, sa.Column) and item.name not in existing:
            op.add_column(name, item)


def upgrade():
    _ensure_table(
        "students",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("surname", sa.String(100), nullable=False),
        sa.Column("login", sa.String(50), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("reset_token_hash", sa.String(255)),
        sa.Column("reset_token_expires_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("login"),
        sa.UniqueConstraint("email"),
    )
    _ensure_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("input_data", sa.Text()),
        sa.Column("output", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("subcategory", sa.String(100)),
        sa.Column("incorrect_output", sa.Text()),
    )
    _ensure_table(
        "student_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("answer_code", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("test_type", sa.String()),
        sa.Column("test_session", sa.String()),
    )
    _ensure_table(
        "test_summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("test_type", sa.String(), nullable=False),
        sa.Column("test_session", sa.String()),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("total_answers", sa.Integer()),
        sa.Column("correct_answers", sa.Integer()),
        sa.Column("incorrect_answers", sa.Integer()),
    )
    _ensure_table(
        "student_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("gender", sa.String(20)),
        sa.Column("age", sa.Integer()),
        sa.Column("experience", sa.String(50)),
        sa.Column("field_of_study", sa.String(100)),
        sa.Column("understand_questions", sa.String(20)),
        sa.Column("easy_navigation", sa.String(20)),
        sa.Column("motivation_level", sa.String(20)),
        sa.Column("helpful_feedback", sa.String(20)),
        sa.Column("overall_usefulness", sa.String(20)),
        sa.Column("difficulty_match", sa.String(20)),
        sa.Column("improved_skills", sa.String(20)),
        sa.Column("time_spent", sa.String(50)),
        sa.Column("future_interest", sa.String(20)),
        sa.Column("ui_satisfaction", sa.String(20)),
        sa.Column("improvement_suggestion", sa.Text()),
    )
    _ensure_table(
        "feedback_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("qkey", sa.String(60), nullable=False),
        sa.Column("label_sk", sa.Text(), nullable=False),
        sa.Column("label_en", sa.Text(), nullable=False),
        sa.Column("qtype", sa.String(20), nullable=False),
        sa.Column("options_json", sa.Text()),
        sa.Column("required", sa.Boolean()),
        sa.Column("position", sa.Integer()),
        sa.Column("active", sa.Boolean()),
        sa.UniqueConstraint("qkey"),
    )
    _ensure_table(
        "feedback_responses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("qkey", sa.String(60), nullable=False),
        sa.Column("value", sa.Text()),
        sa.UniqueConstraint("student_id", "qkey", name="uq_student_qkey"),
    )
    _ensure_table(
        "exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("order_index", sa.Integer()),
        sa.Column("title_sk", sa.String(255), nullable=False),
        sa.Column("title_en", sa.String(255), nullable=False),
        sa.Column("description_sk", sa.Text()),
        sa.Column("description_en", sa.Text()),
        sa.Column("topics_json", sa.Text()),
        sa.Column("code_cells", sa.Integer()),
        sa.Column("published", sa.Boolean()),
        sa.Column("accessible", sa.Boolean()),
        sa.Column("run_timeout", sa.Integer()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.UniqueConstraint("slug"),
    )
    _ensure_table(
        "exercise_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"), nullable=False),
        sa.Column("done_cells_json", sa.Text()),
        sa.Column("answers_json", sa.Text()),
        sa.Column("percent", sa.Integer()),
        sa.Column("status", sa.String(20)),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.UniqueConstraint("student_id", "exercise_id", name="uq_student_exercise"),
    )
    _ensure_table(
        "invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(100)),
        sa.Column("surname", sa.String(100)),
        sa.Column("group_name", sa.String(100)),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("created_by", sa.Integer()),
        sa.Column("last_sent_at", sa.DateTime()),
        sa.Column("send_count", sa.Integer()),
        sa.Column("used_at", sa.DateTime()),
        sa.Column("student_id", sa.Integer()),
        indexes=[
            ("ix_invitations_email", ["email"], True),
            ("ix_invitations_token_hash", ["token_hash"], False),
        ],
    )


def downgrade():
    # Základná schéma sa zámerne nevracia: `downgrade base` by zmazal všetky dáta.
    raise NotImplementedError("Baseline migráciu nie je možné vrátiť späť.")
