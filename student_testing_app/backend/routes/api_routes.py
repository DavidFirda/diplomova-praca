import json
from flask import Blueprint, request, jsonify, session, Response, send_file
from services.capture_output import capture_output, compare_outputs
from services.extract_starter_code import extract_starter_code
from models import db, Student, Question, StudentAnswer, TestSummary, StudentFeedback, FeedbackQuestion, FeedbackResponse
from algorithms.random_selector import RandomQuestionSelector
from algorithms.q_selector import QLearningQuestionSelector
from algorithms.pomdp_selector import POMDPQuestionSelector
from collections import Counter, defaultdict
from io import BytesIO
import pandas as pd

selector_cache = {}
student_attempts = defaultdict(int)
api_bp = Blueprint('api', __name__)

### Kontrola API stavu ###
@api_bp.route("/", methods=["GET"])
def home():
    return jsonify({"message": "API is running!"}), 200

# Registrácia a prihlásenie študentov teraz rieši auth_routes.py (auth_bp,
# prefix /api/auth) - obsahuje heslá, email a reset hesla. Pôvodné /register
# a /login tu boli zámerne odstránené, aby nezostal nezabezpečený obchádzací
# spôsob vytvorenia účtu bez hesla.

@api_bp.route("/test/start", methods=["POST"])
def start_test():
    data = request.get_json()
    student_id = data.get("student_id")
    question_ids = data.get("question_ids") 

    if not student_id or not question_ids:
        return jsonify({"error": "Missing student_id or id"}), 400

    selected_questions = Question.query.filter(Question.id.in_(question_ids)).all()

    session["test_questions"] = [q.id for q in selected_questions]
    session["student_id"] = student_id

    session["attempts"] = {}
    session.modified = True

    return jsonify([{
        "id": q.id,
        "instruction": q.instruction,
        "input_data": q.input_data,
        "category": q.category,
        "starter_code": extract_starter_code(q.output)
    } for q in selected_questions])

@api_bp.route("/main_test/start", methods=["POST"])
def start_main_test():
    data = request.get_json()
    student_id = data.get("student_id")
    categories = data.get("categories", [])
    excluded_ids = data.get("excluded_ids", [])
    test_session = data.get("test_session") 

    print(f"[DEBUG] incoming test_session: {test_session}", flush=True)
    
    if not student_id or not categories:
        return jsonify({"error": "Chýbajúce údaje"}), 400

    if not test_session:
        previous_sessions = (
            db.session.query(StudentAnswer.test_session)
            .filter_by(student_id=student_id, test_type="main")
            .distinct()
            .count()
        )
        test_session = f"main-{previous_sessions + 1}"

    cache_key = (student_id, test_session)
    sid = int(student_id)
    if sid % 3 == 1:  # 1,4,7,...
        selector = RandomQuestionSelector(categories)
    elif sid % 3 == 2:  # 2,5,8,...
        if cache_key not in selector_cache:
            selector_cache[cache_key] = QLearningQuestionSelector(
                student_id=sid,
                categories=categories,
                test_session=test_session,
                excluded_ids=excluded_ids
            )
        selector = selector_cache[cache_key]
    else:  # 3,6,9,...
        selector = POMDPQuestionSelector(
            student_id=sid,
            categories=categories,
            test_session=test_session,
            excluded_ids=excluded_ids
        )

    selected_question = selector.select()

    if not selected_question:
        return jsonify({"error": "Žiadne ďalšie otázky"}), 404

    starter_code = extract_starter_code(selected_question.output)

    return jsonify({
        "id": selected_question.id,
        "instruction": selected_question.instruction,
        "input_data": selected_question.input_data,
        "category": selected_question.category,
        "starter_code": starter_code,
        "test_session": test_session 
    })

