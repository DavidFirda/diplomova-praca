import re
import time
import hashlib
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, session, current_app

from models import db, Student
from services.mail_utils import send_email

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LOGIN_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")
RESET_TOKEN_TTL_MINUTES = 30

# --- Veľmi jednoduchý in-memory rate limiter ---
# Chráni pred hrubou silou pri /login a spamovaním /forgot-password.
# Poznámka: funguje len v rámci jedného procesu/kontajnera. Pri škálovaní
# na viac backend instancií (produkcia) je potrebné nahradiť napr.
# Flask-Limiter + Redis, ktoré zdieľajú stav medzi instanciami.
_attempts = defaultdict(list)


def _rate_limited(key: str, max_attempts: int, window_seconds: int) -> bool:
    now = time.time()
    window_start = now - window_seconds
    _attempts[key] = [t for t in _attempts[key] if t > window_start]
    if len(_attempts[key]) >= max_attempts:
        return True
    _attempts[key].append(now)
    return False


def _client_ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _validate_password_strength(password: str) -> str | None:
    if not password or len(password) < 8:
        return "Heslo musí mať aspoň 8 znakov."
    if password.lower() in ("password", "heslo12345", "12345678"):
        return "Toto heslo je príliš jednoduché."
    return None


def _student_public(student: Student) -> dict:
    return {
        "id": student.id,
        "name": student.name,
        "surname": student.surname,
        "login": student.login,
        "email": student.email,
    }


### Registrácia ###
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    surname = (data.get("surname") or "").strip()
    login = (data.get("login") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not surname or not login or not email or not password:
        return jsonify({"error": "Vyplň prosím všetky polia."}), 400

    if not LOGIN_RE.match(login):
        return jsonify({"error": "Login smie obsahovať len písmená, číslice, '.', '_', '-' (3-50 znakov)."}), 400

    if not EMAIL_RE.match(email):
        return jsonify({"error": "Neplatný formát emailu."}), 400

    pw_error = _validate_password_strength(password)
    if pw_error:
        return jsonify({"error": pw_error}), 400

    if Student.query.filter_by(login=login).first():
        return jsonify({"error": "Tento login je už obsadený."}), 409

    if Student.query.filter_by(email=email).first():
        return jsonify({"error": "Tento email je už zaregistrovaný."}), 409

    student = Student(name=name, surname=surname, login=login, email=email)
    student.set_password(password)
    db.session.add(student)
    db.session.commit()

    session.clear()
    session["student_id"] = student.id
    session.permanent = True

    return jsonify({"message": "Registrácia úspešná!", "student": _student_public(student)}), 201


### Prihlásenie ###
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("login") or data.get("email") or "").strip()
    password = data.get("password") or ""

    if not identifier or not password:
        return jsonify({"error": "Zadaj login/email a heslo."}), 400

    limiter_key = f"login:{_client_ip()}:{identifier.lower()}"
    if _rate_limited(limiter_key, max_attempts=10, window_seconds=300):
        return jsonify({"error": "Príliš veľa pokusov o prihlásenie. Skús to znova o pár minút."}), 429

    student = Student.query.filter(
        (Student.login == identifier) | (Student.email == identifier.lower())
    ).first()

    # Zámerne rovnaká chybová hláška pre "neexistuje" aj "zlé heslo" -
    # nechceme útočníkovi prezradiť, ktoré loginy/emaily v systéme existujú.
    if not student or not student.check_password(password):
        return jsonify({"error": "Nesprávny login/email alebo heslo."}), 401

    session.clear()
    session["student_id"] = student.id
    session.permanent = True

    return jsonify({"message": "Prihlásenie úspešné.", "student": _student_public(student)}), 200


### Odhlásenie ###
@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Odhlásené."}), 200


