# ============================================================
# Admin API - AI ASISTENT (prefix /api/admin/assistant).
#
#   GET    /settings              model, think, teplota + stav Ollamy
#   POST   /settings              zmena modelu/think/teploty/zapnutia za behu
#   POST   /test                  krátka skúšobná odpoveď modelu (overenie spojenia)
#   GET    /stats                 prehľad: počty podľa režimu, časy, zásahy strážcu, zdroje
#   GET    /conversations         zoznam konverzácií (filter: študent, režim, text)
#   GET    /conversations/<id>    správy so zdrojmi RAG, zásahmi strážcu a časmi
#   DELETE /conversations/<id>    zmazanie konverzácie (napr. na žiadosť študenta)
#   GET    /export.csv            export správ do CSV (rovnaké filtre ako zoznam)
# ============================================================
import csv
import io
import json
from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import func

from extensions import admin_required
from models import db, Student
from models_ai import AssistantConversation, AssistantMessage, AssistantSource
from services.ai import config as ai_config
from services.ai import llm

admin_assistant_bp = Blueprint("admin_assistant", __name__)


def _iso(dt):
    return dt.isoformat() if dt else None


def _loads(text, default=None):
    try:
        return json.loads(text) if text else default
    except ValueError:
        return default


def _student_name(s):
    return f"{s.name} {s.surname}".strip() if s else ""


# ------------------------------------------------------------
# Nastavenia modelu
# ------------------------------------------------------------
@admin_assistant_bp.route("/settings", methods=["GET"])
@admin_required
def get_settings():
    cfg = ai_config.load()
    return jsonify({"config": ai_config.public_view(cfg), "health": llm.health(cfg)})


@admin_assistant_bp.route("/settings", methods=["POST"])
@admin_required
def save_settings():
    data = request.get_json(silent=True) or {}
    model = data.get("chat_model")
    if model is not None and len(str(model)) > 100:
        return jsonify({"error": "Názov modelu je príliš dlhý."}), 400
    think = data.get("think")
    if think is not None and str(think).lower() not in ("", "true", "false", "low", "medium", "high"):
        return jsonify({"error": "think musí byť true, false, low, medium alebo high."}), 400
    temperature = data.get("temperature")
    if temperature not in (None, ""):
        try:
            float(temperature)
        except (TypeError, ValueError):
            return jsonify({"error": "Teplota musí byť číslo."}), 400
    ai_config.save_runtime(
        model=None if model is None else str(model),
        think=None if think is None else str(think),
        temperature=None if temperature is None else str(temperature),
        enabled=None if "enabled" not in data else bool(data["enabled"]),
    )
    cfg = ai_config.load()
    return jsonify({"config": ai_config.public_view(cfg), "health": llm.health(cfg)})


@admin_assistant_bp.route("/test", methods=["POST"])
@admin_required
def test_model():
    cfg = ai_config.load()
    try:
        with llm.slot(cfg, wait_s=5):
            text, stats = llm.chat(cfg, [
                {"role": "system", "content": "Answer in Slovak in one short sentence."},
                {"role": "user", "content": "Čo je premenná v Pythone?"}],
                max_tokens=cfg.max_tokens_think if cfg.think not in (None, False) else 120,
                temperature=cfg.temperature, think=cfg.think)
    except llm.Busy:
        return jsonify({"ok": False, "error": "Model je práve vyťažený."}), 503
    except llm.LlmUnavailable as e:
        return jsonify({"ok": False, "error": str(e)}), 503
    return jsonify({"ok": True, "text": text, "stats": stats})


