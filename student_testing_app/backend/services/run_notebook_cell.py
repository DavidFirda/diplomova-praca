# ============================================================
# AdaptPy - spúšťanie code-buniek cvičenia.
#
# Bunky sa spúšťajú v perzistentnom namespace na dvojicu
# (student_id, exercise_id), takže neskoršie bunky vidia definície
# z predchádzajúcich (rovnako ako v Jupyteri). Bunka je "hotová",
# keď dobehne bez výnimky - výstup sa nemusí zhodovať s ničím.
#
# Ak je zadaný `workdir` (napr. sources/lab11), kód beží v ňom, takže
# open('word_list.txt') / pd.read_csv('iris.csv') nájdu svoje súbory.
# Zmena pracovného priečinka je serializovaná zámkom (chdir je
# procesovo-globálny), aby sa vlákna navzájom nerušili.
#
# ⚠️ Bezpečnosť: kód beží cez exec() bez izolácie a bez timeoutu
# (rovnaký vedomý kompromis ako v services/capture_output.py). Pre
# nasadenie mimo dôveryhodné prostredie doplň sandbox / timeout /
# whitelist builtinov.
# ============================================================
import contextlib
import io
import os
import threading
import traceback

# { "student_id:exercise_id": {namespace...} }
_namespaces = {}
# chdir je procesovo-globálny -> spúšťanie serializujeme v rámci procesu
_run_lock = threading.Lock()


def _key(student_id, exercise_id):
    return f"{student_id}:{exercise_id}"


def reset_namespace(student_id, exercise_id):
    """Vyčistí premenné - študent spúšťa cvičenie akoby odznova."""
    _namespaces.pop(_key(student_id, exercise_id), None)


def run_cell(student_id, exercise_id, code, workdir=None):
    """Spustí kód bunky. Vráti dict: ok, output, error."""
    key = _key(student_id, exercise_id)
    ns = _namespaces.get(key)
    if ns is None:
        ns = {"__name__": "__main__"}
        _namespaces[key] = ns

    buf = io.StringIO()
    result = {"ok": True, "output": "", "error": None}

    with _run_lock:
        prev_cwd = None
        try:
            if workdir and os.path.isdir(workdir):
                prev_cwd = os.getcwd()
                os.chdir(workdir)
            try:
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    exec(code, ns)
                result = {"ok": True, "output": buf.getvalue(), "error": None}
            except Exception:
                result = {
                    "ok": False,
                    "output": buf.getvalue(),
                    "error": traceback.format_exc(limit=3),
                }
        finally:
            if prev_cwd is not None:
                try:
                    os.chdir(prev_cwd)
                except OSError:
                    pass

    return result
