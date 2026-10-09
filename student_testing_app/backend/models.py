from datetime import datetime, timezone
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Študent (UserMixin = integrácia s Flask-Login: current_user, login_user, ...)
class Student(UserMixin, db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
    login = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # Rola používateľa: "user" (predvolená) alebo "admin"
    role = db.Column(db.String(20), nullable=False, default="user")

    # Reset hesla
    reset_token_hash = db.Column(db.String(255), nullable=True)
    reset_token_expires_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    answers = db.relationship("StudentAnswer", backref="student", lazy=True)
    summaries = db.relationship("TestSummary", backref="student", lazy=True)

    @property
    def is_admin(self) -> bool:
        return (self.role or "user") == "admin"

    def set_password(self, raw_password: str) -> None:
        # scrypt (werkzeug default) - pomalá, memory-hard funkcia odolná voči brute-force útokom
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

# Otázky
class Question(db.Model):
    __tablename__ = "questions"
    id = db.Column(db.Integer, primary_key=True)
    instruction = db.Column(db.Text, nullable=False)
    input_data = db.Column(db.Text)
    output = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    subcategory = db.Column(db.String(100))
    incorrect_output = db.Column(db.Text)

    answers = db.relationship("StudentAnswer", backref="question", lazy=True)

# Odpovede študenta
class StudentAnswer(db.Model):
    __tablename__ = "student_answers"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    answer_code = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    test_type = db.Column(db.String, default="main")
    test_session = db.Column(db.String, nullable=True)

# Agregovaná metrika
class TestSummary(db.Model):
    __tablename__ = "test_summaries"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    test_type = db.Column(db.String, nullable=False)
    test_session = db.Column(db.String, nullable=True)
    category = db.Column(db.String, nullable=False)
    total_answers = db.Column(db.Integer, default=0)
    correct_answers = db.Column(db.Integer, default=0)
    incorrect_answers = db.Column(db.Integer, default=0)

    @property
    def accuracy(self):
        if self.total_answers == 0:
            return 0.0
        return round(self.correct_answers / self.total_answers, 2)
    
# Progres hlavného testu: jedna session = jeden rozpracovaný/dokončený test.
# Uchováva otázku, ktorá bola študentovi zobrazená, ale ešte na ňu neodpovedal,
# aby sa mu po návrate zobrazila tá istá (a nevybrala sa nová).
# (Progres predtestu sa odvodzuje priamo zo StudentAnswer - pevný zoznam otázok.)
class TestProgress(db.Model):
    __tablename__ = "test_progress"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    test_type = db.Column(db.String, nullable=False, default="main")
    test_session = db.Column(db.String, nullable=False)
    current_question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=True)
    total_questions = db.Column(db.Integer, nullable=False, default=30)
    status = db.Column(db.String(20), nullable=False, default="in_progress")  # in_progress | done
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    __table_args__ = (
        db.UniqueConstraint("student_id", "test_type", "test_session", name="uq_progress_student_type_session"),
        # poistka na úrovni DB: študent má najviac jeden rozpracovaný test daného typu
        db.Index(
            "uq_progress_one_active", "student_id", "test_type", unique=True,
            postgresql_where=db.text("status = 'in_progress'"),
            sqlite_where=db.text("status = 'in_progress'"),
        ),
    )

# Počet použitých opráv na otázku (perzistentné - prežije reštart/viac workerov).
# test_session je pre predtest prázdny reťazec (nie NULL, kvôli unikátnosti).
class AnswerAttempt(db.Model):
    __tablename__ = "answer_attempts"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    test_type = db.Column(db.String, nullable=False)
    test_session = db.Column(db.String, nullable=False, default="")
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    __table_args__ = (
        db.UniqueConstraint("student_id", "test_type", "test_session", "question_id", name="uq_attempt_key"),
    )

# Dotazník
class StudentFeedback(db.Model):
    __tablename__ = "student_feedback"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    gender = db.Column(db.String(20))
    age = db.Column(db.Integer)
    experience = db.Column(db.String(50))
    field_of_study = db.Column(db.String(100))
    understand_questions = db.Column(db.String(20))
    easy_navigation = db.Column(db.String(20))
    motivation_level = db.Column(db.String(20))
    helpful_feedback = db.Column(db.String(20))
    overall_usefulness = db.Column(db.String(20))
    difficulty_match = db.Column(db.String(20))
    improved_skills = db.Column(db.String(20))
    time_spent = db.Column(db.String(50))
    future_interest = db.Column(db.String(20))
    ui_satisfaction = db.Column(db.String(20))
    improvement_suggestion = db.Column(db.Text)


# ===== Dynamický dotazník (spravovateľný adminom) =====

# Otázka dotazníka - admin ich môže pridávať/upravovať/mazať.
class FeedbackQuestion(db.Model):
    __tablename__ = "feedback_questions"
    id = db.Column(db.Integer, primary_key=True)
    # kľúč otázky (stabilný identifikátor pre odpovede), napr. "gender"
    qkey = db.Column(db.String(60), unique=True, nullable=False)
    # text otázky SK / EN
    label_sk = db.Column(db.Text, nullable=False)
    label_en = db.Column(db.Text, nullable=False)
    # typ: "select" (výber z možností), "text", "number", "textarea"
    qtype = db.Column(db.String(20), nullable=False, default="select")
    # možnosti pre select - JSON pole reťazcov (napr. ["Áno","Nie"]); inak prázdne
    options_json = db.Column(db.Text, nullable=True)
    required = db.Column(db.Boolean, default=True)
    # poradie zobrazenia
    position = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)

# Odpoveď študenta na dynamický dotazník (kľúč-hodnota).
class FeedbackResponse(db.Model):
    __tablename__ = "feedback_responses"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    qkey = db.Column(db.String(60), nullable=False)
    value = db.Column(db.Text, nullable=True)
    __table_args__ = (db.UniqueConstraint("student_id", "qkey", name="uq_student_qkey"),)


# ===== Nastavenia aplikácie (kľúč-hodnota) =====
# Napr. "questionnaire_published" = "true"/"false" - či je dotazník zverejnený.
class AppSetting(db.Model):
    __tablename__ = "app_settings"
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ===== Voľná spätná väzba (feedback formulár - je dostupný vždy) =====
class FeedbackMessage(db.Model):
    __tablename__ = "feedback_messages"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    category = db.Column(db.String(20), nullable=False, default="other")  # bug | idea | praise | other
    rating = db.Column(db.SmallInteger, nullable=True)                    # 1-5 hviezdičky (nepovinné)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
