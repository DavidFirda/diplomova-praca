# ============================================================
# AdaptPy - CVIČENIA (admin časť).  Prefix: /api/admin/exercises
# ============================================================
import json
import os
from functools import wraps

from flask import Blueprint, request, jsonify, session

from models import db, Student
from models_exercises import Exercise, ExerciseProgress
from services.exercise_store import get_exercises_dir, exercise_path, is_notebook
from services import notebook_scan

admin_exercise_bp = Blueprint("admin_exercise", __name__)


def _current_student():
    sid = session.get("student_id")
    return Student.query.get(sid) if sid else None


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        student = _current_student()
        if not student:
            return jsonify({"error": "Nie si prihlásený."}), 401
        if (getattr(student, "role", "user") or "user") != "admin":
            return jsonify({"error": "Prístup len pre administrátora."}), 403
        return fn(*args, **kwargs)
    return wrapper


def _count_code_cells(nb):
    return sum(1 for c in nb.get("cells", []) if c.get("cell_type") == "code")


def _slug_from_filename(filename):
    return os.path.splitext(os.path.basename(filename))[0]


def _cell_source(cell):
    src = cell.get("source", "")
    return "".join(src) if isinstance(src, list) else (src or "")


def _load_notebook(ex):
    with open(exercise_path(ex.filename), "r", encoding="utf-8") as f:
        return json.load(f)


def _serialize(ex, with_stats=False):
    try:
        topics = json.loads(ex.topics_json or "[]")
    except Exception:
        topics = []
    data = {
        "id": ex.id, "slug": ex.slug, "filename": ex.filename,
        "order_index": ex.order_index,
        "title_sk": ex.title_sk, "title_en": ex.title_en,
        "description_sk": ex.description_sk, "description_en": ex.description_en,
        "topics": topics, "code_cells": ex.code_cells,
        "published": ex.published, "accessible": ex.accessible,
        "run_timeout": ex.run_timeout,
    }
    if with_stats:
        completed = ExerciseProgress.query.filter_by(exercise_id=ex.id, status="completed").count()
        in_progress = ExerciseProgress.query.filter_by(exercise_id=ex.id, status="in_progress").count()
        data["stats"] = {"completed": completed, "in_progress": in_progress}
    return data


# ---------- zoznam všetkých cvičení (admin) ----------
@admin_exercise_bp.route("", methods=["GET"])
@admin_exercise_bp.route("/", methods=["GET"])
@admin_required
def list_all():
    exercises = Exercise.query.order_by(Exercise.order_index, Exercise.id).all()
    return jsonify({"exercises": [_serialize(e, with_stats=True) for e in exercises]})


# ---------- progres + ODPOVEDE študenta (pre admina) ----------
@admin_exercise_bp.route("/user/<int:uid>", methods=["GET"])
@admin_required
def user_exercises(uid):
    student = Student.query.get(uid)
    if not student:
        return jsonify({"error": "Používateľ neexistuje."}), 404

    exercises = Exercise.query.filter_by(published=True).order_by(
        Exercise.order_index, Exercise.id
    ).all()

    out = []
    for ex in exercises:
        p = ExerciseProgress.query.filter_by(student_id=uid, exercise_id=ex.id).first()
        percent = p.percent if p else 0
        status = p.status if p else "not_started"
        try:
            done = set(json.loads(p.done_cells_json or "[]")) if p else set()
        except Exception:
            done = set()
        try:
            answers = json.loads(p.answers_json or "{}") if p else {}
        except Exception:
            answers = {}

        cells = []
        try:
            nb = _load_notebook(ex)
            ci = 0
            for c in nb.get("cells", []):
                if c.get("cell_type") == "code":
                    ans = answers.get(str(ci))
                    cells.append({
                        "code_index": ci,
                        "prompt": _cell_source(c),
                        "answer": ans,
                        "answered": ans is not None,
                        "ran_ok": ci in done,
                    })
                    ci += 1
        except Exception:
            pass

        out.append({
            "id": ex.id, "order_index": ex.order_index,
            "title_sk": ex.title_sk, "title_en": ex.title_en,
            "code_cells": ex.code_cells,
            "percent": percent, "status": status,
            "cells": cells,
        })

    return jsonify({
        "student": {
            "id": student.id, "name": student.name, "surname": student.surname,
            "login": student.login, "email": student.email,
        },
        "exercises": out,
    })


# ---------- nahratie nového notebooku ----------
@admin_exercise_bp.route("", methods=["POST"])
@admin_exercise_bp.route("/", methods=["POST"])
@admin_required
def upload_exercise():
    if "file" not in request.files:
        return jsonify({"error": "Chýba súbor (.ipynb)."}), 400
    f = request.files["file"]
    if not f.filename or not is_notebook(f.filename):
        return jsonify({"error": "Nahraj súbor typu .ipynb."}), 400

    filename = os.path.basename(f.filename)
    dest = exercise_path(filename)
    if os.path.exists(dest):
        return jsonify({"error": "Súbor s týmto názvom už existuje."}), 409

    raw = f.read()
    try:
        nb = json.loads(raw.decode("utf-8"))
        if "cells" not in nb:
            raise ValueError("nie je to platný notebook")
    except Exception:
        return jsonify({"error": "Súbor nie je platný Jupyter notebook."}), 400

    with open(dest, "w", encoding="utf-8") as out:
        out.write(raw.decode("utf-8"))

    slug = _slug_from_filename(filename)
    if Exercise.query.filter_by(slug=slug).first():
        return jsonify({"error": "Cvičenie s týmto slug už existuje."}), 409

    title = notebook_scan._extract_title(nb, fallback=slug)
    topics = notebook_scan._extract_topics(nb)
    order = request.form.get("order_index")
    try:
        order = int(order) if order not in (None, "") else notebook_scan._order_from_filename(filename)
    except ValueError:
        order = notebook_scan._order_from_filename(filename)

    rt = request.form.get("run_timeout")
    try:
        rt = int(rt) if rt not in (None, "") else None
        if rt is not None and rt <= 0:
            rt = None
    except ValueError:
        rt = None

    ex = Exercise(
        slug=slug, filename=filename, order_index=order, run_timeout=rt,
        title_sk=(request.form.get("title_sk") or title),
        title_en=(request.form.get("title_en") or title),
        description_sk=request.form.get("description_sk") or "",
        description_en=request.form.get("description_en") or "",
        topics_json=json.dumps(topics, ensure_ascii=False),
        code_cells=_count_code_cells(nb),
        published=False, accessible=False,
    )
    db.session.add(ex)
    db.session.commit()
    return jsonify({"exercise": _serialize(ex, with_stats=True)}), 201