@api_bp.route("/test/answer", methods=["POST"])
def evaluate_answer():
    data = request.get_json()
    student_id = data.get("student_id")
    question_id = data.get("question_id")
    code = data.get("code")
    test_type = data.get("test_type", "main")
    test_session = data.get("test_session")

    if not student_id or not question_id:
        return jsonify({"error": "Missing student or question ID"}), 400

    question = Question.query.get(question_id)
    category = question.category
    starter_code = extract_starter_code(question.output)

    if not code or not code.strip() or code.strip() == starter_code.strip():
        return jsonify({
            "correct": False,
            "message": "🛠️ Nezadal si žiadny kód. Skús niečo napísať a odoslať odpoveď."
        })

    attempt_key = (student_id, test_session, question_id)
    attempts = student_attempts[attempt_key]

    student_output, student_error = capture_output(code)
    expected_output, expected_error = capture_output(question.output)

    if expected_error:
        if int(student_id) % 3 == 2 and question.category and test_type == "main":
            cache_key = (student_id, test_session)
            if cache_key not in selector_cache:
                selector_cache[cache_key] = QLearningQuestionSelector(
                    student_id=student_id,
                    categories=["Sorting", "Syntax", "Data Structures", "Scientific Computing"],
                    test_session=test_session
                )
            selector = selector_cache[cache_key]
            selector.update_after_answer(
                question_id=question.id,
                category=question.category,
                correct=False
            )
        elif int(student_id) % 3 == 0 and question.category and test_type == "main":
            cache_key = (student_id, test_session)
            if cache_key not in selector_cache:
                selector_cache[cache_key] = POMDPQuestionSelector(
                    student_id=student_id,
                    categories=["Sorting", "Syntax", "Data Structures", "Scientific Computing"],
                    test_session=test_session,
                    excluded_ids=[]
                )
            selector = selector_cache[cache_key]
            selector.update_after_answer(
                question_id=question.id,
                category=question.category,
                correct=False
            )

        update_summary(student_id, test_type, test_session, category, is_correct=False)

        student_answer = StudentAnswer(
            student_id=student_id,
            question_id=question_id,
            answer_code=code,
            category=category,
            is_correct=True,
            test_type=test_type,
            test_session=test_session
        )
        db.session.add(student_answer)
        db.session.commit()

        return jsonify({
            "correct": False,
            "message": f"❌ Interná chyba v hodnotení otázky: {expected_error}",
            "student_output": student_output
        })

    correct = compare_outputs(student_output, expected_output)

    if correct:
        if int(student_id) % 3 == 2 and question.category and test_type == "main":
            cache_key = (student_id, test_session)
            if cache_key not in selector_cache:
                selector_cache[cache_key] = QLearningQuestionSelector(
                    student_id=student_id,
                    categories=["Sorting", "Syntax", "Data Structures", "Scientific Computing"],
                    test_session=test_session
                )
            selector = selector_cache[cache_key]
            selector.update_after_answer(
                question_id=question.id,
                category=question.category,
                correct=correct
            )
        elif int(student_id) % 3 == 0 and question.category and test_type == "main":
            cache_key = (student_id, test_session)
            if cache_key not in selector_cache:
                selector_cache[cache_key] = POMDPQuestionSelector(
                    student_id=student_id,
                    categories=["Sorting", "Syntax", "Data Structures", "Scientific Computing"],
                    test_session=test_session,
                    excluded_ids=[]
                )
            selector = selector_cache[cache_key]
            selector.update_after_answer(
                question_id=question.id,
                category=question.category,
                correct=correct
            )

        update_summary(student_id, test_type, test_session, category, is_correct=True)

        student_answer = StudentAnswer(
            student_id=student_id,
            question_id=question_id,
            answer_code=code,
            category=category,
            is_correct=True,
            test_type=test_type,
            test_session=test_session
        )
        db.session.add(student_answer)
        db.session.commit()
        return jsonify({
            "correct": True,     
            "student_output": student_output
        })

    if attempts < 1:
        student_attempts[attempt_key] += 1
        return jsonify({
            "correct": False,
            "message": "🛠️ Výstup nie je správny. Skús to ešte raz opraviť!",
            "student_output": student_output
        })
    
    if int(student_id) % 3 == 2 and question.category and test_type == "main":
        cache_key = (student_id, test_session)
        if cache_key not in selector_cache:
            selector_cache[cache_key] = QLearningQuestionSelector(
                student_id=student_id,
                categories=["Sorting", "Syntax", "Data Structures", "Scientific Computing"],
                test_session=test_session
            )
        selector = selector_cache[cache_key]
        selector.update_after_answer(
            question_id=question.id,
            category=question.category,
            correct=correct
        )
    elif int(student_id) % 3 == 0 and question.category and test_type == "main":
        cache_key = (student_id, test_session)
        if cache_key not in selector_cache:
            selector_cache[cache_key] = POMDPQuestionSelector(
                student_id=student_id,
                categories=["Sorting", "Syntax", "Data Structures", "Scientific Computing"],
                test_session=test_session,
                excluded_ids=[]
            )
        selector = selector_cache[cache_key]
        selector.update_after_answer(
            question_id=question.id,
            category=question.category,
            correct=correct
        )
    
    update_summary(student_id, test_type, test_session, category, is_correct=False)

    student_answer = StudentAnswer(
        student_id=student_id,
        question_id=question_id,
        answer_code=code,
        category=category,
        is_correct=False,
        test_type=test_type,
        test_session=test_session
    )
    db.session.add(student_answer)
    db.session.commit()

    return jsonify({
        "correct": False,
        "student_output": student_output,
        "show_solution": True,
        "solution_code": question.output
    })