# ------------------------------------------------------------
# Filtre (zoznam aj export)
# ------------------------------------------------------------
def _filtered_conversations():
    q = AssistantConversation.query
    try:
        sid = int(request.args.get("student_id")) if request.args.get("student_id") else None
    except ValueError:
        sid = None
    if sid:
        q = q.filter(AssistantConversation.student_id == sid)
    mode = request.args.get("mode")
    if mode in ("dashboard", "exercise", "task"):
        q = q.filter(AssistantConversation.mode == mode)
    days = request.args.get("days")
    if days:
        try:
            since = datetime.now(timezone.utc) - timedelta(days=int(days))
            q = q.filter(AssistantConversation.updated_at >= since)
        except ValueError:
            pass
    text = (request.args.get("q") or "").strip()
    if text:
        like = f"%{text}%"
        sub = db.session.query(AssistantMessage.conversation_id).filter(AssistantMessage.text.ilike(like))
        students = db.session.query(Student.id).filter(
            (Student.login.ilike(like)) | (Student.name.ilike(like)) | (Student.surname.ilike(like)))
        q = q.filter(AssistantConversation.id.in_(sub) | AssistantConversation.student_id.in_(students))
    if request.args.get("guard") == "1":
        sub = db.session.query(AssistantMessage.conversation_id).filter(AssistantMessage.guard_hits > 0)
        q = q.filter(AssistantConversation.id.in_(sub))
    return q


def _context_label(conv):
    if conv.mode == "exercise" and conv.exercise_id:
        from models_exercises import Exercise
        ex = db.session.get(Exercise, conv.exercise_id)
        return f"Cvičenie: {ex.title_sk if ex else conv.exercise_id}"
    if conv.mode == "task" and conv.assignment_id:
        from models_ulohy import TaskAssignment
        a = db.session.get(TaskAssignment, conv.assignment_id)
        return f"Úloha #{conv.assignment_id}" + (f" ({a.category})" if a else "")
    return "Dashboard"


# ------------------------------------------------------------
# Zoznam a detail
# ------------------------------------------------------------
@admin_assistant_bp.route("/conversations", methods=["GET"])
@admin_required
def conversations():
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 200))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        limit, offset = 50, 0
    q = _filtered_conversations()
    total = q.count()
    rows = q.order_by(AssistantConversation.updated_at.desc()).offset(offset).limit(limit).all()
    ids = [c.id for c in rows]
    counts = {}
    if ids:
        for cid, role, n, guard, hints in db.session.query(
                AssistantMessage.conversation_id, AssistantMessage.role, func.count(AssistantMessage.id),
                func.coalesce(func.sum(AssistantMessage.guard_hits), 0),
                func.count(AssistantMessage.hint_level)).filter(
                AssistantMessage.conversation_id.in_(ids)).group_by(
                AssistantMessage.conversation_id, AssistantMessage.role).all():
            c = counts.setdefault(cid, {"student": 0, "assistant": 0, "event": 0, "guard": 0, "hints": 0})
            c[role] = n
            c["guard"] += int(guard or 0)
            if role == "assistant":
                c["hints"] = hints
    students = {s.id: s for s in Student.query.filter(Student.id.in_({c.student_id for c in rows})).all()} \
        if rows else {}
    return jsonify({
        "total": total,
        "conversations": [{
            "id": c.id, "mode": c.mode, "context": _context_label(c),
            "student_id": c.student_id, "student_login": getattr(students.get(c.student_id), "login", ""),
            "student_name": _student_name(students.get(c.student_id)),
            "questions": counts.get(c.id, {}).get("student", 0),
            "answers": counts.get(c.id, {}).get("assistant", 0),
            "inserts": counts.get(c.id, {}).get("event", 0),
            "guard_hits": counts.get(c.id, {}).get("guard", 0),
            "hints": counts.get(c.id, {}).get("hints", 0),
            "created_at": _iso(c.created_at), "updated_at": _iso(c.updated_at),
        } for c in rows],
    })


def _message_dict(m, sources):
    return {
        "id": m.id, "role": m.role, "kind": m.kind, "text": m.text, "hint_level": m.hint_level,
        "status": m.status, "model": m.model, "think": m.think, "prompt_version": m.prompt_version,
        "latency_ms": m.latency_ms, "first_token_ms": m.first_token_ms,
        "tokens_in": m.tokens_in, "tokens_out": m.tokens_out,
        "guard": _loads(m.guard_json, []), "context": _loads(m.context_json, {}),
        "created_at": _iso(m.created_at),
        "sources": [{
            "rank": s.rank, "material_id": s.material_id, "chunk_id": s.chunk_id, "type": s.source_type,
            "title": s.title, "lecture_no": s.lecture_no, "location": s.location, "score": s.score,
            "signals": s.signals, "snippet": s.snippet,
        } for s in sources],
    }


