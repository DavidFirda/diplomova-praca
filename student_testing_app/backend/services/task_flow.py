# ============================================================
# AdaptPy - logika ÚLOH (samoštúdium personalizované POMDP).
#
# Tok jednej úlohy (server rozhoduje o všetkom, klient nič z toho neurčuje):
#
#   pokus 1            študent píše sám
#   nesprávny pokus    dostane spätnú väzbu "čo bolo zlé", kód musí opraviť sám
#   po 2. nesprávnom   sprístupní sa agent (nápovedy, nikdy nie riešenie)
#   5. nesprávny       úloha je NESPRÁVNA: ukáže sa riešenie a POMDP dostane zápornú odmenu
#   správne (1.-5.)    úloha je vyriešená, POMDP dostane pozorovanie "správne"
#
# Nezapočítané odoslania (prázdny kód, rovnaký kód ako minule, nedostupný runner)
# sa len zalogujú. Všetko ostatné (každý pokus, správy agenta, ...) ide do DB
# (task_*) aj do textového logu - pozri services/task_log.py.
# Nič sa nedrží v pamäti procesu, stav prežije reštart aj viac workerov.
# ============================================================
import json
from datetime import datetime, timezone

from flask import current_app

from algorithms.pomdp_task_selector import POMDPTaskSelector
from models import db, StudentAnswer
from models_ulohy import TaskAssignment, TaskAttempt, TaskEvent
from services import integrity as integrity_check
from services import task_agent
from services.capture_output import RunnerUnavailable, capture_output, compare_outputs, expected_output
from services.extract_starter_code import extract_starter_code
from services.task_feedback import build_feedback, feedback_payload
from services.task_log import log_event
from services.task_text import normalize_lang, tt
from services.test_flow import TEST_CATEGORIES, get_question, lock_student, question_payload

MAX_ATTEMPTS = 5            # po 5 nesprávnych pokusoch je úloha nesprávna a ukáže sa riešenie
AGENT_AFTER_WRONG = 2       # agent sa sprístupní po 2. nesprávnom pokuse
MAX_CODE_LEN = 20000
MAX_MESSAGE_LEN = 1000


def _now():
    return datetime.now(timezone.utc)


# ------------------------------------------------------------
# Úlohy študenta
# ------------------------------------------------------------
def open_assignment(student_id):
    return TaskAssignment.query.filter_by(student_id=student_id, status="open").first()


def last_attempt(assignment):
    return (TaskAttempt.query.filter_by(assignment_id=assignment.id)
            .order_by(TaskAttempt.attempt_no.desc()).first())


def _student_history(student_id):
    """[(kategória, správne?)] doterajších odpovedí z testov (na zahriatie POMDP)."""
    rows = (StudentAnswer.query.filter_by(student_id=student_id)
            .order_by(StudentAnswer.id).all())
    return [(r.category, r.is_correct) for r in rows]


def _seen_question_ids(student_id):
    """Otázky, ktoré už študent videl (predtest, testy aj úlohy) - nové úlohy sa z nich nevyberajú."""
    seen = {r[0] for r in db.session.query(StudentAnswer.question_id)
            .filter(StudentAnswer.student_id == student_id)}
    return seen | _task_question_ids(student_id)


def _task_question_ids(student_id):
    return {r[0] for r in db.session.query(TaskAssignment.question_id)
            .filter(TaskAssignment.student_id == student_id)}


def start_task(student_id):
    """
    (úloha, vytvorená_nová?). Rozpracovaná úloha pokračuje, inak POMDP vyberie novú.
    (None, False), ak už nie je z čoho vyberať. Volať pod zámkom študenta.
    """
    assignment = open_assignment(student_id)
    if assignment is not None:
        return assignment, False

    apply_pending_pomdp(student_id)

    selector = POMDPTaskSelector(
        student_id=int(student_id),
        categories=TEST_CATEGORIES,
        excluded_ids=list(_seen_question_ids(student_id)),
        fallback_excluded_ids=list(_task_question_ids(student_id)),
        history=_student_history(student_id),
    )
    question, level = selector.select()
    if question is None:
        return None, False

    assignment = TaskAssignment(
        student_id=student_id, question_id=question.id,
        category=question.category, strategy="pomdp",
    )
    db.session.add(assignment)
    db.session.flush()
    log_event(student_id, "task_assigned", assignment,
              payload={"category": question.category, "selection": level})
    return assignment, True


