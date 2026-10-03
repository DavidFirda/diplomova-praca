# ============================================================
# AdaptPy - kde bývajú cvičenia (notebooky) na disku.
# ============================================================
import os
import re

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP_DIR = os.path.dirname(_BACKEND_DIR)


def get_exercises_dir() -> str:
    d = os.getenv("EXERCISES_DIR")
    if not d:
        d = os.path.join(_APP_DIR, "exercises")
    d = os.path.abspath(d)
    os.makedirs(d, exist_ok=True)
    return d


def exercise_path(filename: str) -> str:
    return os.path.join(get_exercises_dir(), os.path.basename(filename))


def is_notebook(filename: str) -> bool:
    return filename.lower().endswith(".ipynb")


def asset_path(relpath: str):
    """Bezpečná cesta k sprievodnému súboru (obrázok/dataset)."""
    base = get_exercises_dir()
    candidate = os.path.normpath(os.path.join(base, relpath))
    if candidate != base and not candidate.startswith(base + os.sep):
        return None
    if not os.path.isfile(candidate):
        return None
    return candidate


def source_dir_for_slug(slug: str):
    """Absolútna cesta k 'sources/labNN' (alebo None)."""
    if not slug:
        return None
    m = re.search(r"(lab\d+)", slug)
    if not m:
        return None
    candidate = os.path.join(get_exercises_dir(), "sources", m.group(1))
    return candidate if os.path.isdir(candidate) else None


def source_dir_rel_for_slug(slug: str):
    """RELATÍVNA cesta k dátam cvičenia, napr. 'sources/lab11' (alebo None)."""
    if not slug:
        return None
    m = re.search(r"(lab\d+)", slug)
    if not m:
        return None
    rel = os.path.join("sources", m.group(1))
    return rel if os.path.isdir(os.path.join(get_exercises_dir(), rel)) else None
