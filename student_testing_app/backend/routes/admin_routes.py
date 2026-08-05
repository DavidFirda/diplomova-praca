import json
from flask import Blueprint, abort, jsonify, Response, request, send_file
from models import Student, StudentAnswer, TestSummary, StudentFeedback
from collections import Counter
from io import BytesIO
import pandas as pd
from flask import current_app

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/students", methods=["GET"])
def export_students_full():
    token = request.args.get("token")
    #if token != "AdaptiveLearningBC":
    if token != current_app.config['ADMIN_TOKEN']:
        abort(401)

    students = Student.query.all()
    rows = []

    def compute_stats(answers):
        total = len(answers)
        correct = sum(1 for a in answers if a.is_correct)
        rate = round((correct / total * 100), 1) if total > 0 else 0
        return total, correct, rate

    def get_weak_categories(answers):
        stats = {}
        for a in answers:
            if not a.category:
                continue
            if a.category not in stats:
                stats[a.category] = {"total": 0, "correct": 0}
            stats[a.category]["total"] += 1
            if a.is_correct:
                stats[a.category]["correct"] += 1

        weak = []
        for cat, val in stats.items():
            if val["total"] > 0:
                rate = val["correct"] / val["total"]
                if rate < 0.6:
                    weak.append(cat)
        return ", ".join(weak)

    for s in students:
        pred_answers = StudentAnswer.query.filter_by(student_id=s.id, test_type="predtest").all()
        pred_total, pred_correct, pred_rate = compute_stats(pred_answers)
        weak_categories = get_weak_categories(pred_answers)

        summaries = TestSummary.query.filter_by(student_id=s.id, test_type="main").all()
        sessions = {}
        
        for summary in summaries:
            session_id = summary.test_session
            if session_id not in sessions:
                sessions[session_id] = {
                    "student_id": s.id,
                    "name": s.name,
                    "login": s.login,
                    "algorithm": "",
                    "pred_total_answers": pred_total,
                    "pred_correct_answers": pred_correct,
                    "pred_accuracy": f"{pred_rate:.1f}%" if pred_total > 0 else "N/A",
                    "predtest_weak_categories": weak_categories, 
                    "test_session": session_id,
                    "main_total": 0,
                    "main_correct": 0
                }

            sessions[session_id]["main_total"] += summary.total_answers
            sessions[session_id]["main_correct"] += summary.correct_answers
            sessions[session_id][f"{summary.category}_accuracy"] = (
                f"{summary.accuracy * 100:.1f}%" if summary.total_answers > 0 else "N/A"
            )

        for session in sessions.values():
            total = session["main_total"]
            correct = session["main_correct"]
            session["main_accuracy"] = f"{round(correct / total * 100, 1)}%" if total > 0 else "N/A"

            if s.id % 3 == 1:
                session["algorithm"] = "Random"
            elif s.id % 3 == 2:
                session["algorithm"] = "Q-Learning"
            else:
                session["algorithm"] = "POMDP"

        rows.extend(sessions.values())

    if not rows:
        return jsonify({"error": "Žiadne dáta na export."}), 404

    df = pd.DataFrame(rows)

    def parse_accuracy(val):
        try:
            return float(str(val).replace("%", ""))
        except:
            return 0.0

    df["overall_accuracy_value"] = df["main_accuracy"].apply(parse_accuracy)

    excel_stream = BytesIO()
    df.to_excel(excel_stream, index=False, sheet_name="All_Students")
    excel_stream.seek(0)

    return send_file(
        excel_stream,
        download_name="all_students_results.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@admin_bp.route("/students/summary", methods=["GET"])
def get_all_students():
    token = request.args.get("token")
    if token != current_app.config['ADMIN_TOKEN']:
        abort(401)

    students = Student.query.all()
    result = []

    def compute_stats(answers):
        total = len(answers)
        correct = sum(1 for a in answers if a.is_correct)
        rate = round((correct / total * 100), 1) if total > 0 else 0
        return total, correct, rate

    def category_stats(answers):
        stats = {}
        for a in answers:
            if not a.category:
                continue
            if a.category not in stats:
                stats[a.category] = {"total": 0, "correct": 0}
            stats[a.category]["total"] += 1
            if a.is_correct:
                stats[a.category]["correct"] += 1

        success = {}
        counts = {}
        weak = []

        for cat, val in stats.items():
            rate = val["correct"] / val["total"]
            success[cat] = round(rate * 100, 1)
            counts[cat] = val["total"]
            if rate < 0.6:
                weak.append(cat)

        return success, counts, weak, list(stats.keys())

    for s in students:
        predtest_answers = StudentAnswer.query.filter_by(student_id=s.id, test_type="predtest").all()
        pred_total, pred_correct, pred_rate = compute_stats(predtest_answers)
        pred_success, pred_counts, pred_weak, pred_used = category_stats(predtest_answers)

        # --- Hlavné testy (zo sumarizačnej tabuľky) ---
        summaries = TestSummary.query.filter_by(student_id=s.id, test_type="main").all()
        sessions = {}
        for summary in summaries:
            if summary.test_session not in sessions:
                sessions[summary.test_session] = {
                    "test_session": summary.test_session,
                    "total_answers": 0,
                    "correct_answers": 0,
                    "category_success": {},
                    "categories": {}
                }
            session = sessions[summary.test_session]
            session["total_answers"] += summary.total_answers
            session["correct_answers"] += summary.correct_answers
            session["category_success"][summary.category] = f"{summary.accuracy * 100:.1f}%"
            session["categories"][summary.category] = summary.total_answers

        session_results = list(sessions.values())

        result.append({
            "id": s.id,
            "name": s.name,
            "login": s.login,

            "predtest": {
                "total_answers": pred_total,
                "correct_answers": pred_correct,
                "success_rate": f"{pred_rate:.1f}%" if pred_total > 0 else "N/A",
                "category_success": pred_success,
                "weak_categories": pred_weak,
                "categories": pred_counts if pred_used else ["Žiadne odpovede"]
            },

            "main_tests": session_results 
        })

    return Response(
        json.dumps(result, ensure_ascii=False, indent=2),
        mimetype='application/json'
    )

@admin_bp.route("/algorithms/stats", methods=["GET"])
def algorithm_stats():
    token = request.args.get("token")
    if token != current_app.config['ADMIN_TOKEN']:
        abort(401)

    students = Student.query.all()

    algo_data = {
        "Random": [],
        "Q-Learning": [],
        "POMDP": []
    }

    category_aggregate = {
        "Random": {},
        "Q-Learning": {},
        "POMDP": {}
    }

    def get_algorithm(student_id):
        if student_id % 3 == 1:
            return "Random"
        elif student_id % 3 == 2:
            return "Q-Learning"
        else:
            return "POMDP"

    def compute_accuracy(answers):
        total = len(answers)
        correct = sum(1 for a in answers if a.is_correct)
        return (correct / total) * 100 if total > 0 else None

    for student in students:
        algorithm = get_algorithm(student.id)

        # Slabé kategórie z predtestu
        pred_answers = StudentAnswer.query.filter_by(student_id=student.id, test_type="predtest").all()
        weak_cats = []
        cat_stats = {}
        for ans in pred_answers:
            cat = ans.category
            if not cat:
                continue
            if cat not in cat_stats:
                cat_stats[cat] = {"total": 0, "correct": 0}
            cat_stats[cat]["total"] += 1
            if ans.is_correct:
                cat_stats[cat]["correct"] += 1
        for cat, val in cat_stats.items():
            rate = val["correct"] / val["total"]
            if rate < 0.6:
                weak_cats.append(cat)

        # Hlavný test
        main_answers = StudentAnswer.query.filter_by(student_id=student.id, test_type="main").all()
        overall_acc = compute_accuracy(main_answers)
        weak_cat_answers = [a for a in main_answers if a.category in weak_cats]
        weak_acc = compute_accuracy(weak_cat_answers)

        algo_data[algorithm].append({
            "student_id": student.id,
            "overall_accuracy": overall_acc,
            "weak_accuracy": weak_acc,
            "weak_categories": weak_cats
        })

        for cat in weak_cats:
            if cat not in category_aggregate[algorithm]:
                category_aggregate[algorithm][cat] = {"total": 0, "weak_count": 0}
            category_aggregate[algorithm][cat]["weak_count"] += 1

        # Hlavný test - počítaj počet otázok
        for ans in main_answers:
            cat = ans.category
            if not cat:
                continue
            if cat not in category_aggregate[algorithm]:
                category_aggregate[algorithm][cat] = {"total": 0, "weak_count": 0}
            category_aggregate[algorithm][cat]["total"] += 1


    # Finálne štatistiky
    def avg(values):
        clean = [v for v in values if v is not None]
        return round(sum(clean) / len(clean), 2) if clean else 0

    summary = {}
    for algo, students in algo_data.items():
        summary[algo] = {
            "count": len(students),
            "avg_overall_accuracy": avg([s["overall_accuracy"] for s in students]),
            "avg_weak_accuracy": avg([s["weak_accuracy"] for s in students]),
            "category_stats": category_aggregate[algo]
        }

    return jsonify({
        "summary": summary,
        "detailed": algo_data
    })

@admin_bp.route("/feedback", methods=["GET"])
def export_feedback():
    token = request.args.get("token")
    if token != current_app.config['ADMIN_TOKEN']:
        abort(401)
        
    feedbacks = StudentFeedback.query.all()

    data = [{
        "student_id": f.student_id,
        "gender": f.gender,
        "age": f.age,
        "experience": f.experience,
        "field_of_study": f.field_of_study,
        "understand_questions": f.understand_questions,
        "easy_navigation": f.easy_navigation,
        "motivation_level": f.motivation_level,
        "helpful_feedback": f.helpful_feedback,
        "overall_usefulness": f.overall_usefulness,
        "difficulty_match": f.difficulty_match,
        "improved_skills": f.improved_skills,
        "time_spent": f.time_spent,
        "future_interest": f.future_interest,
        "ui_satisfaction": f.ui_satisfaction,
        "improvement_suggestion": f.improvement_suggestion
    } for f in feedbacks]

    df = pd.DataFrame(data)
    excel_stream = BytesIO()
    df.to_excel(excel_stream, index=False, sheet_name="Feedback")
    excel_stream.seek(0)

    return send_file(
        excel_stream,
        download_name="student_feedback.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@admin_bp.route("/feedback/summary", methods=["GET"])
def feedback_summary():
    token = request.args.get("token")
    if token != current_app.config['ADMIN_TOKEN']:
        abort(401)

    feedbacks = StudentFeedback.query.all()
    total = len(feedbacks)

    if total == 0:
        return jsonify({"error": "Žiadne odpovede ešte neboli zaznamenané."}), 404

    fields_to_summarize = [
        "gender",
        "age",
        "experience",
        "understand_questions",
        "easy_navigation",
        "motivation_level",
        "helpful_feedback",
        "overall_usefulness",
        "difficulty_match",
        "improved_skills",
        "time_spent",
        "future_interest",
        "ui_satisfaction"
    ]

    summary = {}
    for field in fields_to_summarize:
        counter = Counter(str(getattr(f, field)) for f in feedbacks if getattr(f, field) is not None)
        summary[field] = {
            k: round(v / total * 100, 1) for k, v in counter.items()
        }

    result_dict = {
        "summary": summary,
        "total_responses": total
    }

    return Response(
        json.dumps(result_dict, ensure_ascii=False, indent=2),
        mimetype="application/json"
    )