# ------------------------------------------------------------
# POMDP: výsledok úlohy -> pozorovanie + odmena
# ------------------------------------------------------------
def apply_pomdp(assignment):
    """Odovzdá výsledok skončenej úlohy POMDP (idempotentné - podľa pomdp_applied)."""
    if assignment.pomdp_applied or assignment.status not in ("solved", "failed"):
        return
    failed = assignment.status == "failed"
    try:
        selector = POMDPTaskSelector(
            student_id=int(assignment.student_id), categories=TEST_CATEGORIES,
            history=_student_history(assignment.student_id),
        )
        reward = selector.update_after_task(
            assignment.category, correct=bool(assignment.is_correct), failed=failed,
        )
    except Exception:
        # zlyhanie selektora (súbor, ...) nesmie stratiť výsledok študenta;
        # pomdp_applied ostane False a odovzdá sa pri ďalšej úlohe
        current_app.logger.exception("Aktualizácia POMDP po úlohe zlyhala")
        return
    assignment.reward = reward
    assignment.pomdp_applied = True
    log_event(assignment.student_id, "pomdp_update", assignment, payload={
        "category": assignment.category, "observation_correct": bool(assignment.is_correct),
        "failed_task": failed, "reward": reward,
    })
    db.session.commit()


def apply_pending_pomdp(student_id):
    """Dobehne výsledky skončených úloh, ktoré sa ešte nedostali do POMDP (napr. po páde procesu)."""
    pending = (TaskAssignment.query
               .filter(TaskAssignment.student_id == student_id,
                       TaskAssignment.status.in_(("solved", "failed")),
                       TaskAssignment.pomdp_applied.is_(False))
               .order_by(TaskAssignment.id).all())
    for assignment in pending:
        apply_pomdp(assignment)


# ------------------------------------------------------------
# Serializácia stavu pre klienta
# ------------------------------------------------------------
def state_fields(a):
    return {
        "status": a.status,
        "attempts_used": a.attempts_used,
        "wrong_attempts": a.wrong_attempts,
        "max_attempts": MAX_ATTEMPTS,
        "agent_available": a.status == "open" and a.wrong_attempts >= AGENT_AFTER_WRONG,
        "agent_after": AGENT_AFTER_WRONG,
        "hints_used": a.hints_used,
        "max_hints": task_agent.MAX_HINTS,
    }


def _feedback_of(attempt, lang):
    if attempt is None or not attempt.feedback_json:
        return None
    try:
        return feedback_payload(json.loads(attempt.feedback_json), lang)
    except ValueError:
        return None


def agent_history(assignment):
    events = (TaskEvent.query
              .filter_by(assignment_id=assignment.id, event_type="agent_message")
              .order_by(TaskEvent.id).all())
    history = []
    for e in events:
        try:
            p = json.loads(e.payload_json or "{}")
        except ValueError:
            continue
        history.append({"role": p.get("role"), "text": p.get("text", "")})
    return history


def assignment_payload(a, lang="sk"):
    """Všetko, čo klient potrebuje na zobrazenie úlohy (aj po obnovení stránky)."""
    question = get_question(a.question_id)
    attempt = last_attempt(a)
    data = {
        "id": a.id,
        "question": question_payload(question),
        **state_fields(a),
        "is_correct": a.is_correct,
        "solved_on_attempt": a.solved_on_attempt,
        "agent_opened": a.agent_opened,
        "last_code": attempt.code if attempt else None,     # po obnovení stránky pokračuje z posledného pokusu
        "last_output": attempt.student_output if attempt else None,
        "last_feedback": _feedback_of(attempt, lang) if attempt and not attempt.is_correct else None,
        "agent_history": agent_history(a) if a.agent_opened else [],
    }
    if a.solution_shown:
        data["solution_code"] = question.output
    return data


