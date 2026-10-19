# ============================================================
# AdaptPy - logovanie interakcií v ÚLOHÁCH.
#
# Každá interakcia (pridelenie úlohy, každý pokus aj chybný, odmietnuté odoslanie,
# správy agenta, ukázanie riešenia, POMDP odmena, zásahy admina) sa zapíše:
#   1. do DB (tabuľka task_events - commitne ju volajúci spolu so zvyškom),
#   2. do textového súboru  <TASK_LOG_DIR>/student_<id>.jsonl  (jeden JSON na riadok).
#
# Textový log je plnohodnotná záloha: pri pokusoch obsahuje aj celý kód študenta
# a výstup. Zlyhanie zápisu do súboru nikdy neprerušuje požiadavku študenta.
# ============================================================
import json
import os
from datetime import datetime, timezone

from flask import current_app

from models import db
from models_ulohy import TaskEvent

try:                      # súborový zámok (Linux/macOS); na iných systémoch sa preskočí
    import fcntl
except ImportError:       # pragma: no cover
    fcntl = None

LOG_DIR = os.environ.get("TASK_LOG_DIR", os.path.join("data", "ulohy_logs"))


def _log_path(student_id):
    return os.path.join(LOG_DIR, f"student_{int(student_id)}.jsonl")


def write_text_log(student_id, record):
    """Pripíše jeden záznam do súboru študenta (pod zámkom, aby sa riadky nemiešali medzi workermi)."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        with open(_log_path(student_id), "a", encoding="utf-8") as f:
            if fcntl:
                fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(line)
                f.flush()
            finally:
                if fcntl:
                    fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        current_app.logger.exception("Zápis do textového logu úloh zlyhal")


def log_event(student_id, event_type, assignment=None, question_id=None,
              payload=None, file_extra=None):
    """
    Zaznamená udalosť do DB (bez commitu) aj do textového súboru.
    payload    - ide do DB aj do súboru,
    file_extra - ide LEN do súboru (napr. celý kód študenta; v DB ho má TaskAttempt).
    """
    payload = payload or {}
    assignment_id = getattr(assignment, "id", None)
    if question_id is None:
        question_id = getattr(assignment, "question_id", None)
    now = datetime.now(timezone.utc)

    db.session.add(TaskEvent(
        student_id=student_id, assignment_id=assignment_id, question_id=question_id,
        event_type=event_type, created_at=now,
        payload_json=json.dumps(payload, ensure_ascii=False, default=str),
    ))
    write_text_log(student_id, {
        "ts": now.isoformat(),
        "student_id": student_id,
        "assignment_id": assignment_id,
        "question_id": question_id,
        "event": event_type,
        **payload,
        **(file_extra or {}),
    })