### Info o aktuálne prihlásenom študentovi (podľa session cookie) ###
@auth_bp.route("/me", methods=["GET"])
def me():
    student_id = session.get("student_id")
    if not student_id:
        return jsonify({"error": "Nie si prihlásený."}), 401
    student = Student.query.get(student_id)
    if not student:
        session.clear()
        return jsonify({"error": "Nie si prihlásený."}), 401
    return jsonify({"student": _student_public(student)}), 200


### Úprava profilu (meno/priezvisko/email/login) - prázdne pole = nemení sa ###
@auth_bp.route("/profile", methods=["PATCH", "PUT"])
def update_profile():
    student_id = session.get("student_id")
    if not student_id:
        return jsonify({"error": "Nie si prihlásený."}), 401
    student = Student.query.get(student_id)
    if not student:
        session.clear()
        return jsonify({"error": "Nie si prihlásený."}), 401

    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    surname = (data.get("surname") or "").strip()
    email = (data.get("email") or "").strip().lower()
    login = (data.get("login") or "").strip()

    # Meno/priezvisko - meníme len ak je vyplnené
    if name:
        student.name = name
    if surname:
        student.surname = surname

    # Email - validácia + kontrola, či ho nemá niekto iný
    if email and email != student.email:
        if not EMAIL_RE.match(email):
            return jsonify({"error": "Neplatný formát emailu."}), 400
        existing = Student.query.filter_by(email=email).first()
        if existing and existing.id != student.id:
            return jsonify({"error": "Tento email už používa iný účet."}), 409
        student.email = email

    # Login - validácia + kontrola unikátnosti
    if login and login != student.login:
        if not LOGIN_RE.match(login):
            return jsonify({"error": "Login smie obsahovať len písmená, číslice, '.', '_', '-' (3-50 znakov)."}), 400
        existing = Student.query.filter_by(login=login).first()
        if existing and existing.id != student.id:
            return jsonify({"error": "Tento login už používa iný účet."}), 409
        student.login = login

    db.session.commit()
    return jsonify({"message": "Profil bol aktualizovaný.", "student": _student_public(student)}), 200


### Prehľad pre dashboard prihláseného študenta ###
@auth_bp.route("/dashboard", methods=["GET"])
def dashboard():
    from models import StudentAnswer, TestSummary, StudentFeedback

    student_id = session.get("student_id")
    if not student_id:
        return jsonify({"error": "Nie si prihlásený."}), 401
    student = Student.query.get(student_id)
    if not student:
        session.clear()
        return jsonify({"error": "Nie si prihlásený."}), 401

    # Predtest: považujeme za dokončený, ak existuje aspoň jedna odpoveď typu "predtest"
    pretest_answers = StudentAnswer.query.filter_by(
        student_id=student_id, test_type="predtest"
    ).count()
    pretest_done = pretest_answers > 0

    # Hlavné testy: zoskupené podľa test_session (každá session = jeden absolvovaný test)
    main_answers = StudentAnswer.query.filter_by(
        student_id=student_id, test_type="main"
    ).all()
    main_sessions = sorted({a.test_session for a in main_answers if a.test_session})
    main_tests_count = len(main_sessions)

    # Celková štatistika (všetky odpovede)
    all_answers = StudentAnswer.query.filter_by(student_id=student_id).all()
    total = len(all_answers)
    correct = sum(1 for a in all_answers if a.is_correct)
    accuracy = round(correct / total * 100, 1) if total > 0 else 0.0

    # Dotazník spätnej väzby
    feedback_done = StudentFeedback.query.filter_by(student_id=student_id).count() > 0

    return jsonify({
        "student": _student_public(student),
        "pretest": {
            "done": pretest_done,
            "answers": pretest_answers,
        },
        "main_tests": {
            "count": main_tests_count,
            "sessions": main_sessions,
        },
        "stats": {
            "total_answers": total,
            "correct_answers": correct,
            "accuracy": accuracy,
        },
        "feedback_done": feedback_done,
    }), 200


