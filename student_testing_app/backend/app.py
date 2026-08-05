import os
from flask import Flask, Response, send_from_directory
from flask_cors import CORS
import sys
from api_routes import api_bp
from admin_routes import  admin_bp
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

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback-key")
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['ADMIN_TOKEN'] = os.getenv("ADMIN_TOKEN")

CORS(app)
with app.app_context():
    db.init_app(app)
    db.create_all()

# ===== Registrácia API Blueprintu =====
app.register_blueprint(api_bp, url_prefix="/api")
app.register_blueprint(admin_bp, url_prefix="/admin")

# ===== Frontend Routy =====

@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_FOLDER, "index.html")

@app.route("/config.js")
def serve_config():
    access_code = os.getenv("APP_ACCESS_CODE", "")
    admin_token = os.getenv("ADMIN_TOKEN", "")
    js = f"""
        const ACCESS_CODE = '{access_code}';
        const token = '{admin_token}';
    """
    return Response(js.strip(), mimetype="application/javascript")

@app.route("/login")
def serve_login():
    return send_from_directory(FRONTEND_FOLDER, "login.html")

@app.route("/register")
def serve_register():
    return send_from_directory(FRONTEND_FOLDER, "register.html")

@app.route("/<path:filename>")
def serve_static_files(filename):
    return send_from_directory(FRONTEND_FOLDER, filename)

@app.route("/health")
def health():
    return "OK", 200

@app.errorhandler(404)
def not_found(e):
    return send_from_directory(FRONTEND_FOLDER, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)