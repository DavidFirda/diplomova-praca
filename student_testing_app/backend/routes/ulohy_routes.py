# ============================================================
# AdaptPy - ÚLOHY (študentská časť).  Prefix: /api/ulohy
#
# Samoštúdium: POMDP priebežne vyberá úlohy z kategórií, ktoré študent ešte
# nezvláda. Pravidlá pokusov (agent po 2. chybe, riešenie po 5.) sú v
# services/task_flow.py. Identita študenta je VŽDY z current_user.
# ============================================================
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from models import db
from services import task_flow
from services.task_text import normalize_lang, tt
from services.test_flow import lock_student, pretest_state

ulohy_bp = Blueprint("ulohy", __name__)


def _pretest_required():
    """Odpoveď 403, ak študent ešte nedokončil predtest (z neho sa POMDP učí), inak None."""
    if pretest_state(current_user.id)["done"]:
        return None
    return jsonify({
        "error": "Najprv musíš dokončiť predtest.",
        "error_key": "test.pretestRequired",
    }), 403


def _json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _assignment_id(data):
    try:
        return int(data.get("assignment_id"))
    except (TypeError, ValueError):
        return None


@ulohy_bp.route("/summary", methods=["GET"])
@login_required
def summary():
    """Súhrn pre dashboard. Vždy 200 (aj bez predtestu: vtedy `pretest_done` je false a karta sa zamkne)."""
    if not pretest_state(current_user.id)["done"]:
        return jsonify({"pretest_done": False})
    return jsonify({"pretest_done": True, **task_flow.dashboard_summary(current_user.id)})


@ulohy_bp.route("/current", methods=["GET"])
@login_required
def current():
    """Rozpracovaná úloha (ak nejaká je) + súhrn. Nič nevytvára."""
    denied = _pretest_required()
    if denied:
        return denied
    lang = normalize_lang(request.args.get("lang"))
    assignment = task_flow.open_assignment(current_user.id)
    return jsonify({
        "assignment": task_flow.assignment_payload(assignment, lang) if assignment else None,
        "stats": task_flow.task_stats(current_user.id),
    })


@ulohy_bp.route("/next", methods=["POST"])
@login_required
def next_task():
    """Rozpracovaná úloha pokračuje, inak POMDP vyberie ďalšiu."""
    denied = _pretest_required()
    if denied:
        return denied
    student_id = current_user.id
    lang = normalize_lang(_json().get("lang"))

    lock_student(student_id)
    try:
        assignment, _ = task_flow.start_task(student_id)
        if assignment is None:
            db.session.rollback()
            return jsonify({"error": tt(lang, "no_tasks"), "error_key": "ul.noTasks"}), 404
        db.session.commit()
    except IntegrityError:
        # súbežná požiadavka už otvorila úlohu (unikátny index "jedna otvorená úloha")
        db.session.rollback()
        assignment = task_flow.open_assignment(student_id)

    return jsonify({
        "assignment": task_flow.assignment_payload(assignment, lang),
        "stats": task_flow.task_stats(student_id),
    })


@ulohy_bp.route("/submit", methods=["POST"])
@login_required
def submit():
    data = _json()
    assignment_id = _assignment_id(data)
    if assignment_id is None:
        return jsonify({"error": "Chýba ID úlohy."}), 400
    status, body = task_flow.submit_attempt(
        current_user.id, assignment_id, data.get("code") or "", normalize_lang(data.get("lang")),
        integrity=data.get("integrity"),
    )
    return jsonify(body), status


@ulohy_bp.route("/agent", methods=["POST"])
@login_required
def agent():
    data = _json()
    assignment_id = _assignment_id(data)
    if assignment_id is None:
        return jsonify({"error": "Chýba ID úlohy."}), 400
    status, body = task_flow.agent_chat(
        current_user.id, assignment_id,
        intent=data.get("intent"), message=data.get("message"),
        code=data.get("code") or "", lang=normalize_lang(data.get("lang")),
    )
    return jsonify(body), status
