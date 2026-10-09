import re
import os
import time
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, session, current_app
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import case, func

from models import db, Student, StudentAnswer, FeedbackResponse
from services.settings import questionnaire_published
from services.mail_utils import send_email
from services.test_flow import pretest_state
from services.rate_limiter import rate_limited as _rate_limited, retry_after as _retry_after

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LOGIN_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")
RESET_TOKEN_TTL_MINUTES = 30

# --- Rate limiter ---
# Ochrana pred hrubou silou pri /login a spamom /forgot-password.
# Implementacia je v services/rate_limiter.py a pouziva Redis (ak je REDIS_URL
# nastaveny), takze limit plati napriec vsetkymi gunicorn workermi. Bez Redisu
# automaticky prepne na in-memory rezim (len jeden proces).


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
        "role": student.role or "user",
    }


### Registrácia ###
@auth_bp.route("/register", methods=["POST"])
def register():

    # Registrácia len na pozvánku 
    if os.getenv("REGISTRATION_MODE", "invite").strip().lower() != "open":
        return jsonify({
            "error": "Registrácia je možná len na pozvánku od administrátora.",
            "error_key": "auth.inviteOnly",
        }), 403

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    surname = (data.get("surname") or "").strip()
    login = (data.get("login") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not surname or not login or not email or not password:
        return jsonify({"error": "Vyplň prosím všetky polia.", "error_key": "auth.fillAllFields"}), 400

    if not LOGIN_RE.match(login):
        return jsonify({"error": "Login smie obsahovať len písmená, číslice, '.', '_', '-' (3-50 znakov).", "error_key": "auth.invalidLogin"}), 400

    if not EMAIL_RE.match(email):
        return jsonify({"error": "Neplatný formát emailu.", "error_key": "auth.invalidEmail"}), 400

    pw_error = _validate_password_strength(password)
    if pw_error:
        return jsonify({"error": pw_error}), 400

    if Student.query.filter_by(login=login).first():
        return jsonify({"error": "Tento login je už obsadený.", "error_key": "auth.loginTaken"}), 409

    if Student.query.filter_by(email=email).first():
        return jsonify({"error": "Tento email je už zaregistrovaný.", "error_key": "auth.emailTaken"}), 409

    student = Student(name=name, surname=surname, login=login, email=email)
    student.set_password(password)
    db.session.add(student)
    db.session.commit()

    # Po registrácii NEPRIHLASUJEME - používateľ sa musí prihlásiť sám.
    session.clear()
    return jsonify({"message": "Registrácia úspešná!", "error_key": "auth.registerSuccess", "student": _student_public(student)}), 201


### Prihlásenie ###
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("login") or data.get("email") or "").strip()
    password = data.get("password") or ""

    if not identifier or not password:
        return jsonify({"error": "Zadaj login/email a heslo.", "error_key": "auth.enterCredentials"}), 400

    limiter_key = f"login:{_client_ip()}:{identifier.lower()}"
    if _rate_limited(limiter_key, max_attempts=10, window_seconds=300):
        secs = _retry_after(limiter_key, window_seconds=300)
        return jsonify({
            "error": "Príliš veľa pokusov o prihlásenie. Skús to znova o pár minút.",
            "error_key": "auth.tooManyLogin",
            "retry_after": secs,
        }), 429

    student = Student.query.filter(
        (Student.login == identifier) | (Student.email == identifier.lower())
    ).first()

    # Zámerne rovnaká chybová hláška pre "neexistuje" aj "zlé heslo" -
    # nechceme útočníkovi prezradiť, ktoré loginy/emaily v systéme existujú.
    if not student or not student.check_password(password):
        return jsonify({"error": "Nesprávny login/email alebo heslo.", "error_key": "auth.wrongCredentials"}), 401

    session.clear()                       # nové prihlásenie = čistá session
    login_user(student, remember=False)   # cookie zanikne po zatvorení prehliadača

    return jsonify({"message": "Prihlásenie úspešné.", "error_key": "auth.loginSuccess", "student": _student_public(student)}), 200


### Odhlásenie ###
@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    session.clear()
    return jsonify({"message": "Odhlásené.", "error_key": "auth.loggedOut"}), 200


### Info o aktuálne prihlásenom študentovi (podľa session cookie) ###
@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify({"student": _student_public(current_user)}), 200


### Úprava profilu (meno/priezvisko/email/login) - prázdne pole = nemení sa ###
@auth_bp.route("/profile", methods=["PATCH", "PUT"])
@login_required
def update_profile():
    student = current_user._get_current_object()

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
            return jsonify({"error": "Neplatný formát emailu.", "error_key": "auth.invalidEmail"}), 400
        existing = Student.query.filter_by(email=email).first()
        if existing and existing.id != student.id:
            return jsonify({"error": "Tento email už používa iný účet.", "error_key": "auth.emailUsedByOther"}), 409
        student.email = email

    # Login - validácia + kontrola unikátnosti
    if login and login != student.login:
        if not LOGIN_RE.match(login):
            return jsonify({"error": "Login smie obsahovať len písmená, číslice, '.', '_', '-' (3-50 znakov).", "error_key": "auth.invalidLogin"}), 400
        existing = Student.query.filter_by(login=login).first()
        if existing and existing.id != student.id:
            return jsonify({"error": "Tento login už používa iný účet.", "error_key": "auth.loginUsedByOther"}), 409
        student.login = login

    db.session.commit()
    return jsonify({"message": "Profil bol aktualizovaný.", "error_key": "auth.profileUpdated", "student": _student_public(student)}), 200


