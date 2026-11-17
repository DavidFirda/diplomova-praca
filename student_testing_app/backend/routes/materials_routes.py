# ============================================================
# AdaptPy - MATERIÁLY KURZU (prednášky, knihy) pre RAG asistenta.
#
#   /api/materials                  (študent) zoznam sprístupnených materiálov, stiahnutie
#   /api/admin/materials            (admin)   nahratie, úprava, zmazanie, reindexovanie,
#                                             test vyhľadávania (čo by RAG našiel k otázke)
#
# Súbory ležia v MATERIALS_DIR, index v RAG_INDEX_DIR (oba sú volume, nejdú na git).
# Indexovanie beží na pozadí (services/ai/rag/indexer.py), stav vidno v zozname.
# ============================================================
import os
import uuid

from flask import Blueprint, jsonify, request, send_file
from flask_login import current_user, login_required

from extensions import admin_required
from models import db
from models_ai import CourseMaterial
from services.ai import config as ai_config
from services.ai.rag import indexer, readers, store

materials_bp = Blueprint("materials", __name__)
admin_materials_bp = Blueprint("admin_materials", __name__)

KINDS = ("prednaska", "kniha")


def _iso(dt):
    return dt.isoformat() if dt else None


def _material_dict(m, admin=False):
    d = {
        "id": m.id, "kind": m.kind, "title": m.title, "original_name": m.original_name,
        "lecture_no": m.lecture_no, "size_bytes": m.size_bytes,
        "ext": os.path.splitext(m.original_name)[1].lower().lstrip("."),
    }
    if admin:
        d.update({
            "weight": m.weight, "default_weight": store.DEFAULT_WEIGHTS.get(m.kind, 1.0),
            "use_in_assistant": m.use_in_assistant, "visible_to_students": m.visible_to_students,
            "status": m.status, "chunks": m.chunks, "error": m.error, "embed_model": m.embed_model,
            "position": m.position, "created_at": _iso(m.created_at), "indexed_at": _iso(m.indexed_at),
        })
    return d


def _ordered(query):
    return query.order_by(CourseMaterial.kind.desc(), CourseMaterial.lecture_no.asc().nullslast(),
                          CourseMaterial.position, CourseMaterial.id)


# ------------------------------------------------------------
# Študent
# ------------------------------------------------------------
@materials_bp.route("", methods=["GET"])
@materials_bp.route("/", methods=["GET"])
@login_required
def list_visible():
    rows = _ordered(CourseMaterial.query.filter(CourseMaterial.visible_to_students.is_(True))).all()
    return jsonify({"materials": [_material_dict(m) for m in rows]})


@materials_bp.route("/<int:mid>/download", methods=["GET"])
@login_required
def download_visible(mid):
    m = db.session.get(CourseMaterial, mid)
    if m is None or not (m.visible_to_students or current_user.is_admin):
        return jsonify({"error": "Materiál neexistuje."}), 404
    return _send(m)


def _send(m):
    cfg = ai_config.load()
    path = indexer.material_path(cfg, m)
    if not os.path.isfile(path):
        return jsonify({"error": "Súbor chýba na disku."}), 404
    return send_file(os.path.abspath(path), as_attachment=True, download_name=m.original_name)


# ------------------------------------------------------------
# Admin
# ------------------------------------------------------------
@admin_materials_bp.route("", methods=["GET"])
@admin_materials_bp.route("/", methods=["GET"])
@admin_required
def admin_list():
    cfg = ai_config.load()
    rows = _ordered(CourseMaterial.query).all()
    ready = [m for m in rows if m.status == "ready" and m.use_in_assistant]
    return jsonify({
        "materials": [_material_dict(m, admin=True) for m in rows],
        "index": {
            "embed_model": cfg.embed_model,
            "chunks_in_assistant": sum(m.chunks for m in ready),
            "materials_in_assistant": len(ready),
            "outdated_embeddings": sum(1 for m in ready if m.embed_model and m.embed_model != cfg.embed_model),
        },
        "upload_exts": sorted(readers.UPLOAD_EXTS),
        "max_upload_mb": cfg.max_upload_mb,
    })


@admin_materials_bp.route("", methods=["POST"])
@admin_materials_bp.route("/", methods=["POST"])
@admin_required
def admin_upload():
    cfg = ai_config.load()
    kind = request.form.get("kind", "prednaska")
    if kind not in KINDS:
        return jsonify({"error": "Neznámy typ materiálu."}), 400
    visible = request.form.get("visible_to_students") == "true"
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "Nevybral si žiadny súbor."}), 400
    os.makedirs(cfg.materials_dir, exist_ok=True)

    created, skipped = [], []
    for f in files:
        name = os.path.basename(f.filename or "").strip()
        ext = os.path.splitext(name)[1].lower()
        if not name or ext not in readers.UPLOAD_EXTS:
            skipped.append({"name": name, "reason": "unsupported"})
            continue
        stored = f"{uuid.uuid4().hex}{ext}"
        path = os.path.join(cfg.materials_dir, stored)
        f.save(path)
        size = os.path.getsize(path)
        if size > cfg.max_upload_mb * 1024 * 1024:
            os.remove(path)
            skipped.append({"name": name, "reason": "too_large"})
            continue
        with open(path, "rb") as fh:
            digest = readers.sha256_of(fh)
        if CourseMaterial.query.filter_by(sha256=digest).first():
            os.remove(path)
            skipped.append({"name": name, "reason": "duplicate"})
            continue
        title = readers.first_slide_title(path, name)   # titulný slajd pptx / názov z pdf
        m = CourseMaterial(
            kind=kind, title=(title or os.path.splitext(name)[0])[:255], original_name=name[:255],
            stored_name=stored, size_bytes=size, sha256=digest,
            lecture_no=readers.lecture_no(name) if kind == "prednaska" else None,
            visible_to_students=visible, status="pending", uploaded_by=current_user.id,
        )
        db.session.add(m)
        db.session.flush()
        created.append(m)
    db.session.commit()
    if created:
        indexer.index_in_background([m.id for m in created])
    return jsonify({"created": [_material_dict(m, admin=True) for m in created], "skipped": skipped}), 201


