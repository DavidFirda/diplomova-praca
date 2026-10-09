import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, Response, send_from_directory
from flask_cors import CORS
from flask_session import Session

from bootstrap import register_cli
from extensions import login_manager, migrate
from models import db

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_FOLDER = os.path.join(BASE_DIR, "../frontend")
PAGES_FOLDER = os.path.join(FRONTEND_FOLDER, "pages")
MIGRATIONS_DIR = os.path.join(BASE_DIR, "migrations")

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
    "feedback-form": "feedback_form.html",
    "feedback-visualization": "feedback_visualization.html",
    "algorithm-comparison": "algorithm_comparison.html",
    "admin-users": "admin_users.html",
    "admin-feedback": "admin_feedback.html",
    "cvicenia": "cvicenia.html",
    "cvicenie": "cvicenie.html",
    "admin-exercises": "admin_exercises.html",
    "admin-user-exercises": "admin_user_exercises.html",
}


def _require_env(name, why):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} nie je nastavený v .env! {why}")
    return value


def create_app():
    app = Flask(__name__, static_folder=FRONTEND_FOLDER, template_folder=FRONTEND_FOLDER)

    app.secret_key = _require_env(
        "FLASK_SECRET_KEY",
        "Bez neho by boli session cookies podpísané predvídateľným kľúčom.",
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = _require_env("DATABASE_URL", "Pozri .env.example.")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Connection pool - drží otvorené spojenia na DB (Neon), aby sa pri každom
    # requeste neotváralo nové. pool_pre_ping overí, či je spojenie živé.
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 280,      # Neon zatvára nečinné spojenia
        "pool_pre_ping": True,
        "pool_timeout": 30,
    }
    app.config["ADMIN_TOKEN"] = os.getenv("ADMIN_TOKEN")
    # URL, z ktorej sa generuje odkaz na reset hesla v e-maile
    app.config["FRONTEND_BASE_URL"] = os.getenv("FRONTEND_BASE_URL", "http://localhost:5000")

    # Server-side session v DB (cookie nesie len podpísané session ID). Vďaka tomu
    # appka prežije reštart aj beh na viacerých workeroch.
    app.config["SESSION_TYPE"] = "sqlalchemy"
    app.config["SESSION_SQLALCHEMY"] = db
    app.config["SESSION_SQLALCHEMY_TABLE"] = "flask_sessions"
    app.config["SESSION_PERMANENT"] = False     # cookie zanikne po zatvorení prehliadača
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
    app.config["SESSION_USE_SIGNER"] = True
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # V produkcii (https) nastav SESSION_COOKIE_SECURE=true; lokálne (http) musí byť false.
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"

    db.init_app(app)
    migrate.init_app(app, db, directory=MIGRATIONS_DIR)
    login_manager.init_app(app)
    Session(app)
    CORS(app, supports_credentials=True)
    register_cli(app)

    _register_blueprints(app)
    _register_frontend(app)
    return app


def _register_blueprints(app):
    from routes.admin_api_routes import admin_api_bp
    from routes.admin_exercise_routes import admin_exercise_bp
    from routes.admin_routes import admin_bp
    from routes.api_routes import api_bp
    from routes.auth_routes import auth_bp
    from routes.exercise_routes import exercise_bp
    from routes.invite_routes import invite_admin_bp, invite_public_bp
    import models_exercises  # noqa: F401  (modely sa musia načítať pre migrácie)
    import models_invites    # noqa: F401

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(admin_api_bp, url_prefix="/api/admin")
    app.register_blueprint(exercise_bp, url_prefix="/api/exercises")
    app.register_blueprint(admin_exercise_bp, url_prefix="/api/admin/exercises")
    app.register_blueprint(invite_public_bp, url_prefix="/api/invites")
    app.register_blueprint(invite_admin_bp, url_prefix="/api/admin/invitations")


def _register_frontend(app):
    def _no_cache(resp):
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp

    for route_path, page_file in PAGE_ROUTES.items():
        def _make_page_view(filename):
            return lambda: send_from_directory(PAGES_FOLDER, filename)

        app.add_url_rule(
            f"/{route_path}",
            endpoint=f"page_{route_path or 'index'}",
            view_func=_make_page_view(page_file),
        )

    @app.route("/config.js")
    def serve_config():
        js = f"""
            const ACCESS_CODE = '{os.getenv("APP_ACCESS_CODE", "")}';
            const token = '{os.getenv("ADMIN_TOKEN", "")}';
        """
        return Response(js.strip(), mimetype="application/javascript")

    @app.route("/css/<path:filename>")
    def serve_css(filename):
        return _no_cache(send_from_directory(os.path.join(FRONTEND_FOLDER, "css"), filename))

    @app.route("/js/<path:filename>")
    def serve_js(filename):
        return _no_cache(send_from_directory(os.path.join(FRONTEND_FOLDER, "js"), filename))

    @app.route("/assets/<path:filename>")
    def serve_assets(filename):
        return send_from_directory(os.path.join(FRONTEND_FOLDER, "assets"), filename)

    @app.route("/health")
    def health():
        return "OK", 200

    @app.errorhandler(404)
    def not_found(e):
        return send_from_directory(PAGES_FOLDER, "index.html")


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