def update_summary(student_id, test_type, test_session, category, is_correct):
    if test_type == "predtest":
        return

    summary = TestSummary.query.filter_by(
        student_id=student_id,
        test_type=test_type,
        test_session=test_session,
        category=category
    ).first()

    if not summary:
        summary = TestSummary(
            student_id=student_id,
            test_type=test_type,
            test_session=test_session,
            category=category,
            total_answers=0,
            correct_answers=0,
            incorrect_answers=0
        )
        db.session.add(summary)

    summary.total_answers = summary.total_answers or 0
    summary.correct_answers = summary.correct_answers or 0
    summary.incorrect_answers = summary.incorrect_answers or 0

    summary.total_answers += 1
    if is_correct:
        summary.correct_answers += 1
    else:
        summary.incorrect_answers += 1

@api_bp.route("/test/analysis", methods=["POST"])
def test_analysis():
    data = request.get_json()
    student_id = data.get("student_id")
    test_session = data.get("test_session")

    if not student_id or not test_session:
        return jsonify({"error": "Missing student_id or test_session"}), 400

    # Získaj odpovede študenta pre túto session
    answers = StudentAnswer.query.filter_by(
        student_id=student_id,
        test_type="main",
        test_session=test_session
    ).all()

    if not answers:
        return jsonify({"error": "No answers found"}), 404

    total_questions = len(answers)
    correct_answers = sum(1 for a in answers if a.is_correct)
    student_accuracy = round((correct_answers / total_questions) * 100, 1)

    # Porovnaj s ostatnými študentmi
    student_scores = []
    students = db.session.query(StudentAnswer.student_id).filter_by(test_type="main").distinct().all()
    for sid_row in students:
        sid = sid_row[0]
        all_answers = StudentAnswer.query.filter_by(student_id=sid, test_type="main").all()
        if not all_answers:
            continue
        correct = sum(1 for a in all_answers if a.is_correct)
        total = len(all_answers)
        if total == 0:
            continue
        accuracy = correct / total
        student_scores.append((sid, accuracy))

    # Percentil: Koľko študentov má horší výsledok
    num_below = sum(1 for sid, acc in student_scores if acc < (student_accuracy / 100))
    percentile = round((num_below / len(student_scores)) * 100, 1) if student_scores else 0.0

    return jsonify({
        "correct_answers": correct_answers,
        "total_questions": total_questions,
        "student_accuracy": student_accuracy,
        "percentile_rank": percentile
    })

@api_bp.route("/feedback/questions", methods=["GET"])
def feedback_questions():
    """Verejné: aktívne otázky dotazníka pre používateľa (z DB)."""
    qs = FeedbackQuestion.query.filter_by(active=True).order_by(
        FeedbackQuestion.position, FeedbackQuestion.id
    ).all()
    out = []
    for q in qs:
        try:
            opts = json.loads(q.options_json) if q.options_json else []
        except Exception:
            opts = []
        out.append({
            "qkey": q.qkey,
            "label_sk": q.label_sk,
            "label_en": q.label_en,
            "qtype": q.qtype,
            "options": opts,
            "required": q.required,
        })
    return jsonify({"questions": out})


@api_bp.route("/feedback", methods=["POST"])
def feedback():
    data = request.get_json() or {}
    student_id = data.get("student_id")
    if not student_id:
        return jsonify({"error": "Chýba student_id"}), 400

    answers = data.get("answers") or {}
    # ulož každú odpoveď ako FeedbackResponse (upsert podľa qkey)
    updated = False
    for qkey, value in answers.items():
        existing = FeedbackResponse.query.filter_by(student_id=student_id, qkey=qkey).first()
        if existing:
            existing.value = str(value) if value is not None else None
            updated = True
        else:
            db.session.add(FeedbackResponse(student_id=student_id, qkey=qkey, value=str(value) if value is not None else None))
    db.session.commit()

    msg = "Odpovede boli aktualizované. Ďakujeme!" if updated else "Ďakujeme za vyplnenie dotazníka!"
    return jsonify({"message": msg, "updated": updated})


@api_bp.route("/feedback/get", methods=["POST"])
def get_feedback():
    data = request.get_json() or {}
    student_id = data.get("student_id")
    if not student_id:
        return jsonify({"error": "Chýba student_id"}), 400

    responses = FeedbackResponse.query.filter_by(student_id=student_id).all()
    if not responses:
        return jsonify({"submitted": False, "feedback": {}})

    fb = {r.qkey: r.value for r in responses}
    return jsonify({"submitted": True, "feedback": fb})


@api_bp.route("/feedback/check", methods=["POST"])
def check_feedback_submitted():
    data = request.get_json() or {}
    student_id = data.get("student_id")
    if not student_id:
        return jsonify({"error": "Chýba student_id"}), 400
    existing = FeedbackResponse.query.filter_by(student_id=student_id).first()
    return jsonify({"submitted": bool(existing)})