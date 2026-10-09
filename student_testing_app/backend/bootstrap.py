# ============================================================
# AdaptPy - jednorazové naplnenie DB po štarte:  flask bootstrap
#
# Spúšťa sa RAZ pred štartom workerov (pozri entrypoint.sh), nie pri importe
# aplikácie - inak by ho paralelne spúšťali všetky gunicorn workery.
# Všetky kroky sú idempotentné (bezpečné spustiť opakovane).
# ============================================================
import json
import os

import click
import pandas as pd

from models import db, Student, Question, FeedbackQuestion

QUESTIONS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "final_dataset.csv")

_YES_NO = ["Áno", "Skôr áno", "Skôr nie", "Nie"]
# (kľúč, text SK, text EN, typ, možnosti)
_FEEDBACK_SEED = [
    ("gender", "Aké je tvoje pohlavie?", "What is your gender?", "select", ["Muž", "Žena", "Iné", "Nechcem uviesť"]),
    ("age", "Aký je tvoj vek?", "What is your age?", "number", []),
    ("experience", "Akú máš skúsenosť s programovaním?", "What is your programming experience?", "select", ["Žiadna", "Základná", "Pokročilá", "Profesionálna"]),
    ("field_of_study", "Aký je tvoj študijný odbor?", "What is your field of study?", "text", []),
    ("understand_questions", "Rozumel/a si úlohám?", "Did you understand the tasks?", "select", _YES_NO),
    ("easy_navigation", "Bolo používanie aplikácie pre teba intuitívne?", "Was using the app intuitive?", "select", _YES_NO),
    ("motivation_level", "Ako by si ohodnotil/a svoju motiváciu?", "How would you rate your motivation?", "select", ["Vysoká", "Skôr vysoká", "Skôr nízka", "Nízka"]),
    ("helpful_feedback", "Pomohla ti spätná väzba k odpovediam?", "Did the feedback help you?", "select", _YES_NO),
    ("overall_usefulness", "Bol pre teba test užitočný?", "Was the test useful?", "select", _YES_NO),
    ("difficulty_match", "Boli úlohy primerané tvojej úrovni?", "Did tasks match your level?", "select", _YES_NO),
    ("improved_skills", "Myslíš si, že si sa zlepšil/a?", "Do you think you improved?", "select", _YES_NO),
    ("time_spent", "Koľko času si venoval/a testu?", "How much time did you spend?", "select", ["Menej ako 20 minút", "20 – 40 minút", "40 – 60 minút", "Viac ako 1 hodina"]),
    ("future_interest", "Chcel/a by si riešiť viac úloh?", "Would you like more tasks?", "select", _YES_NO),
    ("ui_satisfaction", "Bol dizajn aplikácie vyhovujúci?", "Was the app design satisfactory?", "select", _YES_NO),
    ("improvement_suggestion", "Máš návrhy na zlepšenie?", "Any suggestions for improvement?", "textarea", []),
]


def seed_questions():
    """Načíta otázky z final_dataset.csv, ak je tabuľka questions prázdna."""
    if Question.query.first():
        return print("[seed] otázky už existujú - preskakujem")
    if not os.path.exists(QUESTIONS_CSV):
        return print(f"[seed] {QUESTIONS_CSV} neexistuje - otázky nenačítané")

    df = pd.read_csv(QUESTIONS_CSV)
    df = df.astype(object).where(df.notna(), None)   # NaN -> NULL
    db.session.add_all(
        Question(
            id=int(row["ID"]),
            instruction=row["Instruction"],
            input_data=str(row["Input"]),
            output=row["Output"],
            category=row["Category"],
            subcategory=row["Subcategory"],
            incorrect_output=row["IncorrectOutput"],
        )
        for _, row in df.iterrows()
    )
    db.session.commit()
    print(f"[seed] načítaných {len(df)} otázok")


def seed_feedback_questions():
    """Prvotné naplnenie dotazníka (potom ho spravuje admin)."""
    if FeedbackQuestion.query.first():
        return
    for position, (qkey, sk, en, qtype, options) in enumerate(_FEEDBACK_SEED):
        db.session.add(FeedbackQuestion(
            qkey=qkey, label_sk=sk, label_en=en, qtype=qtype,
            options_json=json.dumps(options, ensure_ascii=False),
            required=(qtype != "textarea"), position=position, active=True,
        ))
    db.session.commit()
    print(f"[seed] dotazník: {len(_FEEDBACK_SEED)} otázok")


def seed_admin():
    """Admin účet z .env (ADMIN_LOGIN, ADMIN_PASSWORD, ADMIN_EMAIL, ADMIN_NAME, ADMIN_SURNAME)."""
    login = os.getenv("ADMIN_LOGIN")
    password = os.getenv("ADMIN_PASSWORD")
    if not login or not password:
        return print("[seed] ADMIN_LOGIN/ADMIN_PASSWORD nie sú v .env - admin účet preskočený")

    email = os.getenv("ADMIN_EMAIL", "admin@adaptpy.local")
    # login aj e-mail sú unikátne -> hľadáme podľa oboch, inak by vznikla kolízia
    admin = Student.query.filter((Student.login == login) | (Student.email == email)).first()
    if admin is None:
        admin = Student(
            name=os.getenv("ADMIN_NAME", "Admin"),
            surname=os.getenv("ADMIN_SURNAME", "AdaptPy"),
            login=login, email=email, role="admin",
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"[seed] vytvorený admin účet ({login})")
    elif not admin.is_admin:
        admin.role = "admin"
        db.session.commit()
        print("[seed] existujúcemu účtu nastavená rola admin")


def sync_exercises():
    from services.notebook_scan import sync_exercises as scan
    try:
        scan()
    except Exception as e:      # chýbajúci priečinok s cvičeniami nesmie zhodiť štart
        print(f"[cvičenia] sken priečinka preskočený: {e}")


def register_cli(app):
    @app.cli.command("bootstrap")
    def bootstrap():
        """Naplní DB (otázky, dotazník, admin, cvičenia). Spúšťať po `flask db upgrade`."""
        seed_questions()
        seed_feedback_questions()
        seed_admin()
        sync_exercises()
        click.echo("bootstrap hotový")
