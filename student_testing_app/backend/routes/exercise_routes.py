# ============================================================
# AdaptPy - CVIČENIA (študentská časť).  Prefix: /api/exercises
#
# Kód sa spúšťa v IZOLOVANOM sandboxe (kontajner 'runner'), NIE v procese
# backendu. Perzistencia premenných: klient posiela `prelude` = kód všetkých
# buniek nad aktuálnou (v poradí, ako sú na obrazovke).
#
# Časový limit: každé cvičenie môže mať vlastný `run_timeout` (s); ak ho nemá,
# runner použije svoj default. Limit sa posiela runneru a vracia sa aj do UI.
# ============================================================
import json
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, session, send_file

from models import db, Student
from models_exercises import Exercise, ExerciseProgress
from services.exercise_store import exercise_path, asset_path, source_dir_rel_for_slug
from services.code_runner import execute as run_code

exercise_bp = Blueprint("exercise", __name__)


def _current_student():
    sid = session.get("student_id")
    if not sid:
        return None
    return Student.query.get(sid)


def _get_progress(student_id, exercise_id):
    p = ExerciseProgress.query.filter_by(student_id=student_id, exercise_id=exercise_id).first()
    if p is None:
        p = ExerciseProgress(
            student_id=student_id, exercise_id=exercise_id,
            done_cells_json="[]", answers_json="{}", percent=0, status="not_started",
        )
        db.session.add(p)
        db.session.commit()
    return p


def _done_cells(progress):
    try:
        return set(json.loads(progress.done_cells_json or "[]"))
    except Exception:
        return set()


def _answers(progress):
    try:
        return json.loads(progress.answers_json or "{}") or {}
    except Exception:
        return {}


def _recalc_percent(exercise, done):
    total = max(1, exercise.code_cells or 0)
    pct = int(round(100 * len(done) / total)) if exercise.code_cells else 0
    return min(100, max(0, pct))


def _load_notebook_json(exercise):
    with open(exercise_path(exercise.filename), "r", encoding="utf-8") as f:
        return json.load(f)


def _cell_timeout(cell):
    """Limit bunky (s) z metadata.adaptpy.timeout, alebo None."""
    try:
        v = ((cell.get("metadata") or {}).get("adaptpy") or {}).get("timeout")
        v = int(v)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def _timeout_for_cell(exercise, code_index):
    """Limit konkrétnej code bunky; ak nemá vlastný, platí limit cvičenia."""
    try:
        nb = _load_notebook_json(exercise)
        i = 0
        for c in nb.get("cells", []):
            if c.get("cell_type") == "code":
                if i == code_index:
                    t = _cell_timeout(c)
                    if t:
                        return t
                    break
                i += 1
    except Exception:
        pass
    return exercise.run_timeout or None


def _cell_source(cell):
    src = cell.get("source", "")
    return "".join(src) if isinstance(src, list) else (src or "")


def _prev_completed(student_id, exercise):
    prev = (
        Exercise.query.filter(
            Exercise.published == True,  # noqa: E712
            (Exercise.order_index < exercise.order_index)
            | ((Exercise.order_index == exercise.order_index) & (Exercise.id < exercise.id)),
        )
        .order_by(Exercise.order_index.desc(), Exercise.id.desc())
        .first()
    )
    if prev is None:
        return True
    p = ExerciseProgress.query.filter_by(student_id=student_id, exercise_id=prev.id).first()
    return bool(p and p.status == "completed")


# ---------- zoznam cvičení ----------
@exercise_bp.route("", methods=["GET"])
@exercise_bp.route("/", methods=["GET"])
def list_exercises():
    student = _current_student()
    if not student:
        return jsonify({"error": "Nie si prihlásený."}), 401

    exercises = (
        Exercise.query.filter_by(published=True)
        .order_by(Exercise.order_index, Exercise.id).all()
    )
    result = []
    prev_completed = True
    for ex in exercises:
        p = _get_progress(student.id, ex.id)
        unlocked = bool(ex.accessible and prev_completed)
        lock_reason = None
        if not unlocked:
            lock_reason = "not_accessible" if not ex.accessible else "prev_incomplete"
        try:
            topics = json.loads(ex.topics_json or "[]")
        except Exception:
            topics = []
        result.append({
            "id": ex.id, "slug": ex.slug, "order_index": ex.order_index,
            "title_sk": ex.title_sk, "title_en": ex.title_en,
            "description_sk": ex.description_sk, "description_en": ex.description_en,
            "topics": topics, "code_cells": ex.code_cells,
            "percent": p.percent, "status": p.status, "accessible": ex.accessible,
            "locked": not unlocked, "lock_reason": lock_reason,
        })
        prev_completed = (p.status == "completed")
    return jsonify({"exercises": result})