### Štatistiky - výsledky predtestu podľa kategórií ###
@auth_bp.route("/stats", methods=["GET"])
def stats():
    student_id = session.get("student_id")
    if not student_id:
        return jsonify({"error": "Nie si prihlásený."}), 401
    student = Student.query.get(student_id)
    if not student:
        session.clear()
        return jsonify({"error": "Nie si prihlásený."}), 401

    from models import StudentAnswer

    def by_category(test_type):
        answers = StudentAnswer.query.filter_by(
            student_id=student_id, test_type=test_type
        ).all()
        cats = {}
        for a in answers:
            cat = a.category or "Ostatné"
            if cat not in cats:
                cats[cat] = {"total": 0, "correct": 0}
            cats[cat]["total"] += 1
            if a.is_correct:
                cats[cat]["correct"] += 1
        result = []
        for cat, v in sorted(cats.items()):
            acc = round(v["correct"] / v["total"] * 100, 1) if v["total"] > 0 else 0.0
            result.append({
                "category": cat,
                "total": v["total"],
                "correct": v["correct"],
                "accuracy": acc,
            })
        return result

    pretest_cats = by_category("predtest")
    main_cats = by_category("main")

    # Celkové čísla predtestu
    pretest_total = sum(c["total"] for c in pretest_cats)
    pretest_correct = sum(c["correct"] for c in pretest_cats)
    pretest_acc = round(pretest_correct / pretest_total * 100, 1) if pretest_total > 0 else 0.0

    return jsonify({
        "pretest": {
            "done": pretest_total > 0,
            "total": pretest_total,
            "correct": pretest_correct,
            "accuracy": pretest_acc,
            "categories": pretest_cats,
        },
        "main": {
            "categories": main_cats,
        },
    }), 200
@auth_bp.route("/change-password", methods=["POST"])
def change_password():
    student_id = session.get("student_id")
    if not student_id:
        return jsonify({"error": "Nie si prihlásený."}), 401

    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""

    student = Student.query.get(student_id)
    if not student or not student.check_password(current_password):
        return jsonify({"error": "Aktuálne heslo nie je správne."}), 401

    pw_error = _validate_password_strength(new_password)
    if pw_error:
        return jsonify({"error": pw_error}), 400

    student.set_password(new_password)
    student.reset_token_hash = None
    student.reset_token_expires_at = None
    db.session.commit()

    return jsonify({"message": "Heslo bolo zmenené."}), 200


