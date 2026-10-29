# ============================================================
# Admin API - ÚLOHY používateľov (prefix /api/admin/ulohy).
# Admin vidí úlohy študenta, každý jeho pokus (aj nesprávny) s poradovým číslom
# a log interakcií; môže upraviť kód/správnosť pokusu a úlohu zmazať - rovnako
# ako pri testoch. Každý zásah sa zapíše do logu ako "admin_edit".
#
# Úprava správnosti NEMENÍ POMDP: jeho stav sa učí priebežne z odpovedí študenta.
# ============================================================
import json

from flask import Blueprint, jsonify, request
from flask_login import current_user

from extensions import admin_required
from models import db, Question, Student
from models_ulohy import TaskAssignment, TaskAttempt, TaskEvent
from services import integrity as integrity_check
from services.task_feedback import feedback_message
from services.task_log import log_event

admin_ulohy_bp = Blueprint("admin_ulohy", __name__)


def _iso(dt):
    return dt.isoformat() if dt else None


def _loads(text):
    try:
        return json.loads(text) if text else None
    except ValueError:
        return None


def _attempt_dict(t):
    feedback = _loads(t.feedback_json)
    if feedback:
        feedback = {**feedback, "message": feedback_message(feedback.get("kind"), feedback.get("params"), "sk")}
    return {
        "id": t.id, "attempt_no": t.attempt_no, "code": t.code, "is_correct": t.is_correct,
        "student_output": t.student_output, "error": t.error, "feedback": feedback,
        "integrity": integrity_check.admin_view(t.integrity_json, t.integrity_flag, t.flag_dismissed),
        "created_at": _iso(t.created_at),
    }


def _event_dict(e):
    return {"id": e.id, "type": e.event_type, "payload": _loads(e.payload_json) or {},
            "created_at": _iso(e.created_at)}


def _assignment_dict(a, question, attempts, events):
    return {
        "id": a.id, "question_id": a.question_id, "category": a.category,
        "instruction": (question.instruction_sk or question.instruction) if question else "",
        "input_data": question.input_data if question else "",
        "solution_code": question.output if question else "",
        "status": a.status, "is_correct": a.is_correct,
        "attempts_used": a.attempts_used, "wrong_attempts": a.wrong_attempts,
        "solved_on_attempt": a.solved_on_attempt, "hints_used": a.hints_used,
        "agent_opened": a.agent_opened, "solution_shown": a.solution_shown,
        "reward": a.reward, "pomdp_applied": a.pomdp_applied, "strategy": a.strategy,
        "assigned_at": _iso(a.assigned_at), "finished_at": _iso(a.finished_at),
        "attempts": [_attempt_dict(t) for t in attempts],
        "active_flags": sum(1 for t in attempts if t.integrity_flag and not t.flag_dismissed),
        "events": [_event_dict(e) for e in events],
    }


def summary_for(assignments):
    """Súhrn úloh: koľko vyriešil, na koľký pokus, aký priemer."""
    done = [a for a in assignments if a.status in ("solved", "failed")]
    solved = [a for a in done if a.status == "solved"]
    with_attempt = [a for a in solved if a.solved_on_attempt]
    return {
        "total": len(done),
        "open": sum(1 for a in assignments if a.status == "open"),
        "solved": len(solved),
        "failed": sum(1 for a in done if a.status == "failed"),
        "solved_first_try": sum(1 for a in solved if a.solved_on_attempt == 1),
        "avg_attempts_to_solve": round(sum(a.solved_on_attempt for a in with_attempt) / len(with_attempt), 2) if with_attempt else None,
        "total_attempts": sum(a.attempts_used for a in assignments),
        "total_reward": round(sum(a.reward or 0 for a in assignments), 2),
    }


def flag_count(student_id):
    """Počet aktívnych (nezrušených) red flagov v úlohách študenta."""
    return TaskAttempt.query.filter_by(
        student_id=student_id, integrity_flag=True, flag_dismissed=False).count()


@admin_ulohy_bp.route("/user/<int:user_id>", methods=["GET"])
@admin_required
def user_ulohy(user_id):
    student = db.session.get(Student, user_id)
    if not student:
        return jsonify({"error": "Používateľ neexistuje."}), 404

    assignments = (TaskAssignment.query.filter_by(student_id=user_id)
                   .order_by(TaskAssignment.id).all())
    attempts, events = {}, {}
    for t in TaskAttempt.query.filter_by(student_id=user_id).order_by(TaskAttempt.attempt_no):
        attempts.setdefault(t.assignment_id, []).append(t)
    for e in TaskEvent.query.filter_by(student_id=user_id).order_by(TaskEvent.id):
        events.setdefault(e.assignment_id, []).append(e)
    questions = {q.id: q for q in Question.query.filter(
        Question.id.in_({a.question_id for a in assignments})).all()} if assignments else {}

    return jsonify({
        "student": {"id": student.id, "name": student.name, "surname": student.surname,
                    "login": student.login, "email": student.email},
        "summary": summary_for(assignments),
        "assignments": [
            _assignment_dict(a, questions.get(a.question_id), attempts.get(a.id, []), events.get(a.id, []))
            for a in assignments
        ],
    })


