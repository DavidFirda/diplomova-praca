# ============================================================
# AdaptPy - jednoduchá migrácia schémy pre cvičenia.
#
# `db.create_all()` vytvorí len chýbajúce TABUĽKY, nie chýbajúce
# STĹPCE v už existujúcich tabuľkách. Keďže `answers_json` pribudol
# dodatočne, tu ho doplníme cez ALTER TABLE (Postgres aj SQLite).
# Spúšťa sa pri štarte (volá sa z notebook_scan.sync_exercises()).
# ============================================================
from sqlalchemy import inspect, text
from models import db


def ensure_exercise_schema():
    try:
        insp = inspect(db.engine)
        tables = insp.get_table_names()
        if "exercise_progress" not in tables:
            return  # tabuľka ešte neexistuje -> vytvorí ju create_all()

        cols = {c["name"] for c in insp.get_columns("exercise_progress")}
        if "answers_json" not in cols:
            db.session.execute(
                text("ALTER TABLE exercise_progress ADD COLUMN answers_json TEXT")
            )
            db.session.commit()
            print("[cvičenia] migrácia: pridaný stĺpec exercise_progress.answers_json")
    except Exception as e:
        db.session.rollback()
        print(f"[cvičenia] migrácia schémy preskočená/chyba: {e}")
