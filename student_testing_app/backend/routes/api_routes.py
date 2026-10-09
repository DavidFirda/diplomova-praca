import json

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import case, func

from models import (
    db, Question, StudentAnswer, TestSummary, TestProgress,
    FeedbackQuestion, FeedbackResponse,
)
from services.capture_output import (
    RunnerUnavailable, capture_output, compare_outputs, expected_output,
)
from services.extract_starter_code import extract_starter_code
from services.test_flow import (
    MAIN_TEST_TOTAL, QuestionFlow,
    answered_question_ids, build_selector, get_question, get_retries_used, get_turn,
    lock_student, pretest_state, question_payload, set_retries_used,
    start_main_progress, active_main_progress, update_selector,
)

api_bp = Blueprint('api', __name__)

# Identita študenta je VŽDY z prihláseného používateľa (current_user, Flask-Login),
# nikdy z tela požiadavky - inak by si klient mohol podstrčiť cudzie student_id.


@api_bp.route("/", methods=["GET"])
def home():
    return jsonify({"message": "API is running!"}), 200


# ============================================================
# PREDTEST - progres sa ukladá priebežne (odvodzuje sa zo StudentAnswer)
# ============================================================
@api_bp.route("/pretest/state", methods=["GET"])
@login_required
def pretest_current():
    """
    Stav predtestu + otázka, na ktorej študent skončil (prvá nezodpovedaná
    v pevnom poradí). Po návrate sa tak zobrazí presne tá istá otázka;
    späť na predchádzajúce sa vrátiť nedá.
    """
    student_id = current_user.id
    state = pretest_state(student_id)
    question, retries_used = None, 0
    if not state["done"]:
        q = get_question(state["next_question_id"])
        if q:
            question = question_payload(q)
            retries_used = get_retries_used(student_id, "predtest", None, q.id)

    return jsonify({
        "done": state["done"],
        "answered": state["answered"],
        "total": state["total"],
        "attempts_used": retries_used,
        "question": question,
    })


# ============================================================
# HLAVNÝ TEST - progres v tabuľke test_progress
# ============================================================
@api_bp.route("/main_test/start", methods=["POST"])
@login_required
def start_main_test():
    """
    Vráti otázku hlavného testu:
      - rozpracovaný test pokračuje tou istou nezodpovedanou otázkou,
      - inak sa vyberie nová otázka (stratégia podľa ID študenta),
      - po 30 zodpovedaných vráti {"finished": true}.
    Kategórie, už použité otázky a session určuje server (nie klient).
    """
    student_id = current_user.id
    if not pretest_state(student_id)["done"]:
        return jsonify({
            "error": "Najprv musíš dokončiť predtest.",
            "error_key": "test.pretestRequired",
        }), 403

    lock_student(student_id)
    prog = active_main_progress(student_id) or start_main_progress(student_id)
    answered = answered_question_ids(student_id, "main", prog.test_session)
    meta = {
        "test_session": prog.test_session,
        "answered": len(answered),
        "total": prog.total_questions or MAIN_TEST_TOTAL,
    }

    if len(answered) >= meta["total"]:
        prog.status = "done"
        prog.current_question_id = None
        db.session.commit()
        return jsonify({"finished": True, **meta})

    # pokračovanie: otázka, ktorá už bola zobrazená, ale ešte nie je zodpovedaná
    question = get_question(prog.current_question_id) if prog.current_question_id else None
    if question is None or question.id in answered:
        question = build_selector(student_id, prog.test_session, excluded_ids=answered).select()
        if question is None:
            db.session.rollback()
            return jsonify({"error": "Žiadne ďalšie otázky"}), 404
        prog.current_question_id = question.id

    payload = question_payload(question, **meta)
    db.session.commit()
    return jsonify(payload)