# ---------- Úprava jedného pokusu (kód, správnosť) ----------
@admin_ulohy_bp.route("/attempts/<int:attempt_id>", methods=["PATCH"])
@admin_required
def update_attempt(attempt_id):
    t = db.session.get(TaskAttempt, attempt_id)
    if not t:
        return jsonify({"error": "Pokus neexistuje."}), 404
    data = request.get_json(silent=True) or {}
    before = {"code": t.code, "is_correct": t.is_correct}

    # zrušenie / obnovenie red flagu (kontrola originality) - samostatný zásah
    if "flag_dismissed" in data:
        if not isinstance(data["flag_dismissed"], bool):
            return jsonify({"error": "Pole 'flag_dismissed' musí byť true/false."}), 400
        if not t.integrity_flag:
            return jsonify({"error": "Pokus nemá red flag."}), 400
        t.flag_dismissed = data["flag_dismissed"]
        t.integrity_json = integrity_check.set_dismissed(t.integrity_json, t.flag_dismissed, current_user.id)
        log_event(t.student_id, "admin_edit", question_id=t.question_id, payload={
            "admin_id": current_user.id, "target": "integrity_flag", "attempt_id": t.id,
            "assignment_id": t.assignment_id, "attempt_no": t.attempt_no,
            "flag_dismissed": t.flag_dismissed,
        })
        if "code" not in data and "is_correct" not in data:
            db.session.commit()
            return jsonify({"message": "Red flag aktualizovaný.", "flag_dismissed": t.flag_dismissed})

    if "code" in data:
        t.code = data["code"]
    if "is_correct" in data:
        t.is_correct = bool(data["is_correct"])
    log_event(t.student_id, "admin_edit", question_id=t.question_id, payload={
        "admin_id": current_user.id, "target": "attempt", "attempt_id": t.id,
        "assignment_id": t.assignment_id, "attempt_no": t.attempt_no,
        "before_is_correct": before["is_correct"], "after_is_correct": t.is_correct,
        "code_changed": before["code"] != t.code,
    })
    db.session.commit()
    return jsonify({"message": "Pokus aktualizovaný."})


# ---------- Úprava výsledku úlohy ----------
@admin_ulohy_bp.route("/assignments/<int:assignment_id>", methods=["PATCH"])
@admin_required
def update_assignment(assignment_id):
    a = db.session.get(TaskAssignment, assignment_id)
    if not a:
        return jsonify({"error": "Úloha neexistuje."}), 404
    data = request.get_json(silent=True) or {}
    if "is_correct" in data:
        if a.status not in ("solved", "failed"):
            return jsonify({"error": "Výsledok sa dá upraviť len pri uzavretej úlohe."}), 400
        before = a.status
        a.is_correct = bool(data["is_correct"])
        a.status = "solved" if a.is_correct else "failed"
        if a.is_correct:
            # na ktorý pokus bola vyriešená: prvý správny pokus, inak posledný
            attempts = TaskAttempt.query.filter_by(assignment_id=a.id).order_by(TaskAttempt.attempt_no).all()
            first_ok = next((t.attempt_no for t in attempts if t.is_correct), None)
            a.solved_on_attempt = first_ok or (attempts[-1].attempt_no if attempts else None)
        else:
            a.solved_on_attempt = None
        log_event(a.student_id, "admin_edit", a, payload={
            "admin_id": current_user.id, "target": "assignment",
            "before_status": before, "after_status": a.status,
        })
    db.session.commit()
    return jsonify({"message": "Úloha aktualizovaná.", "status": a.status, "is_correct": a.is_correct})


# ---------- Zmazanie ----------
def _delete_assignments(assignment_ids):
    if assignment_ids:
        TaskAttempt.query.filter(TaskAttempt.assignment_id.in_(assignment_ids)).delete(synchronize_session=False)
        TaskAssignment.query.filter(TaskAssignment.id.in_(assignment_ids)).delete(synchronize_session=False)


@admin_ulohy_bp.route("/assignments/<int:assignment_id>", methods=["DELETE"])
@admin_required
def delete_assignment(assignment_id):
    a = db.session.get(TaskAssignment, assignment_id)
    if not a:
        return jsonify({"error": "Úloha neexistuje."}), 404
    log_event(a.student_id, "admin_delete", a, payload={
        "admin_id": current_user.id, "target": "assignment", "status": a.status,
        "attempts_used": a.attempts_used,
    })
    _delete_assignments([a.id])     # log udalostí ostáva (pozri models_ulohy.TaskEvent)
    db.session.commit()
    return jsonify({"message": "Úloha vymazaná."})


@admin_ulohy_bp.route("/user/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user_ulohy(user_id):
    ids = [r[0] for r in db.session.query(TaskAssignment.id).filter_by(student_id=user_id)]
    log_event(user_id, "admin_delete", payload={
        "admin_id": current_user.id, "target": "all_assignments", "count": len(ids),
    })
    _delete_assignments(ids)
    db.session.commit()
    return jsonify({"message": "Úlohy používateľa vymazané."})
