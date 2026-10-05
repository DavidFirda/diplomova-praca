# ============================================================
# AdaptPy - POZVÁNKY
#   Verejné (prefix /api/invites):
#       GET  /mode            -> {"mode": "invite" | "open"}
#       GET  /check?token=..  -> overenie pozvánky (predvyplnenie formulára)
#       POST /register        -> dokončenie registrácie cez pozvánku
#   Admin (prefix /api/admin/invitations):
#       GET    ""             -> zoznam pozvánok + štatistika
#       POST   ""             -> vytvorenie pozvánok (hromadne)
#       POST   /<id>/resend   -> nový odkaz (+ voliteľne e-mail)
#       DELETE /<id>          -> zrušenie pozvánky
# ============================================================
import os
import re
import secrets
from datetime import timedelta
from functools import wraps

from flask import Blueprint, request, jsonify, session

from models import db, Student
from models_invites import Invitation, utcnow
from routes.auth_routes import (
    EMAIL_RE, LOGIN_RE, _hash_token, _validate_password_strength,
    _student_public, _client_ip,
)
from services.mail_utils import send_email
from services.rate_limiter import rate_limited as _rate_limited, retry_after as _retry_after

invite_public_bp = Blueprint("invite_public", __name__)
invite_admin_bp = Blueprint("invite_admin", __name__)

DEFAULT_TTL_DAYS = 7
MAX_TTL_DAYS = 60
MAX_BULK = 300

_table_ready = False


def ensure_invite_table():
    """Vytvorí tabuľku invitations, ak ešte neexistuje (raz za proces)."""
    global _table_ready
    if _table_ready:
        return
    try:
        Invitation.__table__.create(bind=db.engine, checkfirst=True)
    except Exception:
        db.session.rollback()   # pri súbehu workerov môže tabuľku vytvoriť iný proces
    _table_ready = True


def registration_mode():
    """'invite' (predvolené) = registrácia len na pozvánku; 'open' = voľná registrácia."""
    return "open" if os.getenv("REGISTRATION_MODE", "invite").strip().lower() == "open" else "invite"


def _current_student():
    sid = session.get("student_id")
    return Student.query.get(sid) if sid else None


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        ensure_invite_table()
        student = _current_student()
        if not student:
            return jsonify({"error": "Nie si prihlásený."}), 401
        if (getattr(student, "role", "user") or "user") != "admin":
            return jsonify({"error": "Prístup len pre administrátora."}), 403
        return fn(*args, **kwargs)
    return wrapper


def _base_url():
    base = (os.getenv("APP_BASE_URL") or "").strip().rstrip("/")
    return base or request.host_url.rstrip("/")


def _link(raw_token):
    return f"{_base_url()}/register?invite={raw_token}"


def _serialize(inv):
    return {
        "id": inv.id, "email": inv.email,
        "name": inv.name or "", "surname": inv.surname or "", "group": inv.group_name or "",
        "status": inv.status,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "used_at": inv.used_at.isoformat() if inv.used_at else None,
        "last_sent_at": inv.last_sent_at.isoformat() if inv.last_sent_at else None,
        "send_count": inv.send_count or 0,
    }


def _new_token(inv, ttl_days):
    raw = secrets.token_urlsafe(32)
    inv.token_hash = _hash_token(raw)
    inv.expires_at = utcnow() + timedelta(days=ttl_days)
    return raw


def _send_invite_mail(inv, link):
    days = max(1, (inv.expires_at - utcnow()).days)
    greet = f"Ahoj {inv.name}," if inv.name else "Ahoj,"
    text = (
        f"{greet}\n\n"
        "administrátor ťa pozval do aplikácie AdaptPy. Registráciu dokončíš cez tento odkaz:\n"
        f"{link}\n\n"
        f"Odkaz je jednorazový a platí {days} dní.\n\n"
        "---\n"
        "You have been invited to AdaptPy. Complete your registration here:\n"
        f"{link}\n"
        f"The link is single-use and valid for {days} days.\n"
    )
    html = (
        f"<p>{greet}</p>"
        "<p>administrátor ťa pozval do aplikácie <strong>AdaptPy</strong>. Registráciu dokončíš cez tento odkaz:</p>"
        f'<p><a href="{link}">{link}</a></p>'
        f"<p>Odkaz je jednorazový a platí {days} dní.</p><hr>"
        "<p>You have been invited to <strong>AdaptPy</strong>. Complete your registration using the link above "
        f"(single-use, valid for {days} days).</p>"
    )
    send_email(inv.email, "Pozvánka do AdaptPy / AdaptPy invitation", text, html)
    inv.last_sent_at = utcnow()
    inv.send_count = (inv.send_count or 0) + 1