# ---------- úprava metadát / prepínačov / timeoutu ----------
@admin_exercise_bp.route("/<int:ex_id>", methods=["PATCH"])
@admin_required
def patch_exercise(ex_id):
    ex = Exercise.query.get(ex_id)
    if not ex:
        return jsonify({"error": "Cvičenie neexistuje."}), 404
    data = request.get_json(silent=True) or {}

    for field in ("title_sk", "title_en", "description_sk", "description_en"):
        if field in data:
            setattr(ex, field, (data[field] or ""))
    if "order_index" in data:
        try:
            ex.order_index = int(data["order_index"])
        except (TypeError, ValueError):
            pass
    if "topics" in data and isinstance(data["topics"], list):
        ex.topics_json = json.dumps([str(t) for t in data["topics"]], ensure_ascii=False)
    if "published" in data:
        ex.published = bool(data["published"])
    if "accessible" in data:
        ex.accessible = bool(data["accessible"])
        if ex.accessible and not ex.published:
            ex.published = True
    if "run_timeout" in data:
        v = data["run_timeout"]
        try:
            iv = int(v) if v not in (None, "", 0, "0") else None
            ex.run_timeout = iv if (iv is None or iv > 0) else None
        except (TypeError, ValueError):
            ex.run_timeout = None

    db.session.commit()
    return jsonify({"exercise": _serialize(ex, with_stats=True)})


# ---------- surový obsah notebooku ----------
@admin_exercise_bp.route("/<int:ex_id>/raw", methods=["GET"])
@admin_required
def get_raw(ex_id):
    ex = Exercise.query.get(ex_id)
    if not ex:
        return jsonify({"error": "Cvičenie neexistuje."}), 404
    try:
        with open(exercise_path(ex.filename), "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return jsonify({"error": "Súbor sa nepodarilo načítať."}), 500
    return jsonify({"filename": ex.filename, "content": content})


# ---------- uloženie upraveného notebooku ----------
@admin_exercise_bp.route("/<int:ex_id>/raw", methods=["PUT"])
@admin_required
def put_raw(ex_id):
    ex = Exercise.query.get(ex_id)
    if not ex:
        return jsonify({"error": "Cvičenie neexistuje."}), 404
    data = request.get_json(silent=True) or {}
    content = data.get("content", "")
    try:
        nb = json.loads(content)
        if "cells" not in nb:
            raise ValueError("nie je to notebook")
    except Exception:
        return jsonify({"error": "Obsah nie je platný Jupyter notebook (JSON)."}), 400

    with open(exercise_path(ex.filename), "w", encoding="utf-8") as f:
        f.write(content)
    ex.code_cells = _count_code_cells(nb)
    db.session.commit()
    return jsonify({"exercise": _serialize(ex, with_stats=True)})


# ---------- nahradenie súboru ----------
@admin_exercise_bp.route("/<int:ex_id>/file", methods=["PUT"])
@admin_required
def replace_file(ex_id):
    ex = Exercise.query.get(ex_id)
    if not ex:
        return jsonify({"error": "Cvičenie neexistuje."}), 404
    if "file" not in request.files:
        return jsonify({"error": "Chýba súbor."}), 400
    f = request.files["file"]
    if not f.filename or not is_notebook(f.filename):
        return jsonify({"error": "Nahraj súbor typu .ipynb."}), 400
    raw = f.read().decode("utf-8")
    try:
        nb = json.loads(raw)
        if "cells" not in nb:
            raise ValueError
    except Exception:
        return jsonify({"error": "Súbor nie je platný notebook."}), 400
    with open(exercise_path(ex.filename), "w", encoding="utf-8") as out:
        out.write(raw)
    ex.code_cells = _count_code_cells(nb)
    db.session.commit()
    return jsonify({"exercise": _serialize(ex, with_stats=True)})


# ---------- zmazanie cvičenia ----------
@admin_exercise_bp.route("/<int:ex_id>", methods=["DELETE"])
@admin_required
def delete_exercise(ex_id):
    ex = Exercise.query.get(ex_id)
    if not ex:
        return jsonify({"error": "Cvičenie neexistuje."}), 404
    delete_file = request.args.get("file") == "1"
    fname = ex.filename
    ExerciseProgress.query.filter_by(exercise_id=ex.id).delete()
    db.session.delete(ex)
    db.session.commit()
    if delete_file:
        try:
            os.remove(exercise_path(fname))
        except OSError:
            pass
    return jsonify({"ok": True})


# ---------- znovu naskenovať priečinok ----------
@admin_exercise_bp.route("/rescan", methods=["POST"])
@admin_required
def rescan():
    notebook_scan.sync_exercises()
    exercises = Exercise.query.order_by(Exercise.order_index, Exercise.id).all()
    return jsonify({"exercises": [_serialize(e, with_stats=True) for e in exercises]})