@admin_assistant_bp.route("/conversations/<int:cid>", methods=["GET"])
@admin_required
def conversation_detail(cid):
    conv = db.session.get(AssistantConversation, cid)
    if conv is None:
        return jsonify({"error": "Konverzácia neexistuje."}), 404
    msgs = AssistantMessage.query.filter_by(conversation_id=cid).order_by(AssistantMessage.id).all()
    srcs = {}
    if msgs:
        for s in AssistantSource.query.filter(AssistantSource.message_id.in_([m.id for m in msgs])) \
                .order_by(AssistantSource.message_id, AssistantSource.rank).all():
            srcs.setdefault(s.message_id, []).append(s)
    student = db.session.get(Student, conv.student_id)
    return jsonify({
        "conversation": {
            "id": conv.id, "mode": conv.mode, "context": _context_label(conv),
            "exercise_id": conv.exercise_id, "assignment_id": conv.assignment_id,
            "student_id": conv.student_id, "student_login": getattr(student, "login", ""),
            "student_name": _student_name(student),
            "created_at": _iso(conv.created_at), "updated_at": _iso(conv.updated_at),
        },
        "messages": [_message_dict(m, srcs.get(m.id, [])) for m in msgs],
    })


@admin_assistant_bp.route("/conversations/<int:cid>", methods=["DELETE"])
@admin_required
def conversation_delete(cid):
    conv = db.session.get(AssistantConversation, cid)
    if conv is None:
        return jsonify({"error": "Konverzácia neexistuje."}), 404
    msg_ids = [m.id for m in AssistantMessage.query.filter_by(conversation_id=cid).all()]
    if msg_ids:
        AssistantSource.query.filter(AssistantSource.message_id.in_(msg_ids)).delete(synchronize_session=False)
    AssistantMessage.query.filter_by(conversation_id=cid).delete(synchronize_session=False)
    db.session.delete(conv)
    db.session.commit()
    return jsonify({"ok": True})


# ------------------------------------------------------------
# Prehľad
# ------------------------------------------------------------
@admin_assistant_bp.route("/stats", methods=["GET"])
@admin_required
def stats():
    conv_ids = _filtered_conversations().with_entities(AssistantConversation.id)
    base = AssistantMessage.query.filter(AssistantMessage.conversation_id.in_(conv_ids))
    by_mode = {}
    for mode, role, n in db.session.query(
            AssistantConversation.mode, AssistantMessage.role, func.count(AssistantMessage.id)).join(
            AssistantConversation, AssistantConversation.id == AssistantMessage.conversation_id).filter(
            AssistantMessage.conversation_id.in_(conv_ids)).group_by(
            AssistantConversation.mode, AssistantMessage.role).all():
        by_mode.setdefault(mode, {})[role] = n

    answers = base.filter(AssistantMessage.role == "assistant")
    lat = answers.filter(AssistantMessage.status == "ok").with_entities(
        func.avg(AssistantMessage.latency_ms), func.avg(AssistantMessage.first_token_ms),
        func.avg(AssistantMessage.tokens_out)).one()
    statuses = dict(answers.with_entities(AssistantMessage.status, func.count(AssistantMessage.id))
                    .group_by(AssistantMessage.status).all())
    hints = dict(answers.filter(AssistantMessage.hint_level.isnot(None)).with_entities(
        AssistantMessage.hint_level, func.count(AssistantMessage.id)).group_by(AssistantMessage.hint_level).all())

    rules = {}
    for (guard_json,) in answers.filter(AssistantMessage.guard_hits > 0).with_entities(AssistantMessage.guard_json):
        for h in _loads(guard_json, []) or []:
            key = f"{h.get('rule')} → {h.get('action')}"
            rules[key] = rules.get(key, 0) + 1

    msg_ids = answers.with_entities(AssistantMessage.id)
    top = db.session.query(
        AssistantSource.source_type, AssistantSource.title, AssistantSource.lecture_no,
        func.count(AssistantSource.id)).filter(AssistantSource.message_id.in_(msg_ids)).group_by(
        AssistantSource.source_type, AssistantSource.title, AssistantSource.lecture_no).order_by(
        func.count(AssistantSource.id).desc()).limit(15).all()
    inserts = base.filter(AssistantMessage.role == "event", AssistantMessage.kind == "insert").count()

    return jsonify({
        "by_mode": by_mode,
        "answers": sum(statuses.values()),
        "statuses": statuses,
        "avg_latency_ms": round(lat[0]) if lat[0] else None,
        "avg_first_token_ms": round(lat[1]) if lat[1] else None,
        "avg_tokens_out": round(lat[2]) if lat[2] else None,
        "hints_by_level": {str(k): v for k, v in hints.items()},
        "guard_rules": dict(sorted(rules.items(), key=lambda kv: -kv[1])),
        "guard_answers": answers.filter(AssistantMessage.guard_hits > 0).count(),
        "inserts": inserts,
        "top_sources": [{"type": t, "title": ti, "lecture_no": ln, "count": n} for t, ti, ln, n in top],
    })