# ============================================================
# VYHODNOTENIE ODPOVEDE (predtest aj hlavný test)
# ============================================================
def _check_turn(student_id, test_type, question_id):
    """(turn, chybová odpoveď | None): je táto otázka práve na rade?"""
    turn = get_turn(student_id, test_type)
    status = turn.status_of(question_id)
    if status == "answered":
        row = (StudentAnswer.query
               .filter_by(student_id=student_id, question_id=question_id, test_type=test_type)
               .filter(StudentAnswer.test_session == turn.test_session)
               .order_by(StudentAnswer.id.desc()).first())
        # odpoveď už je uložená (dvojklik, obnovenie, druhá karta) - nezapisuj znova
        body = {"correct": bool(row and row.is_correct), "final": True, "already_answered": True}
        if row and not row.is_correct:
            body.update(show_solution=True, solution_code=get_question(question_id).output)
        return turn, jsonify(body)
    if status == "not_current":
        return turn, (jsonify({
            "error": "Táto otázka teraz nie je na rade.",
            "expected_question_id": turn.expected_question_id,
        }), 409)
    return turn, None


@api_bp.route("/test/answer", methods=["POST"])
@login_required
def evaluate_answer():
    student_id = current_user.id
    data = request.get_json(silent=True) or {}
    test_type = data.get("test_type", "main")
    code = data.get("code") or ""
    try:
        question_id = int(data.get("question_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Missing question ID"}), 400
    if test_type not in ("predtest", "main"):
        return jsonify({"error": "Neplatný typ testu"}), 400

    question = get_question(question_id)
    if question is None:
        return jsonify({"error": "Otázka neexistuje"}), 404
    category, solution_code = question.category, question.output

    _, error = _check_turn(student_id, test_type, question_id)
    if error:
        return error

    # Úloha, v ktorej je zadanie rovnaké ako riešenie (napr. len `print(...)`), nemá čo
    # dopĺňať - nezmenený kód je platná odpoveď (inak by na nej študent uviazol).
    starter_code = extract_starter_code(solution_code).strip()
    nothing_to_complete = starter_code == solution_code.strip()
    if not code.strip() or (code.strip() == starter_code and not nothing_to_complete):
        return jsonify({
            "correct": False,
            "message": "🛠️ Nezadal si žiadny kód. Skús niečo napísať a odoslať odpoveď."
        })

    # Beh kódu môže trvať sekundy -> DB spojenie sa medzitým vráti do poolu
    # (inak by pri veľa študentoch naraz došli spojenia).
    db.session.rollback()
    try:
        expected_out, expected_error = expected_output(question_id, solution_code)
        student_out, _ = capture_output(code)
    except RunnerUnavailable as e:
        # nie je to chyba študenta - nič sa nezapisuje, môže to skúsiť znova
        return jsonify({"correct": False, "message": f"⚠️ {e}"}), 503

    # --- zápis: serializovaný per študent, stav sa overí znova pod zámkom ---
    lock_student(student_id)
    turn, error = _check_turn(student_id, test_type, question_id)
    if error:
        return error

    if expected_error:
        # chyba referenčného riešenia nie je chyba študenta: otázka sa uzavrie bez opravy
        _record_final(student_id, turn, question_id, category, code, correct=False)
        return jsonify({
            "correct": False, "final": True, "student_output": student_out,
            "message": f"❌ Interná chyba v hodnotení otázky: {expected_error}",
        })

    correct = compare_outputs(student_out, expected_out)
    flow = QuestionFlow(get_retries_used(student_id, test_type, turn.test_session, question_id))
    flow.correct() if correct else flow.wrong()

    if flow.state == "retry":
        set_retries_used(student_id, test_type, turn.test_session, question_id, flow.retries_used)
        db.session.commit()
        return jsonify({
            "correct": False,
            "message": "🛠️ Výstup nie je správny. Skús to ešte raz opraviť!",
            "student_output": student_out,
        })

    _record_final(student_id, turn, question_id, category, code, correct)
    response = {"correct": correct, "final": True, "student_output": student_out}
    if not correct:
        response.update(show_solution=True, solution_code=solution_code)
    return jsonify(response)


def _record_final(student_id, turn, question_id, category, code, correct):
    """
    Jediné miesto, kde sa zapíše výsledok otázky: StudentAnswer + súhrn
    (a posun progresu hlavného testu) a výsledok sa odovzdá selektoru.
    Volá sa pod zámkom študenta; všetko sa zapíše jedným commitom.
    """
    update_summary(student_id, turn.test_type, turn.test_session, category, correct)
    db.session.add(StudentAnswer(
        student_id=student_id, question_id=question_id, answer_code=code,
        category=category, is_correct=correct,
        test_type=turn.test_type, test_session=turn.test_session,
    ))
    if turn.progress is not None:
        turn.progress.current_question_id = None

    if turn.test_type == "main":
        # zlyhanie selektora (súbor, ...) nesmie stratiť odpoveď študenta
        try:
            update_selector(student_id, turn.test_session, question_id, category, correct)
        except Exception:
            current_app.logger.exception("Aktualizácia selektora zlyhala")
    db.session.commit()


