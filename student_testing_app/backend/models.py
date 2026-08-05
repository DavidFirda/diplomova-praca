from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Študent
class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    login = db.Column(db.String(50), unique=True, nullable=False)

    answers = db.relationship("StudentAnswer", backref="student", lazy=True)
    summaries = db.relationship("TestSummary", backref="student", lazy=True)

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
