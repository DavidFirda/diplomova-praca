# ============================================================
# Admin API - správa používateľov, testov a dotazníka.
# Autentifikácia cez SESSION + rola "admin" (nie token z URL).
# ============================================================
import json
from flask import Blueprint, request, jsonify
from flask_login import current_user

from extensions import admin_required
from models import (
    db, Student, Question, StudentAnswer, TestSummary, TestProgress, AnswerAttempt,
    FeedbackQuestion, FeedbackResponse, StudentFeedback, FeedbackMessage,
)
from models_exercises import Exercise, ExerciseProgress
from models_invites import Invitation
from models_ulohy import TaskAssignment, TaskAttempt, TaskEvent
from routes.admin_ulohy_routes import flag_count as ulohy_flag_count
from services import integrity as integrity_check
from services.settings import (
    questionnaire_published, sections_state, set_questionnaire_published, set_tests_enabled,
)
from services.test_flow import clear_attempts, clear_main_progress, pretest_state

admin_api_bp = Blueprint("admin_api", __name__)


# ---------- Kontrola, či je aktuálny používateľ admin ----------
@admin_api_bp.route("/me", methods=["GET"])
def admin_me():
    return jsonify({"is_admin": bool(current_user.is_authenticated and current_user.is_admin)})


# ============================================================
# SPRÁVA POUŽÍVATEĽOV
# ============================================================
@admin_api_bp.route("/users", methods=["GET"])
@admin_required
def list_users():
    students = Student.query.order_by(Student.id).all()
    published_ex = [e.id for e in Exercise.query.filter_by(published=True).all()]
    result = []
    for s in students:
        pre = pretest_state(s.id)   # predtest je hotový až po zodpovedaní všetkých otázok
        main_sessions = {a.test_session for a in StudentAnswer.query.filter_by(student_id=s.id, test_type="main").all() if a.test_session}
        fb = FeedbackResponse.query.filter_by(student_id=s.id).count() + StudentFeedback.query.filter_by(student_id=s.id).count()
        ulohy_done = TaskAssignment.query.filter(
            TaskAssignment.student_id == s.id, TaskAssignment.status.in_(("solved", "failed")))
        result.append({
            "id": s.id,
            "name": s.name,
            "surname": s.surname,
            "login": s.login,
            "email": s.email,
            "role": getattr(s, "role", "user") or "user",
            "pretest_answers": pre["answered"],
            "pretest_total": pre["total"],
            "pretest_done": pre["done"],
            "main_tests": len(main_sessions),
            # cvičenia: dokončené / publikované
            "exercises_total": len(published_ex),
            "exercises_done": ExerciseProgress.query.filter(
                ExerciseProgress.student_id == s.id, ExerciseProgress.status == "completed",
                ExerciseProgress.exercise_id.in_(published_ex)).count() if published_ex else 0,
            "ulohy_total": ulohy_done.count(),
            "ulohy_solved": ulohy_done.filter(TaskAssignment.status == "solved").count(),
            "feedback_done": fb > 0,
            "flags_ulohy": ulohy_flag_count(s.id),
            "flags_tests": StudentAnswer.query.filter_by(
                student_id=s.id, integrity_flag=True, flag_dismissed=False).count(),
            "flags_exercises": sum(
                integrity_check.exercise_active_count(p.integrity_json)
                for p in ExerciseProgress.query.filter(
                    ExerciseProgress.student_id == s.id, ExerciseProgress.integrity_json.isnot(None))),
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
        # poradie: pokusy musia ísť pred úlohami (cudzí kľúč)
        for model in (TaskAttempt, TaskAssignment, TaskEvent,
                      AnswerAttempt, TestProgress, StudentAnswer, TestSummary,
                      FeedbackResponse, StudentFeedback, FeedbackMessage, ExerciseProgress):
            model.query.filter_by(student_id=user_id).delete()
        Invitation.query.filter(
            (Invitation.student_id == user_id) | (Invitation.email == student.email)
        ).delete(synchronize_session=False)

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

    answers = StudentAnswer.query.filter_by(student_id=user_id).order_by(StudentAnswer.id).all()
    questions = {q.id: q for q in Question.query.filter(
        Question.id.in_({a.question_id for a in answers})).all()} if answers else {}

    def serialize(a):
        q = questions.get(a.question_id)
        return {
            "id": a.id,
            "question_id": a.question_id,
            "category": a.category,
            "answer_code": a.answer_code,
            "is_correct": a.is_correct,
            "test_type": a.test_type,
            "test_session": a.test_session,
            # zadanie a správne riešenie (admin ich vidí pri odpovedi)
            "instruction": ((q.instruction_sk or q.instruction) if q else ""),
            "input_data": q.input_data if q else "",
            "solution_code": q.output if q else "",
            "integrity": integrity_check.admin_view(a.integrity_json, a.integrity_flag, a.flag_dismissed),
        }

    def stats(items):
        return {
            "answered": len(items),
            "correct": sum(1 for x in items if x["is_correct"]),
            "active_flags": sum(1 for x in items if x["integrity"]["active"]),
        }

    pretest = [serialize(a) for a in answers if a.test_type == "predtest"]
    pre = pretest_state(user_id)

    # hlavné testy zoskupené podľa test_session (v poradí, ako vznikli)
    sessions = {}
    for a in answers:
        if a.test_type == "main":
            sessions.setdefault(a.test_session or "—", []).append(serialize(a))
    progress = {p.test_session: p for p in TestProgress.query.filter_by(student_id=user_id, test_type="main")}
    main_tests = []
    for k, items in sessions.items():
        p = progress.get(k)
        main_tests.append({
            "test_session": k, "answers": items, **stats(items),
            "total": p.total_questions if p else None,
            "status": p.status if p else "done",
        })

    return jsonify({
        "user": {"id": student.id, "name": student.name, "surname": student.surname,
                 "login": student.login, "email": student.email},
        "pretest": pretest,
        "pretest_summary": {**stats(pretest), "total": pre["total"], "done": pre["done"]},
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
    if "flag_dismissed" in data:        # zrušenie / obnovenie red flagu (kontrola originality)
        if not isinstance(data["flag_dismissed"], bool):
            return jsonify({"error": "Pole 'flag_dismissed' musí byť true/false."}), 400
        if not a.integrity_flag:
            return jsonify({"error": "Odpoveď nemá red flag."}), 400
        a.flag_dismissed = data["flag_dismissed"]
        a.integrity_json = integrity_check.set_dismissed(a.integrity_json, a.flag_dismissed, current_user.id)
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
    clear_attempts(user_id, "predtest")
    db.session.commit()
    return jsonify({"message": "Predtest vymazaný."})


# ---------- Vymazať konkrétny hlavný test (session) ----------
@admin_api_bp.route("/users/<int:user_id>/tests/<test_session>", methods=["DELETE"])
@admin_required
def delete_main_test(user_id, test_session):
    StudentAnswer.query.filter_by(student_id=user_id, test_type="main", test_session=test_session).delete()
    TestSummary.query.filter_by(student_id=user_id, test_type="main", test_session=test_session).delete()
    clear_attempts(user_id, "main", test_session)
    clear_main_progress(user_id, test_session)
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


# ============================================================
# ZVEREJNENIE DOTAZNÍKA
# ============================================================
@admin_api_bp.route("/questionnaire", methods=["GET"])
@admin_required
def get_questionnaire_state():
    return jsonify({"published": questionnaire_published()})


@admin_api_bp.route("/questionnaire", methods=["PUT"])
@admin_required
def set_questionnaire_state():
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("published"), bool):
        return jsonify({"error": "Pole 'published' musí byť true/false."}), 400
    set_questionnaire_published(data["published"])
    msg = "Dotazník je zverejnený." if data["published"] else "Dotazník je skrytý."
    return jsonify({"message": msg, "published": data["published"]})


# ============================================================
# DOSTUPNOSŤ SEKCIÍ PRE ŠTUDENTOV (kolónka na dashboarde, odkaz v menu, API)
# ============================================================
@admin_api_bp.route("/sections", methods=["GET"])
@admin_required
def get_sections():
    return jsonify(sections_state())


@admin_api_bp.route("/sections", methods=["PUT"])
@admin_required
def set_sections():
    data = request.get_json(silent=True) or {}
    if "tests" in data:
        if not isinstance(data["tests"], bool):
            return jsonify({"error": "Pole 'tests' musí byť true/false."}), 400
        set_tests_enabled(data["tests"])
    return jsonify({**sections_state(), "message": "Dostupnosť sekcií uložená."})


# ============================================================
# SPRÁVY Z FEEDBACK FORMULÁRA
# ============================================================
@admin_api_bp.route("/feedback/messages", methods=["GET"])
@admin_required
def list_feedback_messages():
    rows = (db.session.query(FeedbackMessage, Student)
            .join(Student, Student.id == FeedbackMessage.student_id)
            .order_by(FeedbackMessage.created_at.desc(), FeedbackMessage.id.desc())
            .limit(500).all())
    return jsonify({"messages": [{
        "id": m.id,
        "category": m.category,
        "rating": m.rating,
        "message": m.message,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "student": {"id": s.id, "login": s.login, "name": f"{s.name} {s.surname}".strip()},
    } for m, s in rows]})


@admin_api_bp.route("/feedback/messages/<int:message_id>", methods=["DELETE"])
@admin_required
def delete_feedback_message(message_id):
    m = db.session.get(FeedbackMessage, message_id)
    if not m:
        return jsonify({"error": "Správa neexistuje."}), 404
    db.session.delete(m)
    db.session.commit()
    return jsonify({"message": "Správa vymazaná."})
