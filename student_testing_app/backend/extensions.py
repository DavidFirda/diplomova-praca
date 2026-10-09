# ============================================================
# AdaptPy - rozšírenia Flasku na jednom mieste.
#
#  - Flask-Migrate: verzionované migrácie DB (backend/migrations)
#  - Flask-Login:   prihlásený používateľ (current_user), 401 pre neprihlásených
# ============================================================
from functools import wraps

from flask import jsonify
from flask_login import LoginManager, login_required, current_user
from flask_migrate import Migrate

from models import db, Student

migrate = Migrate()
login_manager = LoginManager()
# "basic": pri zmene IP/prehliadača sa session len označí ako nečerstvá, neodhlási
# sa (mobilní používatelia menia IP aj počas testu).
login_manager.session_protection = "basic"


@login_manager.user_loader
def load_user(user_id):
    """Volá sa raz za request: z ID v session vyrobí objekt Student (alebo None)."""
    try:
        return db.session.get(Student, int(user_id))
    except (TypeError, ValueError):
        return None


@login_manager.unauthorized_handler
def unauthorized():
    # API vždy vracia JSON (nie presmerovanie na login stránku)
    return jsonify({"error": "Nie si prihlásený.", "error_key": "auth.notLoggedIn"}), 401


def admin_required(fn):
    """Povolí prístup len prihlásenému adminovi (401 = nie je prihlásený, 403 = nie je admin)."""
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            return jsonify({"error": "Prístup len pre administrátora."}), 403
        return fn(*args, **kwargs)
    return wrapper
