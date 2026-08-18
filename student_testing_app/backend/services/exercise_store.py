# ============================================================
# AdaptPy - kde bývajú cvičenia (notebooky) na disku.
#
# Predvolene priečinok `student_testing_app/exercises/`. Dá sa
# prepísať premennou EXERCISES_DIR v .env (napr. na existujúce ../labs).
# Admin doň nahráva / upravuje / maže .ipynb súbory cez aplikáciu.
#
# Sprievodné súbory (obrázky, datasety) sú v podpriečinku `sources/`,
# členené po cvičeniach: sources/lab01/, sources/lab11/iris.csv, atď.
# ============================================================
import os
import re

# .../backend/services/exercise_store.py -> .../backend
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# .../backend -> .../student_testing_app
_APP_DIR = os.path.dirname(_BACKEND_DIR)


def get_exercises_dir() -> str:
    """Absolútna cesta k priečinku s cvičeniami. Vytvorí ho, ak chýba."""
    d = os.getenv("EXERCISES_DIR")
    if not d:
        d = os.path.join(_APP_DIR, "exercises")
    d = os.path.abspath(d)
    os.makedirs(d, exist_ok=True)
    return d


def exercise_path(filename: str) -> str:
    """Bezpečná cesta k jednému notebooku (basename - žiadne ../)."""
    return os.path.join(get_exercises_dir(), os.path.basename(filename))


def is_notebook(filename: str) -> bool:
    return filename.lower().endswith(".ipynb")


def asset_path(relpath: str):
    """
    Bezpečná cesta k sprievodnému súboru (obrázok/dataset) v rámci
    priečinka s cvičeniami. Zabráni úniku mimo priečinka (../).
    Vráti absolútnu cestu alebo None, ak by cesta viedla von / neexistuje.
    """
    base = get_exercises_dir()
    # normalizuj a znemožni traversal
    candidate = os.path.normpath(os.path.join(base, relpath))
    if candidate != base and not candidate.startswith(base + os.sep):
        return None
    if not os.path.isfile(candidate):
        return None
    return candidate


def source_dir_for_slug(slug: str):
    """
    Pracovný priečinok pre spúšťanie kódu daného cvičenia.
    Zo slugu vytiahne 'labNN' a nájde 'sources/labNN' (tam bývajú
    iris.csv, word_list.txt, *_results.txt, ...). Vďaka tomu kód typu
    pd.read_csv('iris.csv') / open('word_list.txt') nájde svoje súbory.
    Vráti absolútnu cestu alebo None, ak taký priečinok neexistuje.
    """
    if not slug:
        return None
    m = re.search(r"(lab\d+)", slug)
    if not m:
        return None
    candidate = os.path.join(get_exercises_dir(), "sources", m.group(1))
    return candidate if os.path.isdir(candidate) else None
