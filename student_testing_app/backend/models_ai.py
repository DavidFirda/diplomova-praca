# ============================================================
# AdaptPy - modely pre AI ASISTENTA a MATERIÁLY KURZU (RAG).
#
#  - CourseMaterial:        nahratý materiál (prednáška, kniha), z ktorého čerpá RAG.
#                           Súbor leží v MATERIALS_DIR, kúsky a vektory v RAG_INDEX_DIR.
#  - AssistantConversation: jedna konverzácia študenta s asistentom v danom kontexte
#                           (dashboard | cvičenie <id> | úloha <assignment_id>).
#  - AssistantMessage:      správa (študent / asistent / udalosť, napr. vloženie kódu),
#                           s modelom, časmi, tokenmi a zásahmi strážcu.
#  - AssistantSource:       z ktorých kúskov materiálov RAG čerpal pri danej odpovedi.
#
# Schému spravujú migrácie (backend/migrations, 0009_ai_assistant).
# ============================================================
from datetime import datetime, timezone

from models import db


def _now():
    return datetime.now(timezone.utc)


class CourseMaterial(db.Model):
    __tablename__ = "course_materials"
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False, default="prednaska")   # prednaska | kniha
    title = db.Column(db.String(255), nullable=False, default="")
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False, unique=True)   # názov súboru v MATERIALS_DIR
    size_bytes = db.Column(db.Integer, nullable=False, default=0)
    sha256 = db.Column(db.String(64), nullable=False, index=True)
    lecture_no = db.Column(db.Integer, nullable=True)          # číslo prednášky (z názvu súboru)
    weight = db.Column(db.Float, nullable=True)                # None = predvolená váha podľa typu
    position = db.Column(db.Integer, nullable=False, default=0)

    use_in_assistant = db.Column(db.Boolean, nullable=False, default=True)
    visible_to_students = db.Column(db.Boolean, nullable=False, default=False)

    # pending | indexing | ready | error
    status = db.Column(db.String(20), nullable=False, default="pending")
    chunks = db.Column(db.Integer, nullable=False, default=0)
    error = db.Column(db.Text, nullable=True)
    embed_model = db.Column(db.String(100), nullable=True)

    uploaded_by = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)
    indexed_at = db.Column(db.DateTime, nullable=True)


class AssistantConversation(db.Model):
    __tablename__ = "assistant_conversations"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    mode = db.Column(db.String(20), nullable=False)             # dashboard | exercise | task
    # "dashboard", "exercise:<id>", "task:<assignment_id>" - jedna konverzácia na kontext
    context_key = db.Column(db.String(60), nullable=False)
    exercise_id = db.Column(db.Integer, nullable=True, index=True)
    assignment_id = db.Column(db.Integer, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, index=True)

    __table_args__ = (
        db.UniqueConstraint("student_id", "context_key", name="uq_assistant_conv_context"),
    )


class AssistantMessage(db.Model):
    __tablename__ = "assistant_messages"
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("assistant_conversations.id"),
                                nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)             # student | assistant | event
    # chat | hint | greeting | insert (študent vložil kód z odpovede do bunky/editora)
    kind = db.Column(db.String(20), nullable=False, default="chat")
    text = db.Column(db.Text, nullable=False, default="")
    hint_level = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="ok")   # ok | error | fallback

    model = db.Column(db.String(100), nullable=True)
    think = db.Column(db.String(20), nullable=True)
    prompt_version = db.Column(db.String(20), nullable=True)
    latency_ms = db.Column(db.Integer, nullable=True)           # celá odpoveď
    first_token_ms = db.Column(db.Integer, nullable=True)       # prvé slovo
    tokens_in = db.Column(db.Integer, nullable=True)
    tokens_out = db.Column(db.Integer, nullable=True)

    guard_json = db.Column(db.Text, nullable=True)              # zásahy strážcu [{"rule", ...}]
    guard_hits = db.Column(db.Integer, nullable=False, default=0)
    context_json = db.Column(db.Text, nullable=True)            # bunka, dĺžka kódu, retrieval dotaz...
    created_at = db.Column(db.DateTime, default=_now, index=True)


class AssistantSource(db.Model):
    __tablename__ = "assistant_sources"
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("assistant_messages.id"), nullable=False, index=True)
    rank = db.Column(db.Integer, nullable=False)
    # bez cudzieho kľúča: log prežije aj zmazanie materiálu
    material_id = db.Column(db.Integer, nullable=True, index=True)
    chunk_id = db.Column(db.String(40), nullable=False)
    source_type = db.Column(db.String(20), nullable=False)      # prednaska | kniha
    lecture_no = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(255), nullable=False, default="")
    location = db.Column(db.String(120), nullable=False, default="")
    score = db.Column(db.Float, nullable=True)
    signals = db.Column(db.String(255), nullable=True)          # poradie v jednotlivých signáloch
    snippet = db.Column(db.Text, nullable=True)