# ------------------------------------------------------------
# Export CSV
# ------------------------------------------------------------
CSV_COLUMNS = [
    "message_id", "conversation_id", "created_at", "student_id", "login", "mode", "context",
    "exercise_id", "assignment_id", "role", "kind", "hint_level", "status", "text",
    "model", "think", "prompt_version", "latency_ms", "first_token_ms", "tokens_in", "tokens_out",
    "guard_hits", "guard_rules", "sources_count", "sources", "insert_target",
]


@admin_assistant_bp.route("/export.csv", methods=["GET"])
@admin_required
def export_csv():
    convs = _filtered_conversations().order_by(AssistantConversation.id).all()
    conv_by_id = {c.id: c for c in convs}
    students = {s.id: s for s in Student.query.filter(
        Student.id.in_({c.student_id for c in convs})).all()} if convs else {}
    labels = {c.id: _context_label(c) for c in convs}

    buf = io.StringIO()
    buf.write("﻿")                                   # Excel: UTF-8 s BOM
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    w.writerow(CSV_COLUMNS)
    ids = list(conv_by_id)
    for start in range(0, len(ids), 200):
        chunk_ids = ids[start:start + 200]
        msgs = AssistantMessage.query.filter(AssistantMessage.conversation_id.in_(chunk_ids)) \
            .order_by(AssistantMessage.conversation_id, AssistantMessage.id).all()
        srcs = {}
        if msgs:
            for s in AssistantSource.query.filter(AssistantSource.message_id.in_([m.id for m in msgs])) \
                    .order_by(AssistantSource.message_id, AssistantSource.rank).all():
                srcs.setdefault(s.message_id, []).append(s)
        for m in msgs:
            c = conv_by_id[m.conversation_id]
            st = students.get(c.student_id)
            guard = _loads(m.guard_json, []) or []
            src = srcs.get(m.id, [])
            ctx = _loads(m.context_json, {}) or {}
            w.writerow([
                m.id, c.id, _iso(m.created_at), c.student_id, getattr(st, "login", ""), c.mode, labels[c.id],
                c.exercise_id or "", c.assignment_id or "", m.role, m.kind, m.hint_level or "", m.status,
                m.text, m.model or "", m.think or "", m.prompt_version or "", m.latency_ms or "",
                m.first_token_ms or "", m.tokens_in or "", m.tokens_out or "", m.guard_hits,
                " | ".join(f"{h.get('rule')}:{h.get('action')}" for h in guard), len(src),
                " | ".join(f"[{s.rank}] {s.source_type} · {s.title} · {s.location} · {s.score}" for s in src),
                ctx.get("target", "") if m.role == "event" else "",
            ])
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return Response(buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="ai_asistent_{stamp}.csv"'})
