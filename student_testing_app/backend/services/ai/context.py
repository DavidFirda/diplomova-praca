# ============================================================
# AdaptPy - kontext pre asistenta (čo model "vidí") v jednotlivých režimoch.
#
# Dashboard: návod k aplikácii + údaje prihláseného študenta + povolené odkazy.
#            Žiadny kód aplikácie, nič z admin rozhrania (model to nemá odkiaľ vziať).
# Cvičenie:  zadanie cvičenia (text sekcie z notebooku), bunky s kódom, aktuálny kód
#            študenta a výstup bunky. Zadanie sa číta zo servera, nie od klienta.
# Úloha:     zadanie, vstup, posledný pokus (kód, výstup, spätná väzba), referenčné
#            riešenie (len pre model; strážca kontroluje, aby ho neprezradil).
# ============================================================
import json
import re

from sqlalchemy import case, func

from models import db, StudentAnswer
from models_ai import CourseMaterial
from models_exercises import Exercise, ExerciseProgress
from models_ulohy import TaskAssignment
from services import task_flow
from services.extract_starter_code import extract_starter_code
from services.settings import questionnaire_published, sections_state
from services.task_feedback import feedback_payload
from services.test_flow import get_question, pretest_state

MAX_CODE = 6000
MAX_SECTION = 3500
MAX_OUTPUT = 1500


class ContextError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _cut(text, n):
    text = text or ""
    return text if len(text) <= n else text[:n] + "\n…(skrátené)"


def _cell_source(cell):
    src = cell.get("source", "")
    return "".join(src) if isinstance(src, list) else (src or "")


# ------------------------------------------------------------
# Materiály viditeľné pre študentov (odkazy z asistenta)
# ------------------------------------------------------------
def visible_materials():
    return (CourseMaterial.query.filter(CourseMaterial.visible_to_students.is_(True))
            .order_by(CourseMaterial.kind.desc(), CourseMaterial.lecture_no, CourseMaterial.position,
                      CourseMaterial.id).all())


def material_links():
    return [f"/materialy#m-{m.id}" for m in visible_materials()]


# ------------------------------------------------------------
# Cvičenia študenta (dashboard + kontrola prístupu)
# ------------------------------------------------------------
def exercise_overview(student_id, lang="sk"):
    exercises = (Exercise.query.filter_by(published=True)
                 .order_by(Exercise.order_index, Exercise.id).all())
    progress = {p.exercise_id: p for p in ExerciseProgress.query.filter_by(student_id=student_id).all()}
    out, prev_completed = [], True
    for ex in exercises:
        p = progress.get(ex.id)
        status = p.status if p else "not_started"
        unlocked = bool(ex.accessible and prev_completed)
        try:
            topics = json.loads(ex.topics_json or "[]")
        except ValueError:
            topics = []
        out.append({
            "id": ex.id,
            "title": (ex.title_en or ex.title_sk) if lang == "en" else (ex.title_sk or ex.title_en),
            "topics": topics, "status": status, "percent": p.percent if p else 0, "unlocked": unlocked,
        })
        prev_completed = status == "completed"
    return out


def exercise_unlocked(student_id, exercise_id):
    return any(e["id"] == exercise_id and e["unlocked"] for e in exercise_overview(student_id))


