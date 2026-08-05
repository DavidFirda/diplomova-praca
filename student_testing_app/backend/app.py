import os
import sys
from datetime import timedelta

from flask import Flask, Response, send_from_directory
from flask_cors import CORS
from flask_session import Session

from routes.api_routes import api_bp
from routes.admin_routes import admin_bp
from routes.auth_routes import auth_bp
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
app.config['SESSION_PERMANENT'] = True
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

# ===== Registrácia API Blueprintov =====
app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(api_bp, url_prefix="/api")
app.register_blueprint(admin_bp, url_prefix="/admin")

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
    "predtest": "predtest.html",
    "hlavnytest": "hlavnytest.html",
    "analyza": "analyza.html",
    "feedback": "feedback.html",
    "feedback-visualization": "feedback_visualization.html",
    "algorithm-comparison": "algorithm_comparison.html",
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
    return send_from_directory(os.path.join(FRONTEND_FOLDER, "css"), filename)

@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory(os.path.join(FRONTEND_FOLDER, "js"), filename)

@app.route("/health")
def health():
    return "OK", 200

@app.errorhandler(404)
def not_found(e):
    return send_from_directory(PAGES_FOLDER, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)