# ---------- parsovanie vstupu admina ----------
def parse_entries(raw):
    """
    Vstup: text (riadky/čiarky/bodkočiarky) alebo zoznam.
    Podporované riadky:
        jan@x.sk
        jan@x.sk, Ján, Novák
        a@x.sk; b@x.sk
    Vráti [{"email","name","surname"}], poradie zachované, duplicity preč.
    """
    if isinstance(raw, list):
        lines = [str(x) for x in raw]
    else:
        lines = str(raw or "").splitlines()
    out, seen = [], set()
    for line in lines:
        tokens = [t.strip() for t in re.split(r"[;,\t]+", line) if t.strip()]
        emails = [t for t in tokens if "@" in t]
        others = [t for t in tokens if "@" not in t]
        if not emails:
            # e-mail oddelený medzerou
            emails = [t for t in line.split() if "@" in t]
            others = []
        for i, em in enumerate(emails):
            em = em.strip().lower().strip("<>")
            if em in seen:
                continue
            seen.add(em)
            name = surname = ""
            if len(emails) == 1:
                name = others[0] if len(others) > 0 else ""
                surname = others[1] if len(others) > 1 else ""
            out.append({"email": em, "name": name[:100], "surname": surname[:100]})
    return out


# =====================================================================
#   ADMIN
# =====================================================================
@invite_admin_bp.route("", methods=["GET"])
@invite_admin_bp.route("/", methods=["GET"])
@admin_required
def list_invites():
    items = Invitation.query.order_by(Invitation.created_at.desc()).all()
    data = [_serialize(i) for i in items]
    stats = {
        "total": len(data),
        "pending": sum(1 for d in data if d["status"] == "pending"),
        "registered": sum(1 for d in data if d["status"] == "registered"),
        "expired": sum(1 for d in data if d["status"] == "expired"),
    }
    return jsonify({"invitations": data, "stats": stats, "mode": registration_mode()})


@invite_admin_bp.route("", methods=["POST"])
@invite_admin_bp.route("/", methods=["POST"])
@admin_required
def create_invites():
    body = request.get_json(silent=True) or {}
    entries = parse_entries(body.get("emails"))
    if not entries:
        return jsonify({"error": "Zadaj aspoň jeden e-mail."}), 400
    if len(entries) > MAX_BULK:
        return jsonify({"error": f"Naraz je možné pozvať najviac {MAX_BULK} ľudí."}), 400

    try:
        ttl = int(body.get("expires_days") or DEFAULT_TTL_DAYS)
    except (TypeError, ValueError):
        ttl = DEFAULT_TTL_DAYS
    ttl = max(1, min(ttl, MAX_TTL_DAYS))
    group = (body.get("group") or "").strip()[:100] or None
    do_mail = bool(body.get("send_email", True))
    admin = _current_student()

    results = []
    for e in entries:
        email = e["email"]
        if not EMAIL_RE.match(email):
            results.append({"email": email, "result": "invalid"})
            continue
        if Student.query.filter_by(email=email).first():
            results.append({"email": email, "result": "already_registered"})
            continue

        inv = Invitation.query.filter_by(email=email).first()
        action = "created"
        if inv:
            # Účet s týmto e-mailom už neexistuje (kontrola vyššie). Ak bol pozvaný používateľ
            # medzitým zmazaný, pozvánku možno použiť znova.
            if inv.used_at:
                inv.used_at = None
                inv.student_id = None
            action = "renewed"     # čakajúca, vypršaná alebo po zmazanom účte -> nový odkaz
        else:
            inv = Invitation(email=email, token_hash="", expires_at=utcnow(), created_by=admin.id)
            db.session.add(inv)

        if e["name"]:
            inv.name = e["name"]
        if e["surname"]:
            inv.surname = e["surname"]
        if group:
            inv.group_name = group
        raw = _new_token(inv, ttl)
        link = _link(raw)
        if do_mail:
            _send_invite_mail(inv, link)
        db.session.flush()
        results.append({"email": email, "result": action, "link": link, "id": inv.id, "mailed": do_mail})

    db.session.commit()
    return jsonify({"results": results}), 201


@invite_admin_bp.route("/<int:inv_id>/resend", methods=["POST"])
@admin_required
def resend_invite(inv_id):
    inv = Invitation.query.get(inv_id)
    if not inv:
        return jsonify({"error": "Pozvánka neexistuje."}), 404
    if inv.used_at:
        return jsonify({"error": "Používateľ sa už zaregistroval."}), 409
    body = request.get_json(silent=True) or {}
    try:
        ttl = int(body.get("expires_days") or DEFAULT_TTL_DAYS)
    except (TypeError, ValueError):
        ttl = DEFAULT_TTL_DAYS
    ttl = max(1, min(ttl, MAX_TTL_DAYS))
    raw = _new_token(inv, ttl)     # starý odkaz tým prestáva platiť
    link = _link(raw)
    mailed = bool(body.get("send_email", True))
    if mailed:
        _send_invite_mail(inv, link)
    db.session.commit()
    return jsonify({"invitation": _serialize(inv), "link": link, "mailed": mailed})


