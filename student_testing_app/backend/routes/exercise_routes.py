# ============================================================
# AdaptPy - CVIČENIA (študentská časť).  Prefix: /api/exercises
#
# Autentifikácia cez session (session["student_id"]) - rovnako
# ako zvyšok appky.
#
# Odomykanie cvičenia (sekvenčné) = OBOJE naraz:
#   1) admin ho SPRÍSTUPNIL (accessible = True), a zároveň
#   2) PREDCHÁDZAJÚCE cvičenie (podľa poradia) je DOKONČENÉ.
# Prvé cvičenie nemá predchodcu, takže mu stačí byť sprístupnené.
# ============================================================
import json
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, session, send_file

from models import db, Student
from models_exercises import Exercise, ExerciseProgress
from services.exercise_store import exercise_path, asset_path, source_dir_for_slug
from services.run_notebook_cell import run_cell, reset_namespace

exercise_bp = Blueprint("exercise", __name__)


# ---------- pomocníci ----------
def _current_student():
    sid = session.get("student_id")
    if not sid:
        return None
    return Student.query.get(sid)


def _get_progress(student_id, exercise_id):
    p = ExerciseProgress.query.filter_by(
        student_id=student_id, exercise_id=exercise_id
    ).first()
    if p is None:
        p = ExerciseProgress(
            student_id=student_id, exercise_id=exercise_id,
            done_cells_json="[]", percent=0, status="not_started",
        )
        db.session.add(p)
        db.session.commit()
    return p


def _done_cells(progress):
    try:
        return set(json.loads(progress.done_cells_json or "[]"))
    except Exception:
        return set()


def _recalc_percent(exercise, done):
    total = max(1, exercise.code_cells or 0)
    pct = int(round(100 * len(done) / total)) if exercise.code_cells else 0
    return min(100, max(0, pct))


def _load_notebook_json(exercise):
    with open(exercise_path(exercise.filename), "r", encoding="utf-8") as f:
        return json.load(f)


def _cell_source(cell):
    src = cell.get("source", "")
    return "".join(src) if isinstance(src, list) else (src or "")


def _prev_completed(student_id, exercise):
    """True, ak je predchádzajúce publikované cvičenie dokončené (alebo neexistuje)."""
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


# ---------- zoznam cvičení pre študenta ----------
@exercise_bp.route("", methods=["GET"])
@exercise_bp.route("/", methods=["GET"])
def list_exercises():
    student = _current_student()
    if not student:
        return jsonify({"error": "Nie si prihlásený."}), 401

    exercises = (
        Exercise.query.filter_by(published=True)
        .order_by(Exercise.order_index, Exercise.id)
        .all()
    )

    result = []
    prev_completed = True
    for ex in exercises:
        p = _get_progress(student.id, ex.id)
        unlocked = bool(ex.accessible and prev_completed)
        lock_reason = None
        if not unlocked:
            if not ex.accessible:
                lock_reason = "not_accessible"
            elif not prev_completed:
                lock_reason = "prev_incomplete"

        try:
            topics = json.loads(ex.topics_json or "[]")
        except Exception:
            topics = []

        result.append({
            "id": ex.id,
            "slug": ex.slug,
            "order_index": ex.order_index,
            "title_sk": ex.title_sk, "title_en": ex.title_en,
            "description_sk": ex.description_sk, "description_en": ex.description_en,
            "topics": topics,
            "code_cells": ex.code_cells,
            "percent": p.percent,
            "status": p.status,
            "accessible": ex.accessible,
            "locked": not unlocked,
            "lock_reason": lock_reason,
        })

        prev_completed = (p.status == "completed")

    return jsonify({"exercises": result})


# ---------- detail + obsah notebooku (bunky) ----------
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

    cells = []
    code_index = 0
    for c in nb.get("cells", []):
        ctype = c.get("cell_type")
        if ctype == "markdown":
            cells.append({"type": "markdown", "source": _cell_source(c)})
        elif ctype == "code":
            cells.append({
                "type": "code",
                "code_index": code_index,
                "source": _cell_source(c),
                "done": code_index in done,
            })
            code_index += 1

    try:
        topics = json.loads(ex.topics_json or "[]")
    except Exception:
        topics = []

    return jsonify({
        "id": ex.id,
        "slug": ex.slug,
        "title_sk": ex.title_sk, "title_en": ex.title_en,
        "description_sk": ex.description_sk, "description_en": ex.description_en,
        "topics": topics,
        "code_cells": ex.code_cells,
        "cells": cells,
        "progress": {
            "percent": p.percent,
            "status": p.status,
            "done_cells": sorted(done),
        },
    })


# ---------- sprievodný súbor (obrázok/dataset) z notebooku ----------
@exercise_bp.route("/<int:ex_id>/asset/<path:relpath>", methods=["GET"])
def get_asset(ex_id, relpath):
    # prístup len prihlásenému študentovi a len k sprístupnenému cvičeniu
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


# ---------- spustenie code-bunky ----------
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
    if code_index is None:
        return jsonify({"error": "Chýba code_index."}), 400

    # pracovný priečinok cvičenia, aby kód našiel svoje dátové súbory
    workdir = source_dir_for_slug(ex.slug)
    res = run_cell(student.id, ex.id, code, workdir=workdir)

    p = _get_progress(student.id, ex.id)
    done = _done_cells(p)
    if res["ok"]:
        done.add(int(code_index))
    p.done_cells_json = json.dumps(sorted(done))
    p.percent = _recalc_percent(ex, done)
    if p.status == "not_started" and (res["ok"] or done):
        p.status = "in_progress"
    db.session.commit()

    return jsonify({
        "ok": res["ok"],
        "output": res["output"],
        "error": res["error"],
        "percent": p.percent,
        "done_cells": sorted(done),
        "status": p.status,
    })


# ---------- reset behu (spusti odznova) ----------
@exercise_bp.route("/<int:ex_id>/reset", methods=["POST"])
def reset_exercise(ex_id):
    student = _current_student()
    if not student:
        return jsonify({"error": "Nie si prihlásený."}), 401
    reset_namespace(student.id, ex_id)
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
        return jsonify({
            "error": "Najprv spusti všetky bunky bez chyby.",
            "percent": p.percent,
        }), 400

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
        exercise_path(ex.filename),
        as_attachment=True,
        download_name=ex.filename,
        mimetype="application/x-ipynb+json",
    )
