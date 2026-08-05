import json
from flask import Blueprint, request, jsonify, session, Response, send_file
from capture_output import capture_output, compare_outputs
from extract_starter_code import extract_starter_code
from models import db, Student, Question, StudentAnswer, TestSummary, StudentFeedback
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

### Registrácia nového študenta ###
@api_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    name = data.get("name")
    login = data.get("login")

    if not name or not login:
        return jsonify({"error": "Name and login are required"}), 400

    existing_student = Student.query.filter_by(login=login).first()
    if existing_student:
        return jsonify({"error": "Login already taken"}), 400

    student = Student(name=name, login=login)
    db.session.add(student)
    db.session.commit()

    return jsonify({"id": student.id, "name": student.name, "login": student.login, "message": "Registration successful!"}), 201

### Prihlásenie študenta ###
@api_bp.route("/login", methods=["POST"])
def login():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    login = data.get("login")
    if not login:
        return jsonify({"error": "Login required"}), 400

    student = Student.query.filter_by(login=login).first()
    if not student:
        return jsonify({"error": "Invalid login"}), 404

    return jsonify({"id": student.id}), 200
  
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

@api_bp.route("/feedback", methods=["POST"])
def feedback():
    data = request.get_json()
    student_id = data.get("student_id")

    if not student_id:
        return jsonify({"error": "Chýba student_id"}), 400

    feedback = StudentFeedback(
        student_id=student_id,
        gender=data.get("gender"),
        age=data.get("age"),
        experience=data.get("experience"),
        field_of_study=data.get("field_of_study"),
        understand_questions=data.get("understand_questions"),
        easy_navigation=data.get("easy_navigation"),
        motivation_level=data.get("motivation_level"),
        helpful_feedback=data.get("helpful_feedback"),
        overall_usefulness=data.get("overall_usefulness"),
        difficulty_match=data.get("difficulty_match"),
        improved_skills=data.get("improved_skills"),
        time_spent=data.get("time_spent"),
        future_interest=data.get("future_interest"),
        ui_satisfaction=data.get("ui_satisfaction"),
        improvement_suggestion=data.get("improvement_suggestion")
    )

    db.session.add(feedback)
    db.session.commit()
    return jsonify({"message": "Ďakujeme za vyplnenie dotazníka!"})

@api_bp.route("/feedback/check", methods=["POST"])
def check_feedback_submitted():
    data = request.get_json()
    student_id = data.get("student_id")

    if not student_id:
        return jsonify({"error": "Chýba student_id"}), 400

    existing = StudentFeedback.query.filter_by(student_id=student_id).first()
    return jsonify({"submitted": bool(existing)})