# ------------------------------------------------------------
# DASHBOARD
# ------------------------------------------------------------
def dashboard_context(student, lang="sk"):
    """-> (text kontextu, povolené odkazy, metadáta do logu)."""
    sid = student.id
    pt = pretest_state(sid)
    sections = sections_state()
    total, correct = db.session.query(
        func.count(StudentAnswer.id),
        func.coalesce(func.sum(case((StudentAnswer.is_correct.is_(True), 1), else_=0)), 0),
    ).filter(StudentAnswer.student_id == sid).one()
    main_sessions = db.session.query(func.count(func.distinct(StudentAnswer.test_session))).filter(
        StudentAnswer.student_id == sid, StudentAnswer.test_type == "main",
        StudentAnswer.test_session.isnot(None)).scalar() or 0

    data = {
        "name": student.name,
        "pretest": {"done": pt["done"], "answered": pt["answered"], "total": pt["total"]},
        "tests_enabled": sections.get("tests", True),
        "main_tests_taken": int(main_sessions),
        "all_answers": {"total": int(total), "correct": int(correct),
                        "accuracy_percent": round(correct / total * 100, 1) if total else None},
    }
    if pt["done"]:
        summary = task_flow.dashboard_summary(sid)
        data["tasks"] = {
            "stats": summary["stats"],
            "topic_mastery_percent": {m["category"]: m["percent"] for m in summary["mastery"]
                                      if m["percent"] is not None},
            "topics_without_results": [m["category"] for m in summary["mastery"] if m["percent"] is None],
            "task_in_progress": ({"category": summary["current"]["category"],
                                  "attempts_used": summary["current"]["attempts_used"],
                                  "max_attempts": summary["current"]["max_attempts"]}
                                 if summary["current"] else None),
        }
    exercises = exercise_overview(sid, lang)
    data["exercises"] = [{k: e[k] for k in ("id", "title", "topics", "status", "percent", "unlocked")}
                         for e in exercises]
    mats = visible_materials()
    data["materials_available"] = [
        {"id": m.id, "type": "lecture" if m.kind == "prednaska" else "book",
         "lecture_no": m.lecture_no, "title": m.title} for m in mats]
    data["questionnaire_published"] = questionnaire_published()

    links = ["/dashboard", "/cvicenia", "/analyza", "/profile", "/change-password", "/feedback-form"]
    if not pt["done"]:
        links.append("/predtest")
    else:
        links.append("/ulohy")
        if data["tests_enabled"]:
            links.append("/hlavnytest")
    if data["questionnaire_published"]:
        links.append("/feedback")
    links += [f"/cvicenie?id={e['id']}" for e in exercises if e["unlocked"]]
    if mats:
        links.append("/materialy")
        links += [f"/materialy#m-{m.id}" for m in mats]

    text = (
        f"APP GUIDE:\n{_app_guide(lang)}\n\n"
        f"STUDENT DATA (JSON, only this student):\n{json.dumps(data, ensure_ascii=False, indent=1)}\n\n"
        "ALLOWED LINKS (use only these):\n" + "\n".join(links)
    )
    return text, links, {"links": len(links)}


def _app_guide(lang):
    from services.ai.prompts import app_guide
    return app_guide(lang)


# ------------------------------------------------------------
# CVIČENIE
# ------------------------------------------------------------
def _load_notebook(ex):
    from services.exercise_store import exercise_path
    with open(exercise_path(ex.filename), encoding="utf-8") as f:
        return json.load(f)