# ---------- detail + bunky + uložené odpovede ----------
@exercise_bp.route("/<int:ex_id>", methods=["GET"])
def get_exercise(ex_id):
    student = _current_student()
    if not student:
        return jsonify({"error": "Nie si prihlásený."}), 401
    ex = Exercise.query.get(ex_id)
    if not ex or not ex.published:
        return jsonify({"error": "Cvičenie neexistuje."}), 404
    if not ex.accessible:
        return jsonify({"error": "Cvičenie zatiaľ nie je sprístupnené.",
                        "locked": True, "lock_reason": "not_accessible"}), 403
    if not _prev_completed(student.id, ex):
        return jsonify({"error": "Najprv dokonči predchádzajúce cvičenie.",
                        "locked": True, "lock_reason": "prev_incomplete"}), 403
    try:
        nb = _load_notebook_json(ex)
    except Exception:
        return jsonify({"error": "Notebook sa nepodarilo načítať."}), 500

    p = _get_progress(student.id, ex.id)
    done = _done_cells(p)
    answers = _answers(p)

    cells = []
    code_index = 0
    for c in nb.get("cells", []):
        ctype = c.get("cell_type")
        if ctype == "markdown":
            cells.append({"type": "markdown", "source": _cell_source(c)})
        elif ctype == "code":
            cells.append({
                "type": "code", "code_index": code_index,
                "source": _cell_source(c),
                "timeout": _cell_timeout(c),
                "saved": answers.get(str(code_index)),
                "done": code_index in done,
            })
            code_index += 1

    try:
        topics = json.loads(ex.topics_json or "[]")
    except Exception:
        topics = []

    return jsonify({
        "id": ex.id, "slug": ex.slug,
        "title_sk": ex.title_sk, "title_en": ex.title_en,
        "description_sk": ex.description_sk, "description_en": ex.description_en,
        "topics": topics, "code_cells": ex.code_cells, "cells": cells,
        "run_timeout": ex.run_timeout,          # limit cvičenia (s) pre UI odpočet (None = default)
        "progress": {"percent": p.percent, "status": p.status, "done_cells": sorted(done)},
    })


# ---------- sprievodný súbor (obrázok/dataset) ----------
@exercise_bp.route("/<int:ex_id>/asset/<path:relpath>", methods=["GET"])
def get_asset(ex_id, relpath):
    student = _current_student()
    if not student:
        return jsonify({"error": "Nie si prihlásený."}), 401
    ex = Exercise.query.get(ex_id)
    if not ex or not ex.published or not ex.accessible:
        return jsonify({"error": "Nedostupné."}), 403
    full = asset_path(relpath)
    if not full:
        return jsonify({"error": "Súbor sa nenašiel."}), 404
    return send_file(full)