@admin_materials_bp.route("/<int:mid>", methods=["PATCH"])
@admin_required
def admin_update(mid):
    m = db.session.get(CourseMaterial, mid)
    if m is None:
        return jsonify({"error": "Materiál neexistuje."}), 404
    data = request.get_json(silent=True) or {}
    reindex = False
    if "title" in data:
        m.title = str(data["title"] or "").strip()[:255] or m.original_name
        reindex = True                      # názov je súčasťou vektora kúska
    if "kind" in data and data["kind"] in KINDS and data["kind"] != m.kind:
        m.kind = data["kind"]
        reindex = True
    if "lecture_no" in data:
        try:
            m.lecture_no = int(data["lecture_no"]) if data["lecture_no"] not in (None, "") else None
        except (TypeError, ValueError):
            return jsonify({"error": "Číslo prednášky musí byť celé číslo."}), 400
    if "weight" in data:
        try:
            m.weight = None if data["weight"] in (None, "") else max(0.0, min(float(data["weight"]), 3.0))
        except (TypeError, ValueError):
            return jsonify({"error": "Váha musí byť číslo."}), 400
    for flag in ("use_in_assistant", "visible_to_students"):
        if flag in data:
            setattr(m, flag, bool(data[flag]))
    if "position" in data:
        try:
            m.position = int(data["position"])
        except (TypeError, ValueError):
            pass
    db.session.commit()
    store.bump_version(ai_config.load().index_dir)   # workery si index načítajú znova
    if reindex and m.status in ("ready", "error"):
        indexer.index_in_background([m.id])
    return jsonify({"material": _material_dict(m, admin=True)})


@admin_materials_bp.route("/<int:mid>", methods=["DELETE"])
@admin_required
def admin_delete(mid):
    cfg = ai_config.load()
    m = db.session.get(CourseMaterial, mid)
    if m is None:
        return jsonify({"error": "Materiál neexistuje."}), 404
    path = indexer.material_path(cfg, m)
    db.session.delete(m)
    db.session.commit()
    store.remove_material(cfg.index_dir, mid)
    try:
        os.remove(path)
    except OSError:
        pass
    return jsonify({"ok": True})


@admin_materials_bp.route("/<int:mid>/download", methods=["GET"])
@admin_required
def admin_download(mid):
    m = db.session.get(CourseMaterial, mid)
    if m is None:
        return jsonify({"error": "Materiál neexistuje."}), 404
    return _send(m)


@admin_materials_bp.route("/<int:mid>/reindex", methods=["POST"])
@admin_required
def admin_reindex(mid):
    m = db.session.get(CourseMaterial, mid)
    if m is None:
        return jsonify({"error": "Materiál neexistuje."}), 404
    m.status = "pending"
    db.session.commit()
    indexer.index_in_background([mid])
    return jsonify({"material": _material_dict(m, admin=True)})


@admin_materials_bp.route("/reindex-all", methods=["POST"])
@admin_required
def admin_reindex_all():
    ids = [m.id for m in CourseMaterial.query.order_by(CourseMaterial.id).all()]
    CourseMaterial.query.update({CourseMaterial.status: "pending"})
    db.session.commit()
    indexer.index_in_background(ids)
    return jsonify({"queued": len(ids)})


@admin_materials_bp.route("/search-test", methods=["POST"])
@admin_required
def admin_search_test():
    """Čo by RAG našiel k otázke (na ladenie váh a materiálov, rovnako ako ask.py)."""
    data = request.get_json(silent=True) or {}
    question = str(data.get("question") or "").strip()[:1000]
    if not question:
        return jsonify({"error": "Napíš otázku."}), 400
    try:
        k = max(1, min(int(data.get("k") or 5), 15))
    except (TypeError, ValueError):
        k = 5
    cfg = ai_config.load()
    results, info = indexer.retrieve(cfg, question, k=k)
    return jsonify({
        "info": info,
        "results": [{
            "rank": i, "label": store.source_label(c), "material_id": c.get("material_id"),
            "type": c.get("typ"), "location": c.get("poloha"), "score": c.get("skore"),
            "signals": c.get("poradie"), "text": c.get("text", "")[:1500],
        } for i, c in enumerate(results, start=1)],
    })
