# ============================================================
# AdaptPy - načítanie cvičení z priečinku pri štarte aplikácie.
#
# Prejde všetky .ipynb v EXERCISES_DIR a "zosynchronizuje" ich
# do tabuľky `exercises`:
#   - nový súbor  -> vytvorí sa záznam (nadpis, popis, témy, počet buniek)
#   - známy súbor -> aktualizuje sa len počet code-buniek (metadáta, ktoré
#                     admin upravil v appke, ostanú zachované)
#   - zmiznutý súbor -> ostáva v DB, ale označí sa published=False
#                        (nestratíme progres študentov)
# Voláme z app.py po db.create_all().
# ============================================================
import json
import os
import re

from models import db
from models_exercises import Exercise
from services.exercise_store import get_exercises_dir, is_notebook


def _read_notebook(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _cell_source(cell):
    src = cell.get("source", "")
    if isinstance(src, list):
        return "".join(src)
    return src or ""


def _count_code_cells(nb):
    return sum(1 for c in nb.get("cells", []) if c.get("cell_type") == "code")


def _extract_title(nb, fallback):
    # Prvý H1 (# ...) z markdownu = nadpis cvičenia.
    for c in nb.get("cells", []):
        if c.get("cell_type") != "markdown":
            continue
        for line in _cell_source(c).splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    return fallback


def _extract_topics(nb, limit=8):
    # Nadpisy sekcií (## ...) = "čo sa preberá / aké časti".
    topics = []
    for c in nb.get("cells", []):
        if c.get("cell_type") != "markdown":
            continue
        for line in _cell_source(c).splitlines():
            line = line.strip()
            if line.startswith("## "):
                t = re.sub(r"^#+\s*", "", line).strip()
                # odstráň úvodné číslovanie typu "1." / "1.2."
                t = re.sub(r"^\d+(\.\d+)*\.?\s*", "", t).strip()
                if t and t not in topics:
                    topics.append(t)
    return topics[:limit]


def _order_from_filename(filename):
    # "lab07-..." / "07-..." -> 7 ; inak veľké číslo (na koniec)
    m = re.search(r"(\d+)", filename)
    return int(m.group(1)) if m else 999


def _slug_from_filename(filename):
    return os.path.splitext(os.path.basename(filename))[0]


def sync_exercises():
    """Zosynchronizuje priečinok s cvičeniami do DB. Idempotentné."""
    directory = get_exercises_dir()
    files = sorted(f for f in os.listdir(directory) if is_notebook(f))
    seen_slugs = set()

    for filename in files:
        path = os.path.join(directory, filename)
        try:
            nb = _read_notebook(path)
        except Exception as e:
            print(f"[cvičenia] preskočený nečitateľný notebook {filename}: {e}")
            continue

        slug = _slug_from_filename(filename)
        seen_slugs.add(slug)
        code_cells = _count_code_cells(nb)

        ex = Exercise.query.filter_by(slug=slug).first()
        if ex is None:
            title = _extract_title(nb, fallback=slug)
            topics = _extract_topics(nb)
            ex = Exercise(
                slug=slug,
                filename=filename,
                order_index=_order_from_filename(filename),
                title_sk=title,
                title_en=title,
                description_sk="",
                description_en="",
                topics_json=json.dumps(topics, ensure_ascii=False),
                code_cells=code_cells,
                published=False,     # admin musí vedome publikovať
                accessible=False,    # a vedome sprístupniť
            )
            db.session.add(ex)
            print(f"[cvičenia] pridané nové cvičenie: {slug} ({code_cells} buniek)")
        else:
            # len osviežime to, čo sa mení v súbore; metadáta od admina nechávame
            ex.filename = filename
            ex.code_cells = code_cells

    # notebooky, ktoré zmizli z priečinku - odpublikuj (nemaž, progres ostáva)
    if seen_slugs:
        vanished = Exercise.query.filter(~Exercise.slug.in_(seen_slugs)).all()
    else:
        vanished = Exercise.query.all()
    for ex in vanished:
        if ex.published or ex.accessible:
            ex.published = False
            ex.accessible = False
            print(f"[cvičenia] súbor zmizol, odpublikované: {ex.slug}")

    db.session.commit()