# ---------- spustenie bunky (v sandboxe) ----------
@exercise_bp.route("/<int:ex_id>/run", methods=["POST"])
def run_exercise_cell(ex_id):
    student = _current_student()
    if not student:
        return jsonify({"error": "Nie si prihlásený."}), 401
    ex = Exercise.query.get(ex_id)
    if not ex or not ex.published or not ex.accessible:
        return jsonify({"error": "Cvičenie nie je dostupné."}), 403
    if not _prev_completed(student.id, ex):
        return jsonify({"error": "Cvičenie je zamknuté."}), 403

    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    code_index = data.get("code_index")
    prelude = data.get("prelude", "")
    if code_index is None:
        return jsonify({"error": "Chýba code_index."}), 400

    # spustenie v izolovanom sandboxe (runner), s per-cvičenie timeoutom
    workrel = source_dir_rel_for_slug(ex.slug)
    try:
        ci = int(code_index)
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatný code_index."}), 400
    cell_to = _timeout_for_cell(ex, ci) if 0 <= ci < (ex.code_cells or 0) else (ex.run_timeout or None)
    res = run_code(prelude, code, workrel, timeout=cell_to)

    is_real = (0 <= ci < (ex.code_cells or 0))

    p = _get_progress(student.id, ex.id)
    done = _done_cells(p)
    if res.get("ok") and is_real:
        done.add(ci)
    p.done_cells_json = json.dumps(sorted(done))

    if is_real:
        answers = _answers(p)
        answers[str(ci)] = code
        p.answers_json = json.dumps(answers, ensure_ascii=False)

    p.percent = _recalc_percent(ex, done)
    if p.status == "not_started" and (res.get("ok") or done):
        p.status = "in_progress"
    db.session.commit()

    return jsonify({
        "ok": res.get("ok", False),
        "output": res.get("output", ""),
        "error": res.get("error"),
        "images": res.get("images", []),
        "timed_out": res.get("timed_out", False),
        "timeout": res.get("timeout"),
        "percent": p.percent,
        "done_cells": sorted(done),
        "status": p.status,
    })


# ---------- priebežné uloženie odpovede ----------
@exercise_bp.route("/<int:ex_id>/save", methods=["POST"])
def save_answer(ex_id):
    student = _current_student()
    if not student:
        return jsonify({"error": "Nie si prihlásený."}), 401
    ex = Exercise.query.get(ex_id)
    if not ex or not ex.published or not ex.accessible:
        return jsonify({"error": "Cvičenie nie je dostupné."}), 403
    data = request.get_json(silent=True) or {}
    code_index = data.get("code_index")
    code = data.get("code", "")
    if code_index is None:
        return jsonify({"error": "Chýba code_index."}), 400
    ci = int(code_index)
    if not (0 <= ci < (ex.code_cells or 0)):
        return jsonify({"ok": True})
    p = _get_progress(student.id, ex.id)
    answers = _answers(p)
    answers[str(ci)] = code
    p.answers_json = json.dumps(answers, ensure_ascii=False)
    db.session.commit()
    return jsonify({"ok": True})


# ---------- reset (už netreba živý namespace) ----------
@exercise_bp.route("/<int:ex_id>/reset", methods=["POST"])
def reset_exercise(ex_id):
    if not _current_student():
        return jsonify({"error": "Nie si prihlásený."}), 401
    return jsonify({"ok": True})


# ---------- "Dokončil som" ----------
@exercise_bp.route("/<int:ex_id>/complete", methods=["POST"])
def complete_exercise(ex_id):
    student = _current_student()
    if not student:
        return jsonify({"error": "Nie si prihlásený."}), 401
    ex = Exercise.query.get(ex_id)
    if not ex or not ex.published:
        return jsonify({"error": "Cvičenie neexistuje."}), 404
    p = _get_progress(student.id, ex.id)
    if ex.code_cells and p.percent < 100:
        return jsonify({"error": "Najprv spusti všetky bunky bez chyby.", "percent": p.percent}), 400
    p.status = "completed"
    p.percent = 100
    p.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"ok": True, "status": p.status, "percent": p.percent})


# ---------- stiahnutie .ipynb ----------
@exercise_bp.route("/<int:ex_id>/download", methods=["GET"])
def download_exercise(ex_id):
    student = _current_student()
    if not student:
        return jsonify({"error": "Nie si prihlásený."}), 401
    ex = Exercise.query.get(ex_id)
    if not ex or not ex.published or not ex.accessible:
        return jsonify({"error": "Cvičenie nie je dostupné."}), 403
    if not _prev_completed(student.id, ex):
        return jsonify({"error": "Cvičenie je zamknuté."}), 403
    return send_file(
        exercise_path(ex.filename), as_attachment=True,
        download_name=ex.filename, mimetype="application/x-ipynb+json",
    )