def task_stats(student_id):
    rows = TaskAssignment.query.filter_by(student_id=student_id).all()
    solved = [r for r in rows if r.status == "solved"]
    return {
        "total": sum(1 for r in rows if r.status in ("solved", "failed")),
        "solved": len(solved),
        "failed": sum(1 for r in rows if r.status == "failed"),
        "solved_first_try": sum(1 for r in solved if r.solved_on_attempt == 1),
    }


def topic_mastery(student_id):
    """
    Zvládnutie tém v % pre dashboard: odpovede z testov + výsledky úloh
    (vyriešená úloha = správne, nevyriešená = nesprávne). `percent` je None,
    kým o téme študent zatiaľ nemá žiadny výsledok.
    """
    correct = {c: 0 for c in TEST_CATEGORIES}
    total = {c: 0 for c in TEST_CATEGORIES}
    answers = (db.session.query(StudentAnswer.category, StudentAnswer.is_correct)
               .filter(StudentAnswer.student_id == student_id).all())
    for category, ok in answers:
        if category in total:
            total[category] += 1
            correct[category] += 1 if ok else 0
    tasks = (db.session.query(TaskAssignment.category, TaskAssignment.status)
             .filter(TaskAssignment.student_id == student_id,
                     TaskAssignment.status.in_(("solved", "failed"))).all())
    for category, status in tasks:
        if category in total:
            total[category] += 1
            correct[category] += 1 if status == "solved" else 0
    return [
        {"category": c, "answered": total[c],
         "percent": round(100 * correct[c] / total[c]) if total[c] else None}
        for c in TEST_CATEGORIES
    ]


def dashboard_summary(student_id):
    """Súhrn pre kartu Úlohy na dashboarde (rozpracovaná úloha, štatistika, zvládnutie tém)."""
    assignment = open_assignment(student_id)
    current = None
    if assignment is not None:
        question = get_question(assignment.question_id)
        current = {
            "question": question_payload(question),
            "category": assignment.category,
            "attempts_used": assignment.attempts_used,
            "wrong_attempts": assignment.wrong_attempts,
            "max_attempts": MAX_ATTEMPTS,
        }
    return {"stats": task_stats(student_id), "mastery": topic_mastery(student_id), "current": current}


# ------------------------------------------------------------
# Odoslanie pokusu
# ------------------------------------------------------------
def _normalize_code(code):
    return "\n".join(line.rstrip() for line in (code or "").strip().splitlines())


def _rejection(a, question, code):
    """Dôvod, prečo sa odoslanie nezapočíta ako pokus (alebo None)."""
    solution = question.output or ""
    starter = extract_starter_code(solution).strip()
    nothing_to_complete = starter == solution.strip()
    if not code.strip() or (code.strip() == starter and not nothing_to_complete):
        return "empty"
    previous = last_attempt(a)
    if previous is not None and _normalize_code(previous.code) == _normalize_code(code):
        return "duplicate"
    return None


def _rejected_response(student_id, a, code, reason, lang, status=200, message=None):
    log_event(student_id, "submission_rejected", a, payload={"reason": reason},
              file_extra={"code": code})
    db.session.commit()
    return status, {
        "correct": False, "counted": False, "reason": reason,
        "message": message or tt(lang, f"reject.{reason}"), **state_fields(a),
    }


def _finished_response(a, lang):
    """Odpoveď pre už uzavretú úlohu (dvojklik, druhá karta, obnovenie)."""
    attempt = last_attempt(a)
    body = {
        "correct": bool(a.is_correct), "final": True, "counted": False, "already_finished": True,
        "student_output": attempt.student_output if attempt else "",
        "feedback": _feedback_of(attempt, lang) if attempt and not attempt.is_correct else None,
        **state_fields(a),
    }
    if a.solution_shown:
        body["solution_code"] = get_question(a.question_id).output
    return 200, body


