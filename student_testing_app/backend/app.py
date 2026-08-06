import os
import sys
from datetime import timedelta

from flask import Flask, Response, send_from_directory
from flask_cors import CORS
from flask_session import Session

from routes.api_routes import api_bp
from routes.admin_routes import admin_bp
from routes.auth_routes import auth_bp
from routes.admin_api_routes import admin_api_bp
from models import db
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_FOLDER = os.path.join(BASE_DIR, "../frontend")

app = Flask(
    __name__,
    static_folder=FRONTEND_FOLDER,
    template_folder=FRONTEND_FOLDER
)

secret_key = os.environ.get("FLASK_SECRET_KEY")
if not secret_key:
    raise RuntimeError(
        "FLASK_SECRET_KEY nie je nastavený v .env! Bez neho by boli session "
        "cookies podpísané predvídateľným kľúčom, čo je bezpečnostné riziko."
    )
app.secret_key = secret_key

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL nie je nastavený v .env!")
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['ADMIN_TOKEN'] = os.getenv("ADMIN_TOKEN")

# URL, na ktorú sa v emaili s resetom hesla generuje odkaz na reset-password.html
app.config['FRONTEND_BASE_URL'] = os.getenv("FRONTEND_BASE_URL", "http://localhost:5000")

# ===== Bezpečné, server-side session (uložené v Postgres, nie len v cookie) =====
# Vďaka tomu appka prežije reštart backendu aj beh na viacerých workeroch,
# a do session sa dá bezpečne ukladať aj priebeh testu (nie len 4KB cookie limit).
app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SESSION_SQLALCHEMY'] = db
app.config['SESSION_SQLALCHEMY_TABLE'] = 'flask_sessions'
# SESSION_PERMANENT = False => session cookie zanikne pri zatvorení prehliadača,
# takže po zavretí karty/okna sa musí používateľ znova prihlásiť.
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_USE_SIGNER'] = True  # cookie obsahuje len podpísané session ID, nie dáta

# Cookie nastavenia proti XSS/CSRF krádeži session cookie:
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# V produkcii (https) nastav SESSION_COOKIE_SECURE=true v .env, aby sa cookie
# posielala len cez HTTPS. Lokálne (http://localhost) musí ostať false.
app.config['SESSION_COOKIE_SECURE'] = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"

CORS(app, supports_credentials=True)

with app.app_context():
    db.init_app(app)
    db.create_all()
    Session(app)
    db.create_all()  # znova, aby sa vytvorila aj tabuľka flask_sessions z Flask-Session

    # Jednoduchá migrácia: pridaj stĺpec 'role' do students, ak ešte neexistuje.
    # (db.create_all nepridáva stĺpce do existujúcich tabuliek.)
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        cols = [c["name"] for c in inspector.get_columns("students")]
        if "role" not in cols:
            with db.engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE students ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"
                ))
            print("[migrácia] Pridaný stĺpec students.role")
    except Exception as e:
        print(f"[migrácia] role stĺpec - preskočené/chyba: {e}")

    # Seed dotazníkových otázok, ak tabuľka je prázdna (prvotné naplnenie
    # pôvodnými 15 otázkami, aby dotazník fungoval hneď a admin ich mohol upravovať).
    try:
        from models import FeedbackQuestion
        import json as _json
        if FeedbackQuestion.query.count() == 0:
            yn = ["Áno", "Skôr áno", "Skôr nie", "Nie"]
            seed = [
                ("gender", "Aké je tvoje pohlavie?", "What is your gender?", "select", ["Muž", "Žena", "Iné", "Nechcem uviesť"]),
                ("age", "Aký je tvoj vek?", "What is your age?", "number", []),
                ("experience", "Akú máš skúsenosť s programovaním?", "What is your programming experience?", "select", ["Žiadna", "Základná", "Pokročilá", "Profesionálna"]),
                ("field_of_study", "Aký je tvoj študijný odbor?", "What is your field of study?", "text", []),
                ("understand_questions", "Rozumel/a si úlohám?", "Did you understand the tasks?", "select", yn),
                ("easy_navigation", "Bolo používanie aplikácie pre teba intuitívne?", "Was using the app intuitive?", "select", yn),
                ("motivation_level", "Ako by si ohodnotil/a svoju motiváciu?", "How would you rate your motivation?", "select", ["Vysoká", "Skôr vysoká", "Skôr nízka", "Nízka"]),
                ("helpful_feedback", "Pomohla ti spätná väzba k odpovediam?", "Did the feedback help you?", "select", yn),
                ("overall_usefulness", "Bol pre teba test užitočný?", "Was the test useful?", "select", yn),
                ("difficulty_match", "Boli úlohy primerané tvojej úrovni?", "Did tasks match your level?", "select", yn),
                ("improved_skills", "Myslíš si, že si sa zlepšil/a?", "Do you think you improved?", "select", yn),
                ("time_spent", "Koľko času si venoval/a testu?", "How much time did you spend?", "select", ["Menej ako 20 minút", "20 – 40 minút", "40 – 60 minút", "Viac ako 1 hodina"]),
                ("future_interest", "Chcel/a by si riešiť viac úloh?", "Would you like more tasks?", "select", yn),
                ("ui_satisfaction", "Bol dizajn aplikácie vyhovujúci?", "Was the app design satisfactory?", "select", yn),
                ("improvement_suggestion", "Máš návrhy na zlepšenie?", "Any suggestions for improvement?", "textarea", []),
            ]
            for i, (qkey, sk, en, qtype, opts) in enumerate(seed):
                db.session.add(FeedbackQuestion(
                    qkey=qkey, label_sk=sk, label_en=en, qtype=qtype,
                    options_json=_json.dumps(opts, ensure_ascii=False),
                    required=(qtype != "textarea"), position=i, active=True,
                ))
            db.session.commit()
            print("[seed] Naplnených 15 dotazníkových otázok")
    except Exception as e:
        print(f"[seed] dotazník otázky - preskočené/chyba: {e}")

    # Automatické vytvorenie admin účtu, ak ešte neexistuje.
    # Login: Admin | Heslo: pythonadmin | Rola: admin
    try:
        from models import Student
        admin = Student.query.filter_by(login="Admin").first()
        if not admin:
            admin = Student(
                name="Admin",
                surname="AdaptPy",
                login="Admin",
                email="admin@adaptpy.local",
                role="admin",
            )
            admin.set_password("pythonadmin")
            db.session.add(admin)
            db.session.commit()
            print("[seed] Vytvorený admin účet (login: Admin, heslo: pythonadmin)")
        elif getattr(admin, "role", "user") != "admin":
            # ak účet Admin existuje ale nemá admin rolu, oprav to
            admin.role = "admin"
            db.session.commit()
            print("[seed] Účtu Admin nastavená rola admin")
    except Exception as e:
        print(f"[seed] admin účet - preskočené/chyba: {e}")

