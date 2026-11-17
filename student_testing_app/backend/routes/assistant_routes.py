# ============================================================
# AdaptPy - AI ASISTENT (študentská časť).  Prefix: /api/assistant
#
#   POST /stream    otázka / nápoveda -> odpoveď ako Server-Sent Events
#   GET  /history   história konverzácie (obnoví sa po návrate na stránku)
#   POST /insert    študent potvrdil vloženie kódu z odpovede do bunky/editora (log)
#   GET  /status    je asistent zapnutý?
#
# Identita študenta je VŽDY z current_user. Logika je v services/ai/service.py.
# ============================================================
from flask import Blueprint, Response, jsonify, request, stream_with_context
from flask_login import current_user, login_required

from services.ai import config as ai_config
from services.ai import service
from services.task_text import normalize_lang

assistant_bp = Blueprint("assistant", __name__)


def _json():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _int_arg(name):
    try:
        return int(request.args.get(name))
    except (TypeError, ValueError):
        return None


@assistant_bp.route("/status", methods=["GET"])
@login_required
def status():
    cfg = ai_config.load()
    return jsonify({"enabled": cfg.enabled})


@assistant_bp.route("/stream", methods=["POST"])
@login_required
def stream():
    student = current_user._get_current_object()
    try:
        prepared = service.prepare(student, _json())
    except service.RequestError as e:
        return jsonify({"error": str(e), "error_key": e.key, **e.extra}), e.status

    resp = Response(stream_with_context(service.stream(prepared)), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache, no-transform"
    resp.headers["X-Accel-Buffering"] = "no"      # nginx nesmie odpoveď bufferovať
    return resp


@assistant_bp.route("/history", methods=["GET"])
@login_required
def history():
    mode = request.args.get("mode")
    if mode not in service.MODES:
        return jsonify({"error": "Neznámy režim."}), 400
    exercise_id, assignment_id = _int_arg("exercise_id"), _int_arg("assignment_id")
    if (mode == "exercise" and exercise_id is None) or (mode == "task" and assignment_id is None):
        return jsonify({"error": "Chýba ID."}), 400
    if mode == "task":
        from models import db
        from models_ulohy import TaskAssignment
        a = db.session.get(TaskAssignment, assignment_id)
        if a is None or a.student_id != current_user.id:
            return jsonify({"error": "Úloha neexistuje."}), 404
    messages = service.history(current_user.id, mode, exercise_id, assignment_id,
                               lang=normalize_lang(request.args.get("lang")))
    return jsonify({"messages": messages})


@assistant_bp.route("/insert", methods=["POST"])
@login_required
def insert():
    try:
        return jsonify(service.log_insert(current_user._get_current_object(), _json()))
    except service.RequestError as e:
        return jsonify({"error": str(e)}), e.status