### Prehľad pre dashboard prihláseného študenta ###
@auth_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    student = current_user._get_current_object()
    student_id = student.id

    # Predtest je dokončený, až keď sú zodpovedané VŠETKY jeho otázky
    # (rozpracovaný predtest pokračuje od nezodpovedanej otázky).
    pt_state = pretest_state(student_id)
    pretest_answers = pt_state["answered"]
    pretest_done = pt_state["done"]

    # Hlavné testy: zoskupené podľa test_session (každá session = jeden absolvovaný test)
    main_sessions = sorted(
        row[0] for row in db.session.query(StudentAnswer.test_session)
        .filter(StudentAnswer.student_id == student_id,
                StudentAnswer.test_type == "main",
                StudentAnswer.test_session.isnot(None))
        .distinct()
    )

    # Celková štatistika (všetky odpovede) - agregácia v DB, dashboard sa volá pri každej stránke
    total, correct = db.session.query(
        func.count(StudentAnswer.id),
        func.coalesce(func.sum(case((StudentAnswer.is_correct.is_(True), 1), else_=0)), 0),
    ).filter(StudentAnswer.student_id == student_id).one()
    accuracy = round(correct / total * 100, 1) if total > 0 else 0.0

    # Dotazník spätnej väzby (nový dynamický systém: FeedbackResponse)
    feedback_done = FeedbackResponse.query.filter_by(student_id=student_id).count() > 0

    return jsonify({
        "student": _student_public(student),
        "is_admin": student.is_admin,
        "pretest": {
            "done": pretest_done,
            "answers": pretest_answers,
            "total": pt_state["total"],
        },
        "main_tests": {
            "count": len(main_sessions),
            "sessions": main_sessions,
        },
        "stats": {
            "total_answers": total,
            "correct_answers": correct,
            "accuracy": accuracy,
        },
        "feedback_done": feedback_done,
        "questionnaire_published": questionnaire_published(),
    }), 200


### Štatistiky - výsledky predtestu podľa kategórií ###
@auth_bp.route("/stats", methods=["GET"])
@login_required
def stats():
    student_id = current_user.id

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
            "done": pretest_state(student_id)["done"],
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
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""

    student = current_user._get_current_object()
    if not student.check_password(current_password):
        return jsonify({"error": "Aktuálne heslo nie je správne.", "error_key": "auth.wrongCurrentPassword"}), 401

    pw_error = _validate_password_strength(new_password)
    if pw_error:
        return jsonify({"error": pw_error}), 400

    student.set_password(new_password)
    student.reset_token_hash = None
    student.reset_token_expires_at = None
    db.session.commit()

    return jsonify({"message": "Heslo bolo zmenené.", "error_key": "auth.passwordChanged"}), 200


### Žiadosť o reset hesla (zabudnuté heslo) ###
@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email or not EMAIL_RE.match(email):
        return jsonify({"error": "Zadaj platný email.", "error_key": "auth.enterValidEmail"}), 400

    limiter_key = f"forgot:{_client_ip()}:{email}"
    if _rate_limited(limiter_key, max_attempts=5, window_seconds=900):
        secs = _retry_after(limiter_key, window_seconds=900)
        return jsonify({
            "error": "Príliš veľa žiadostí. Skús to znova neskôr.",
            "error_key": "auth.tooManyForgot",
            "retry_after": secs,
        }), 429

    student = Student.query.filter_by(email=email).first()

    # Vždy rovnaká odpoveď bez ohľadu na to, či email existuje -
    # zabraňuje "user enumeration" (zisťovaniu, kto je v systéme zaregistrovaný).
    generic_response = jsonify({
        "message": "Ak je tento email zaregistrovaný, poslali sme naň link na reset hesla.",
        "message_key": "forgot.sent"
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
        return jsonify({"error": "Neplatný alebo neúplný odkaz na reset hesla.", "error_key": "auth.invalidResetLink"}), 400

    pw_error = _validate_password_strength(new_password)
    if pw_error:
        return jsonify({"error": pw_error}), 400

    student = Student.query.get(uid)
    if not student or not student.reset_token_hash or not student.reset_token_expires_at:
        return jsonify({"error": "Odkaz na reset hesla je neplatný alebo už bol použitý.", "error_key": "auth.resetLinkUsed"}), 400

    expires_at = student.reset_token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires_at:
        return jsonify({"error": "Platnosť odkazu vypršala. Vyžiadaj si prosím nový.", "error_key": "auth.resetLinkExpired"}), 400

    # secrets.compare_digest chráni pred "timing attack" pri porovnávaní tokenu
    if not secrets.compare_digest(student.reset_token_hash, _hash_token(raw_token)):
        return jsonify({"error": "Odkaz na reset hesla je neplatný alebo už bol použitý.", "error_key": "auth.resetLinkUsed"}), 400

    student.set_password(new_password)
    # Token je jednorazový - po použití ho zneplatníme
    student.reset_token_hash = None
    student.reset_token_expires_at = None
    db.session.commit()

    return jsonify({"message": "Heslo bolo úspešne zmenené. Môžeš sa prihlásiť.", "error_key": "auth.passwordResetDone"}), 200
