# ============================================================
# AdaptPy - jednoduchá migrácia schémy pre cvičenia.
#
# db.create_all() vytvorí len chýbajúce TABUĽKY, nie chýbajúce STĹPCE.
# Tu dopĺňame stĺpce pridané dodatočne:
#   - exercise_progress.answers_json
#   - exercises.run_timeout
# Spúšťa sa pri štarte (z notebook_scan.sync_exercises()).
# Funguje na Postgres aj SQLite.
# ============================================================
from sqlalchemy import inspect, text
from models import db


def ensure_exercise_schema():
    try:
        insp = inspect(db.engine)
        tables = insp.get_table_names()

        # --- exercise_progress.answers_json ---
        if "exercise_progress" in tables:
            cols = {c["name"] for c in insp.get_columns("exercise_progress")}
            if "answers_json" not in cols:
                db.session.execute(
                    text("ALTER TABLE exercise_progress ADD COLUMN answers_json TEXT")
                )
                db.session.commit()
                print("[cvičenia] migrácia: pridaný stĺpec exercise_progress.answers_json")

        # --- exercises.run_timeout ---
        if "exercises" in tables:
            cols_ex = {c["name"] for c in insp.get_columns("exercises")}
            if "run_timeout" not in cols_ex:
                db.session.execute(
                    text("ALTER TABLE exercises ADD COLUMN run_timeout INTEGER")
                )
                db.session.commit()
                print("[cvičenia] migrácia: pridaný stĺpec exercises.run_timeout")
    except Exception as e:
        db.session.rollback()
        print(f"[cvičenia] migrácia schémy preskočená/chyba: {e}")