@invite_admin_bp.route("/<int:inv_id>", methods=["DELETE"])
@admin_required
def delete_invite(inv_id):
    inv = Invitation.query.get(inv_id)
    if not inv:
        return jsonify({"error": "Pozvánka neexistuje."}), 404
    db.session.delete(inv)       # už vytvorený účet zostáva
    db.session.commit()
    return jsonify({"ok": True})


# =====================================================================
#   VEREJNÉ
# =====================================================================
@invite_public_bp.route("/mode", methods=["GET"])
def get_mode():
    return jsonify({"mode": registration_mode()})


def _find_by_token(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    return Invitation.query.filter_by(token_hash=_hash_token(raw)).first()


def _reason(inv):
    if not inv:
        return "invalid"
    if inv.used_at:
        return "used"
    if inv.expires_at < utcnow():
        return "expired"
    return None


@invite_public_bp.route("/check", methods=["GET"])
def check_invite():
    ensure_invite_table()
    key = f"invcheck:{_client_ip()}"
    if _rate_limited(key, max_attempts=30, window_seconds=300):
        return jsonify({"valid": False, "reason": "rate"}), 429
    inv = _find_by_token(request.args.get("token"))
    reason = _reason(inv)
    if reason:
        return jsonify({"valid": False, "reason": reason}), 200
    return jsonify({"valid": True, "email": inv.email, "name": inv.name or "", "surname": inv.surname or ""})


@invite_public_bp.route("/register", methods=["POST"])
def register_with_invite():
    ensure_invite_table()
    data = request.get_json(silent=True) or {}

    key = f"invreg:{_client_ip()}"
    if _rate_limited(key, max_attempts=10, window_seconds=300):
        return jsonify({
            "error": "Príliš veľa pokusov. Skús to znova o pár minút.",
            "error_key": "auth.tooManyLogin",
            "retry_after": _retry_after(key, window_seconds=300),
        }), 429

    token = data.get("token") or ""
    name = (data.get("name") or "").strip()
    surname = (data.get("surname") or "").strip()
    login = (data.get("login") or "").strip()
    password = data.get("password") or ""

    inv = _find_by_token(token)
    reason = _reason(inv)
    if reason:
        msgs = {
            "invalid": ("Pozvánka je neplatná.", "invite.invalid"),
            "used": ("Táto pozvánka už bola použitá.", "invite.used"),
            "expired": ("Platnosť pozvánky vypršala. Požiadaj administrátora o novú.", "invite.expired"),
        }
        m, k = msgs[reason]
        return jsonify({"error": m, "error_key": k}), 400

    if not name or not surname or not login or not password:
        return jsonify({"error": "Vyplň prosím všetky polia.", "error_key": "auth.fillAllFields"}), 400
    if not LOGIN_RE.match(login):
        return jsonify({"error": "Login smie obsahovať len písmená, číslice, '.', '_', '-' (3-50 znakov).", "error_key": "auth.invalidLogin"}), 400
    pw_error = _validate_password_strength(password)
    if pw_error:
        return jsonify({"error": pw_error}), 400
    if Student.query.filter_by(login=login).first():
        return jsonify({"error": "Tento login je už obsadený.", "error_key": "auth.loginTaken"}), 409
    if Student.query.filter_by(email=inv.email).first():
        return jsonify({"error": "Tento email je už zaregistrovaný.", "error_key": "auth.emailTaken"}), 409

    # zámok riadku pozvánky -> dve súbežné registrácie s rovnakým odkazom neprejdú obe
    locked = Invitation.query.filter_by(id=inv.id).with_for_update().first()
    if locked.used_at:
        db.session.rollback()
        return jsonify({"error": "Táto pozvánka už bola použitá.", "error_key": "invite.used"}), 400

    student = Student(name=name, surname=surname, login=login, email=inv.email)   # e-mail je vždy z pozvánky
    student.set_password(password)
    db.session.add(student)
    db.session.flush()
    locked.used_at = utcnow()
    locked.student_id = student.id
    db.session.commit()

    session.clear()   # po registrácii sa neprihlasuje automaticky
    return jsonify({"message": "Registrácia úspešná!", "error_key": "auth.registerSuccess",
                    "student": _student_public(student)}), 201