def submit_attempt(student_id, assignment_id, code, lang="sk", integrity=None):
    """(http_status, telo odpovede). Jediné miesto, kde vzniká pokus a mení sa stav úlohy.
    `integrity` = metriky písania z editora (kontrola originality, services/integrity.py)."""
    lang = normalize_lang(lang)
    code = code or ""
    if len(code) > MAX_CODE_LEN:
        return 400, {"error": f"Kód je príliš dlhý (max {MAX_CODE_LEN} znakov)."}

    a = db.session.get(TaskAssignment, assignment_id)
    if a is None or a.student_id != student_id:
        return 404, {"error": "Úloha neexistuje."}
    if a.status != "open":
        return _finished_response(a, lang)

    question = get_question(a.question_id)
    reason = _rejection(a, question, code)
    if reason:
        return _rejected_response(student_id, a, code, reason, lang)

    # Kontrola originality: podozrivé písanie -> študent najprv potvrdí, čia je to práca.
    # Kým nepotvrdí, kód sa nespustí a pokus sa nezapočíta.
    verdict, integrity_record = integrity_check.check(code, integrity)
    if verdict == "confirm":
        log_event(student_id, "integrity_confirmation_required", a,
                  payload={"reasons": integrity_record}, file_extra={"code": code})
        db.session.commit()
        return 200, integrity_check.confirm_response(integrity_record, state_fields(a))

    # Beh kódu môže trvať sekundy -> DB spojenie sa medzitým vráti do poolu.
    question_id, solution_code = question.id, question.output
    db.session.rollback()
    try:
        expected_out, expected_error = expected_output(question_id, solution_code)
        student_out, student_err = capture_output(code)
    except RunnerUnavailable as e:
        # nie je to chyba študenta - pokus sa nezapočíta, môže to skúsiť znova
        a = db.session.get(TaskAssignment, assignment_id)
        return _rejected_response(student_id, a, code, "runner_unavailable", lang,
                                  status=503, message=str(e))

    # --- zápis: serializovaný per študent, stav sa overí znova pod zámkom ---
    lock_student(student_id)
    a = db.session.get(TaskAssignment, assignment_id)
    if a.status != "open":
        return _finished_response(a, lang)
    question = get_question(a.question_id)
    reason = _rejection(a, question, code)         # súbežný dvojklik: druhý je už "duplicate"
    if reason:
        return _rejected_response(student_id, a, code, reason, lang)

    now = _now()
    if expected_error:
        # chyba referenčného riešenia nie je chyba študenta: úloha sa zruší bez dopadu na POMDP
        a.status, a.finished_at, a.pomdp_applied = "void", now, True
        log_event(student_id, "task_void", a,
                  payload={"reason": "reference_solution_error", "error": str(expected_error)[:500]},
                  file_extra={"code": code})
        db.session.commit()
        return 200, {"correct": False, "final": True, "counted": False, "void": True,
                     "message": tt(lang, "void"), **state_fields(a)}

    correct = student_err is None and compare_outputs(student_out, expected_out)
    feedback = None if correct else build_feedback(student_out, student_err, expected_out)

    attempt_no = a.attempts_used + 1
    db.session.add(TaskAttempt(
        assignment_id=a.id, student_id=student_id, question_id=a.question_id,
        attempt_no=attempt_no, code=code, is_correct=correct,
        student_output=student_out, error=student_err,
        feedback_kind=feedback["kind"] if feedback else None,
        feedback_json=json.dumps(feedback, ensure_ascii=False) if feedback else None,
        integrity_json=integrity_check.dumps(integrity_record),
        integrity_flag=verdict == "flagged",
        created_at=now,
    ))
    a.attempts_used = attempt_no

    agent_unlocked_now = False
    finished = False
    if correct:
        a.status, a.is_correct, a.solved_on_attempt, a.finished_at = "solved", True, attempt_no, now
        finished = True
    else:
        a.wrong_attempts += 1
        agent_unlocked_now = a.wrong_attempts == AGENT_AFTER_WRONG
        if a.wrong_attempts >= MAX_ATTEMPTS:
            a.status, a.is_correct, a.solution_shown, a.finished_at = "failed", False, True, now
            finished = True

    log_event(student_id, "attempt_submitted", a, payload={
        "attempt_no": attempt_no, "is_correct": correct,
        "wrong_attempts": a.wrong_attempts,
        "feedback_kind": feedback["kind"] if feedback else None,
        "feedback_params": feedback["params"] if feedback else None,
    }, file_extra={"code": code, "student_output": student_out, "error": student_err})
    if verdict == "flagged":
        log_event(student_id, "integrity_flagged", a, payload={
            "attempt_no": attempt_no, "reasons": integrity_record["reasons"],
            "confirmation": integrity_record["confirmation"],
        })
    if agent_unlocked_now:
        log_event(student_id, "agent_unlocked", a, payload={"after_wrong_attempts": a.wrong_attempts})
    if a.status == "failed":
        log_event(student_id, "solution_shown", a, payload={"after_wrong_attempts": a.wrong_attempts},
                  file_extra={"solution_code": solution_code})
    if finished:
        log_event(student_id, "task_finished", a, payload={
            "status": a.status, "is_correct": a.is_correct, "attempts_used": a.attempts_used,
            "solved_on_attempt": a.solved_on_attempt, "hints_used": a.hints_used,
            "agent_opened": a.agent_opened,
        })
    db.session.commit()

    if finished:
        apply_pomdp(a)

    body = {
        "correct": correct, "final": finished, "counted": True, "attempt_no": attempt_no,
        "student_output": student_out,
        "feedback": feedback_payload(feedback, lang),
        "agent_unlocked_now": agent_unlocked_now,
        **state_fields(a),
    }
    if a.solution_shown:
        body["solution_code"] = solution_code
    return 200, body