# ===== Registrácia API Blueprintov =====
app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(api_bp, url_prefix="/api")
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(admin_api_bp, url_prefix="/api/admin")

# ===== Frontend Routy =====

# ===== Frontend Routy =====
PAGES_FOLDER = os.path.join(FRONTEND_FOLDER, "pages")

# Mapa "čistá URL" -> "súbor v pages/". Vďaka tomu vieme fyzicky
# reorganizovať frontend (pages/js/css) bez toho, aby sa menili URL,
# na ktoré appka odkazuje.
PAGE_ROUTES = {
    "": "index.html",
    "login": "login.html",
    "register": "register.html",
    "forgot-password": "forgot-password.html",
    "reset-password": "reset-password.html",
    "change-password": "change-password.html",
    "dashboard": "dashboard.html",
    "profile": "profile.html",
    "predtest": "predtest.html",
    "hlavnytest": "hlavnytest.html",
    "analyza": "analyza.html",
    "feedback": "feedback.html",
    "feedback-visualization": "feedback_visualization.html",
    "algorithm-comparison": "algorithm_comparison.html",
    "admin-users": "admin_users.html",
    "admin-feedback": "admin_feedback.html",
}

for route_path, page_file in PAGE_ROUTES.items():
    def _make_page_view(filename):
        def _view():
            return send_from_directory(PAGES_FOLDER, filename)
        return _view

    app.add_url_rule(
        f"/{route_path}",
        endpoint=f"page_{route_path or 'index'}",
        view_func=_make_page_view(page_file),
    )

@app.route("/config.js")
def serve_config():
    access_code = os.getenv("APP_ACCESS_CODE", "")
    admin_token = os.getenv("ADMIN_TOKEN", "")
    js = f"""
        const ACCESS_CODE = '{access_code}';
        const token = '{admin_token}';
    """
    return Response(js.strip(), mimetype="application/javascript")

@app.route("/css/<path:filename>")
def serve_css(filename):
    resp = send_from_directory(os.path.join(FRONTEND_FOLDER, "css"), filename)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

@app.route("/js/<path:filename>")
def serve_js(filename):
    resp = send_from_directory(os.path.join(FRONTEND_FOLDER, "js"), filename)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory(os.path.join(FRONTEND_FOLDER, "assets"), filename)

@app.route("/health")
def health():
    return "OK", 200

@app.errorhandler(404)
def not_found(e):
    return send_from_directory(PAGES_FOLDER, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)