def exercise_context(student, exercise_id, cell_index=None, cell_code=None, cell_output=None,
                     lang="sk"):
    """
    -> dict: text (pre model), retrieval_hint (názov sekcie), target_functions (funkcie zo zadania
    na kontrolu strážcom), cells (zoznam buniek pre UI), meta (do logu).
    """
    ex = db.session.get(Exercise, exercise_id)
    if ex is None or not ex.published:
        raise ContextError("Cvičenie neexistuje.", 404)
    if not exercise_unlocked(student.id, ex.id):
        raise ContextError("Cvičenie je zamknuté.", 403)
    try:
        nb = _load_notebook(ex)
    except (OSError, ValueError):
        raise ContextError("Notebook sa nepodarilo načítať.", 500)

    title = (ex.title_en or ex.title_sk) if lang == "en" else (ex.title_sk or ex.title_en)
    cells, code_i, last_md, section_for = [], 0, "", {}
    intro = ""
    for c in nb.get("cells", []):
        src = _cell_source(c)
        if c.get("cell_type") == "markdown":
            if not intro:
                intro = src
            last_md = src
        elif c.get("cell_type") == "code":
            cells.append({"index": code_i, "number": code_i + 1, "starter": src})
            section_for[code_i] = last_md
            code_i += 1

    target_functions = set()
    for cell in cells:
        target_functions |= set(re.findall(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", cell["starter"], re.M))

    active = None
    if isinstance(cell_index, int) and 0 <= cell_index < len(cells):
        active = cells[cell_index]
    section = section_for.get(cell_index, "") if active else ""

    cells_list = "\n".join(
        f"- cell {c['number']}: " + (_first_line(c["starter"]) or "(empty)") for c in cells)
    parts = [f"EXERCISE: {title}", f"INTRODUCTION:\n{_cut(intro, 1200)}"]
    if active:
        parts.append(f"CURRENT TASK SECTION (text above cell {active['number']}):\n{_cut(section, MAX_SECTION)}")
        parts.append(f"STARTER CODE OF CELL {active['number']} (given by the teacher):\n"
                     f"```python\n{_cut(active['starter'], 2000)}\n```")
        if cell_code is not None:
            parts.append(f"STUDENT'S CURRENT CODE IN CELL {active['number']}:\n```python\n{_cut(cell_code, MAX_CODE)}\n```")
        if cell_output:
            parts.append(f"LAST OUTPUT / ERROR OF THIS CELL:\n```\n{_cut(cell_output, MAX_OUTPUT)}\n```")
    elif cell_code:
        parts.append("The student is working in their own scratch cell (not part of the exercise):\n"
                     f"```python\n{_cut(cell_code, MAX_CODE)}\n```")
        if cell_output:
            parts.append(f"LAST OUTPUT / ERROR OF THE SCRATCH CELL:\n```\n{_cut(cell_output, MAX_OUTPUT)}\n```")
    else:
        parts.append("The student has not selected any cell yet.")
    parts.append(f"CODE CELLS OF THE NOTEBOOK (numbers the student sees):\n{cells_list}")

    heading = ""
    m = re.search(r"^#{1,4}\s+(.+)$", section or "", re.M)
    if m:
        heading = m.group(1).strip()
    return {
        "text": "\n\n".join(parts),
        "retrieval_hint": " ".join(filter(None, [heading, _first_line(active["starter"]) if active else ""])),
        "target_functions": sorted(target_functions),
        "starter": active["starter"] if active else "",
        "meta": {"exercise_id": ex.id, "cell": active["number"] if active else None,
                 "code_len": len(cell_code or "")},
    }


def _first_line(code):
    for line in (code or "").splitlines():
        if line.strip() and not line.strip().startswith("#"):
            return line.strip()[:100]
    return ""


# ------------------------------------------------------------
# ÚLOHA
# ------------------------------------------------------------
def task_context(student, assignment_id, current_code=None, lang="sk"):
    a = db.session.get(TaskAssignment, assignment_id)
    if a is None or a.student_id != student.id:
        raise ContextError("Úloha neexistuje.", 404)
    q = get_question(a.question_id)
    instruction = (q.instruction_sk or q.instruction) if lang == "sk" else (q.instruction or q.instruction_sk)
    attempt = task_flow.last_attempt(a)
    feedback = None
    if attempt is not None and attempt.feedback_json and not attempt.is_correct:
        try:
            feedback = feedback_payload(json.loads(attempt.feedback_json), lang)
        except ValueError:
            feedback = None

    parts = [
        f"TASK (category: {q.category}):\n{instruction}",
        f"TASK INPUT:\n{q.input_data or 'None'}",
        f"STARTER CODE SHOWN TO THE STUDENT:\n```python\n{extract_starter_code(q.output or '')}\n```",
        f"STATE: attempt {a.attempts_used} of {task_flow.MAX_ATTEMPTS} used, wrong attempts: {a.wrong_attempts}, "
        f"hints used: {a.hints_used} of 3, status: {a.status}.",
    ]
    if attempt is not None:
        parts.append(f"STUDENT'S LAST SUBMITTED ATTEMPT (#{attempt.attempt_no}, "
                     f"{'correct' if attempt.is_correct else 'wrong'}):\n```python\n{_cut(attempt.code, MAX_CODE)}\n```")
        if attempt.error:
            parts.append(f"ERROR OF THE LAST ATTEMPT:\n```\n{_cut(attempt.error, MAX_OUTPUT)}\n```")
        elif attempt.student_output:
            parts.append(f"OUTPUT OF THE LAST ATTEMPT:\n```\n{_cut(attempt.student_output, MAX_OUTPUT)}\n```")
        if feedback and feedback.get("message"):
            parts.append(f"AUTOMATIC FEEDBACK THE STUDENT SAW:\n{feedback['message']}")
    else:
        parts.append("The student has not submitted any attempt yet.")
    if current_code is not None and (attempt is None or current_code.strip() != (attempt.code or "").strip()):
        parts.append(f"STUDENT'S CURRENT CODE IN THE EDITOR (not submitted yet):\n```python\n"
                     f"{_cut(current_code, MAX_CODE)}\n```")
    parts.append("HIDDEN REFERENCE SOLUTION (never reveal, never quote, never write equivalent full code):\n"
                 f"```python\n{_cut(q.output, MAX_CODE)}\n```")
    return {
        "assignment": a,
        "question": q,
        "text": "\n\n".join(parts),
        "retrieval_query": f"{instruction}\n{q.category}",
        "reference": q.output or "",
        "starter": extract_starter_code(q.output or ""),
        "meta": {"assignment_id": a.id, "question_id": q.id, "attempts_used": a.attempts_used,
                 "wrong_attempts": a.wrong_attempts, "hints_used": a.hints_used,
                 "code_len": len(current_code or "")},
    }