# ------------------------------------------------------------
# Agent
# ------------------------------------------------------------
def agent_chat(student_id, assignment_id, intent=None, message=None, code="", lang="sk"):
    """(http_status, telo odpovede). Agent sa sprístupní po AGENT_AFTER_WRONG nesprávnych pokusoch."""
    lang = normalize_lang(lang)
    message = (message or "").strip()[:MAX_MESSAGE_LEN]
    code = (code or "")[:MAX_CODE_LEN]

    lock_student(student_id)
    a = db.session.get(TaskAssignment, assignment_id)
    if a is None or a.student_id != student_id:
        return 404, {"error": "Úloha neexistuje."}
    if a.status != "open":
        return 409, {"error": tt(lang, "agent.closed")}
    if a.wrong_attempts < AGENT_AFTER_WRONG:
        return 403, {"error": "Agent sa sprístupní až po druhej nesprávnej odpovedi.",
                     "agent_available": False}

    question = get_question(a.question_id)
    already_opened = a.agent_opened
    if not already_opened:
        a.agent_opened = True
        log_event(student_id, "agent_opened", a, payload={"wrong_attempts": a.wrong_attempts})

    if intent == "open" and already_opened:
        # pozdrav sa zalogoval pri prvom otvorení; opätovné otvorenie nič nezapisuje
        return 200, {"reply": task_agent.greeting(lang), "intent": "open", "hint_level": None,
                     **state_fields(a)}

    if intent not in ("open", "explain", "hint"):
        intent = task_agent.intent_from_message(message) if message else "hint"

    if message:
        log_event(student_id, "agent_message", a,
                  payload={"role": "student", "text": message, "intent": intent})

    if intent == "open":
        result = {"text": task_agent.greeting(lang), "intent": "open", "hint_level": None}
    else:
        result = task_agent.reply(question, a, last_attempt(a), code, intent, lang)

    log_event(student_id, "agent_message", a, payload={
        "role": "agent", "text": result["text"], "intent": result["intent"],
        "hint_level": result["hint_level"],
    })
    db.session.commit()
    return 200, {
        "reply": result["text"], "intent": result["intent"], "hint_level": result["hint_level"],
        **state_fields(a),
    }