def update_summary(student_id, test_type, test_session, category, is_correct):
    if test_type == "predtest":
        return

    summary = TestSummary.query.filter_by(
        student_id=student_id, test_type=test_type,
        test_session=test_session, category=category,
    ).first()
    if not summary:
        summary = TestSummary(
            student_id=student_id, test_type=test_type, test_session=test_session,
            category=category, total_answers=0, correct_answers=0, incorrect_answers=0,
        )
        db.session.add(summary)

    summary.total_answers = (summary.total_answers or 0) + 1
    if is_correct:
        summary.correct_answers = (summary.correct_answers or 0) + 1
    else:
        summary.incorrect_answers = (summary.incorrect_answers or 0) + 1


@api_bp.route("/test/analysis", methods=["POST"])
@login_required
def test_analysis():
    student_id = current_user.id
    data = request.get_json(silent=True) or {}
    test_session = data.get("test_session")
    if not test_session:
        # bez zadanej session: posledný test študenta
        last = (TestProgress.query
                .filter_by(student_id=student_id, test_type="main")
                .order_by(TestProgress.id.desc()).first())
        test_session = last.test_session if last else None
    if not test_session:
        return jsonify({"error": "Missing test_session"}), 400

    total_questions, correct_answers = db.session.query(
        func.count(StudentAnswer.id),
        func.coalesce(func.sum(case((StudentAnswer.is_correct.is_(True), 1), else_=0)), 0),
    ).filter(
        StudentAnswer.student_id == student_id,
        StudentAnswer.test_type == "main",
        StudentAnswer.test_session == test_session,
    ).one()
    if not total_questions:
        return jsonify({"error": "No answers found"}), 404

    student_accuracy = round(correct_answers / total_questions * 100, 1)

    # Percentil: aký podiel študentov má horší celkový výsledok v hlavných testoch
    # (jedna agregačná query namiesto prechádzania všetkých odpovedí všetkých študentov).
    accuracies = [
        float(row[0]) for row in db.session.query(
            func.avg(case((StudentAnswer.is_correct.is_(True), 1.0), else_=0.0))
        ).filter(StudentAnswer.test_type == "main").group_by(StudentAnswer.student_id)
    ]
    below = sum(1 for acc in accuracies if acc < student_accuracy / 100)
    percentile = round(below / len(accuracies) * 100, 1) if accuracies else 0.0

    return jsonify({
        "correct_answers": int(correct_answers),
        "total_questions": total_questions,
        "student_accuracy": student_accuracy,
        "percentile_rank": percentile,
    })


# ============================================================
# DOTAZNÍK
# ============================================================
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
@login_required
def feedback():
    student_id = current_user.id
    answers = (request.get_json(silent=True) or {}).get("answers") or {}
    # každá odpoveď je jeden FeedbackResponse (upsert podľa qkey)
    updated = False
    for qkey, value in answers.items():
        value = str(value) if value is not None else None
        existing = FeedbackResponse.query.filter_by(student_id=student_id, qkey=qkey).first()
        if existing:
            existing.value = value
            updated = True
        else:
            db.session.add(FeedbackResponse(student_id=student_id, qkey=qkey, value=value))
    db.session.commit()

    msg = "Odpovede boli aktualizované. Ďakujeme!" if updated else "Ďakujeme za vyplnenie dotazníka!"
    return jsonify({"message": msg, "updated": updated})


@api_bp.route("/feedback/get", methods=["POST"])
@login_required
def get_feedback():
    responses = FeedbackResponse.query.filter_by(student_id=current_user.id).all()
    if not responses:
        return jsonify({"submitted": False, "feedback": {}})
    return jsonify({"submitted": True, "feedback": {r.qkey: r.value for r in responses}})


@api_bp.route("/feedback/check", methods=["POST"])
@login_required
def check_feedback_submitted():
    existing = FeedbackResponse.query.filter_by(student_id=current_user.id).first()
    return jsonify({"submitted": existing is not None})