### Žiadosť o reset hesla (zabudnuté heslo) ###
@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email or not EMAIL_RE.match(email):
        return jsonify({"error": "Zadaj platný email."}), 400

    limiter_key = f"forgot:{_client_ip()}:{email}"
    if _rate_limited(limiter_key, max_attempts=5, window_seconds=900):
        return jsonify({"error": "Príliš veľa žiadostí. Skús to znova neskôr."}), 429

    student = Student.query.filter_by(email=email).first()

    # Vždy rovnaká odpoveď bez ohľadu na to, či email existuje -
    # zabraňuje "user enumeration" (zisťovaniu, kto je v systéme zaregistrovaný).
    generic_response = jsonify({
        "message": "Ak je tento email zaregistrovaný, poslali sme naň link na reset hesla."
    })

    if not student:
        return generic_response, 200

    raw_token = secrets.token_urlsafe(48)
    student.reset_token_hash = _hash_token(raw_token)
    student.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)
    db.session.commit()

    frontend_base_url = current_app.config.get("FRONTEND_BASE_URL", "http://localhost:5000")
    reset_link = f"{frontend_base_url}/reset-password?uid={student.id}&token={raw_token}"

    text_body = (
        f"Ahoj {student.name},\n\n"
        f"Niekto (dúfajme že ty) požiadal o reset hesla k tvojmu účtu.\n"
        f"Klikni na nasledujúci link do {RESET_TOKEN_TTL_MINUTES} minút, aby si nastavil nové heslo:\n\n"
        f"{reset_link}\n\n"
        f"Ak si o reset nežiadal, tento email jednoducho ignoruj - tvoje heslo ostáva nezmenené.\n"
    )

    html_body = f"""\
<!DOCTYPE html>
<html lang="sk">
<body style="margin:0; padding:0; background:#f4f6f8; font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f6f8; padding:24px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="480" cellspacing="0" cellpadding="0"
               style="background:#ffffff; border-radius:10px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.06);">
          <tr>
            <td style="background:#1c3f60; padding:20px 28px; color:#ffffff; font-size:20px; font-weight:bold; letter-spacing:0.5px;">
              AdaptPy
            </td>
          </tr>
          <tr>
            <td style="padding:28px;">
              <p style="margin:0 0 14px; font-size:15px; color:#222;">Ahoj {student.name},</p>
              <p style="margin:0 0 14px; font-size:15px; color:#222;">
                Niekto (dúfajme že ty) požiadal o reset hesla k tvojmu účtu.
                Klikni na tlačidlo nižšie a nastav si nové heslo. Odkaz je platný
                <strong>{RESET_TOKEN_TTL_MINUTES} minút</strong>.
              </p>
              <p style="margin:24px 0; text-align:center;">
                <a href="{reset_link}"
                   style="background:#1c3f60; color:#ffffff; text-decoration:none;
                          padding:12px 28px; border-radius:6px; font-size:15px; display:inline-block;">
                  Nastaviť nové heslo
                </a>
              </p>
              <p style="margin:0 0 8px; font-size:13px; color:#666;">
                Ak tlačidlo nefunguje, skopíruj do prehliadača tento odkaz:
              </p>
              <p style="margin:0 0 18px; font-size:13px; word-break:break-all;">
                <a href="{reset_link}" style="color:#1c3f60;">{reset_link}</a>
              </p>
              <p style="margin:0; font-size:13px; color:#666;">
                Ak si o reset nežiadal, tento email jednoducho ignoruj -
                tvoje heslo ostáva nezmenené.
              </p>
            </td>
          </tr>
          <tr>
            <td style="background:#f0f2f4; padding:14px 28px; font-size:12px; color:#999; text-align:center;">
              AdaptPy &middot; adaptívne precvičovanie programovania v Pythone
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    send_email(
        to_email=student.email,
        subject="Reset hesla - AdaptPy",
        text_body=text_body,
        html_body=html_body,
    )

    return generic_response, 200


### Reset hesla cez token z emailu ###
@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True) or {}
    uid = data.get("uid")
    raw_token = data.get("token") or ""
    new_password = data.get("new_password") or ""

    if not uid or not raw_token:
        return jsonify({"error": "Neplatný alebo neúplný odkaz na reset hesla."}), 400

    pw_error = _validate_password_strength(new_password)
    if pw_error:
        return jsonify({"error": pw_error}), 400

    student = Student.query.get(uid)
    if not student or not student.reset_token_hash or not student.reset_token_expires_at:
        return jsonify({"error": "Odkaz na reset hesla je neplatný alebo už bol použitý."}), 400

    expires_at = student.reset_token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires_at:
        return jsonify({"error": "Platnosť odkazu vypršala. Vyžiadaj si prosím nový."}), 400

    # secrets.compare_digest chráni pred "timing attack" pri porovnávaní tokenu
    if not secrets.compare_digest(student.reset_token_hash, _hash_token(raw_token)):
        return jsonify({"error": "Odkaz na reset hesla je neplatný alebo už bol použitý."}), 400

    student.set_password(new_password)
    # Token je jednorazový - po použití ho zneplatníme
    student.reset_token_hash = None
    student.reset_token_expires_at = None
    db.session.commit()

    return jsonify({"message": "Heslo bolo úspešne zmenené. Môžeš sa prihlásiť."}), 200
