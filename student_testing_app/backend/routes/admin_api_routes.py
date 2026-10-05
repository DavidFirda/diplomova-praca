# ============================================================
# Admin API - správa používateľov, testov a dotazníka.
# Autentifikácia cez SESSION + rola "admin" (nie token z URL).
# ============================================================
import json
from functools import wraps
from flask import Blueprint, request, jsonify, session

from models_exercises import ExerciseProgress
from models import (
    db, Student, StudentAnswer, TestSummary,
    FeedbackQuestion, FeedbackResponse, StudentFeedback,
)

admin_api_bp = Blueprint("admin_api", __name__)


def _current_student():
    sid = session.get("student_id")
    if not sid:
        return None
    return Student.query.get(sid)


def admin_required(fn):
    """Dekorátor: povolí prístup len prihlásenému adminovi."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        student = _current_student()
        if not student:
            return jsonify({"error": "Nie si prihlásený."}), 401
        if (getattr(student, "role", "user") or "user") != "admin":
            return jsonify({"error": "Prístup len pre administrátora."}), 403
        return fn(*args, **kwargs)
    return wrapper


# ---------- Kontrola, či je aktuálny používateľ admin ----------
@admin_api_bp.route("/me", methods=["GET"])
def admin_me():
    student = _current_student()
    is_admin = bool(student and (getattr(student, "role", "user") or "user") == "admin")
    return jsonify({"is_admin": is_admin})


# ============================================================
# SPRÁVA POUŽÍVATEĽOV
# ============================================================
@admin_api_bp.route("/users", methods=["GET"])
@admin_required
def list_users():
    students = Student.query.order_by(Student.id).all()
    result = []
    for s in students:
        pre = StudentAnswer.query.filter_by(student_id=s.id, test_type="predtest").count()
        main_sessions = {a.test_session for a in StudentAnswer.query.filter_by(student_id=s.id, test_type="main").all() if a.test_session}
        fb = FeedbackResponse.query.filter_by(student_id=s.id).count() + StudentFeedback.query.filter_by(student_id=s.id).count()
        result.append({
            "id": s.id,
            "name": s.name,
            "surname": s.surname,
            "login": s.login,
            "email": s.email,
            "role": getattr(s, "role", "user") or "user",
            "pretest_answers": pre,
            "main_tests": len(main_sessions),
            "feedback_done": fb > 0,
        })
    return jsonify({"users": result})


@admin_api_bp.route("/users/<int:user_id>/role", methods=["PATCH"])
@admin_required
def set_user_role(user_id):
    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "").strip().lower()
    if role not in ("user", "admin"):
        return jsonify({"error": "Neplatná rola."}), 400
    student = Student.query.get(user_id)
    if not student:
        return jsonify({"error": "Používateľ neexistuje."}), 404
    student.role = role
    db.session.commit()
    return jsonify({"message": "Rola aktualizovaná.", "role": role})


@admin_api_bp.route("/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    student = Student.query.get(user_id)
    if not student:
        return jsonify({"error": "Používateľ neexistuje."}), 404
    try:
        StudentAnswer.query.filter_by(student_id=user_id).delete()
        TestSummary.query.filter_by(student_id=user_id).delete()
        FeedbackResponse.query.filter_by(student_id=user_id).delete()
        StudentFeedback.query.filter_by(student_id=user_id).delete()
        ExerciseProgress.query.filter_by(student_id=user_id).delete()     
 
        try:
            from models_invites import Invitation
            Invitation.query.filter(
                (Invitation.student_id == user_id) | (Invitation.email == student.email)
            ).delete(synchronize_session=False)
        except Exception:
            pass
 
        db.session.delete(student)
        db.session.commit()
    except Exception as e:
        db.session.rollback()        
        return jsonify({"error": f"Používateľa sa nepodarilo vymazať: {e.__class__.__name__}"}), 500
    return jsonify({"message": "Používateľ a jeho dáta boli vymazané."})
 


# ---------- Detail testov používateľa ----------
@admin_api_bp.route("/users/<int:user_id>/tests", methods=["GET"])
@admin_required
def user_tests(user_id):
    student = Student.query.get(user_id)
    if not student:
        return jsonify({"error": "Používateľ neexistuje."}), 404

    def serialize(a):
        return {
            "id": a.id,
            "question_id": a.question_id,
            "category": a.category,
            "answer_code": a.answer_code,
            "is_correct": a.is_correct,
            "test_type": a.test_type,
            "test_session": a.test_session,
        }

    pretest = [serialize(a) for a in StudentAnswer.query.filter_by(student_id=user_id, test_type="predtest").order_by(StudentAnswer.id).all()]

    main_answers = StudentAnswer.query.filter_by(student_id=user_id, test_type="main").order_by(StudentAnswer.id).all()
    # zoskup main podľa test_session
    sessions = {}
    for a in main_answers:
        key = a.test_session or "—"
        sessions.setdefault(key, []).append(serialize(a))
    main_tests = [{"test_session": k, "answers": v} for k, v in sessions.items()]

    return jsonify({
        "user": {"id": student.id, "name": student.name, "surname": student.surname, "login": student.login},
        "pretest": pretest,
        "main_tests": main_tests,
    })


# ---------- Úprava jednej odpovede ----------
@admin_api_bp.route("/answers/<int:answer_id>", methods=["PATCH"])
@admin_required
def update_answer(answer_id):
    a = StudentAnswer.query.get(answer_id)
    if not a:
        return jsonify({"error": "Odpoveď neexistuje."}), 404
    data = request.get_json(silent=True) or {}
    if "answer_code" in data:
        a.answer_code = data["answer_code"]
    if "is_correct" in data:
        a.is_correct = bool(data["is_correct"])
    if "category" in data and data["category"]:
        a.category = data["category"]
    db.session.commit()
    return jsonify({"message": "Odpoveď aktualizovaná."})


@admin_api_bp.route("/answers/<int:answer_id>", methods=["DELETE"])
@admin_required
def delete_answer(answer_id):
    a = StudentAnswer.query.get(answer_id)
    if not a:
        return jsonify({"error": "Odpoveď neexistuje."}), 404
    db.session.delete(a)
    db.session.commit()
    return jsonify({"message": "Odpoveď vymazaná."})


# ---------- Vymazať celý predtest používateľa ----------
@admin_api_bp.route("/users/<int:user_id>/pretest", methods=["DELETE"])
@admin_required
def delete_pretest(user_id):
    StudentAnswer.query.filter_by(student_id=user_id, test_type="predtest").delete()
    TestSummary.query.filter_by(student_id=user_id, test_type="predtest").delete()
    db.session.commit()
    return jsonify({"message": "Predtest vymazaný."})


# ---------- Vymazať konkrétny hlavný test (session) ----------
@admin_api_bp.route("/users/<int:user_id>/tests/<test_session>", methods=["DELETE"])
@admin_required
def delete_main_test(user_id, test_session):
    StudentAnswer.query.filter_by(student_id=user_id, test_type="main", test_session=test_session).delete()
    TestSummary.query.filter_by(student_id=user_id, test_type="main", test_session=test_session).delete()
    db.session.commit()
    return jsonify({"message": "Test vymazaný."})


# ============================================================
# SPRÁVA DOTAZNÍKA (otázky)
# ============================================================
def _q_public(q):
    opts = []
    if q.options_json:
        try: opts = json.loads(q.options_json)
        except Exception: opts = []
    return {
        "id": q.id,
        "qkey": q.qkey,
        "label_sk": q.label_sk,
        "label_en": q.label_en,
        "qtype": q.qtype,
        "options": opts,
        "required": q.required,
        "position": q.position,
        "active": q.active,
    }


@admin_api_bp.route("/feedback/questions", methods=["GET"])
@admin_required
def list_feedback_questions():
    qs = FeedbackQuestion.query.order_by(FeedbackQuestion.position, FeedbackQuestion.id).all()
    return jsonify({"questions": [_q_public(q) for q in qs]})


@admin_api_bp.route("/feedback/questions", methods=["POST"])
@admin_required
def create_feedback_question():
    data = request.get_json(silent=True) or {}
    qkey = (data.get("qkey") or "").strip()
    label_sk = (data.get("label_sk") or "").strip()
    label_en = (data.get("label_en") or "").strip()
    qtype = (data.get("qtype") or "select").strip()
    if not qkey or not label_sk or not label_en:
        return jsonify({"error": "Vyplň kľúč a text otázky (SK aj EN)."}), 400
    if FeedbackQuestion.query.filter_by(qkey=qkey).first():
        return jsonify({"error": "Otázka s týmto kľúčom už existuje."}), 409
    options = data.get("options") or []
    maxpos = db.session.query(db.func.max(FeedbackQuestion.position)).scalar() or 0
    q = FeedbackQuestion(
        qkey=qkey, label_sk=label_sk, label_en=label_en, qtype=qtype,
        options_json=json.dumps(options, ensure_ascii=False),
        required=bool(data.get("required", True)),
        position=maxpos + 1, active=True,
    )
    db.session.add(q)
    db.session.commit()
    return jsonify({"message": "Otázka pridaná.", "question": _q_public(q)}), 201


@admin_api_bp.route("/feedback/questions/<int:qid>", methods=["PATCH"])
@admin_required
def update_feedback_question(qid):
    q = FeedbackQuestion.query.get(qid)
    if not q:
        return jsonify({"error": "Otázka neexistuje."}), 404
    data = request.get_json(silent=True) or {}
    if "label_sk" in data: q.label_sk = data["label_sk"]
    if "label_en" in data: q.label_en = data["label_en"]
    if "qtype" in data: q.qtype = data["qtype"]
    if "options" in data: q.options_json = json.dumps(data["options"] or [], ensure_ascii=False)
    if "required" in data: q.required = bool(data["required"])
    if "active" in data: q.active = bool(data["active"])
    if "position" in data: q.position = int(data["position"])
    db.session.commit()
    return jsonify({"message": "Otázka aktualizovaná.", "question": _q_public(q)})


@admin_api_bp.route("/feedback/questions/<int:qid>", methods=["DELETE"])
@admin_required
def delete_feedback_question(qid):
    q = FeedbackQuestion.query.get(qid)
    if not q:
        return jsonify({"error": "Otázka neexistuje."}), 404
    # Zmaž aj odpovede na túto otázku
    FeedbackResponse.query.filter_by(qkey=q.qkey).delete()
    db.session.delete(q)
    db.session.commit()
    return jsonify({"message": "Otázka a jej odpovede vymazané."})
