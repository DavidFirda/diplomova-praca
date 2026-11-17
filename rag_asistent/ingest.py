"""Rozseka materialy z data/ na kusky a ulozi ich do index/chunks.jsonl."""
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from config import CHUNK_CHARS, DATA, INDEX, OVERLAP_CHARS, SOURCES

SKIP_DIRS = {".ipynb_checkpoints", "__pycache__", ".git", ".venv"}
EXTS = {".pptx", ".ipynb", ".py", ".md", ".txt", ".pdf"}
SK_CHARS = re.compile(r"[áäčďéíĺľňóôŕšťúýž]", re.I)


def clean(text):
    # \x0b = novy riadok v pptx, \u02c6 robia niektore pdf
    for bad, good in (("\x0b", "\n"), ("\x00", " "), ("\u00a0", " "), ("\u02c6", "")):
        text = text.replace(bad, good)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def guess_lang(text):
    letters = re.findall(r"[a-záäčďéíĺľňóôŕšťúýž]", text.lower())
    if not letters:
        return "?"
    return "sk" if len(SK_CHARS.findall(text)) / len(letters) > 0.01 else "en"


def lecture_no(path):
    for name in (path.stem, path.parent.name):
        m = re.search(r"(?<![a-z])(?:lecture|prednaska)[ _-]?0*(\d{1,2})(?!\d)", name, re.I)
        if m:
            return int(m.group(1))
    return None


def pack(units, max_chars=CHUNK_CHARS, overlap=0):
    """Spoji male casti do kuskov do max_chars, prilis dlhe rozdeli."""
    pieces = []
    for text, loc in units:
        text = text.strip()
        if not text:
            continue
        while len(text) > max_chars * 1.3:  # dlhu cast rozdel na konci riadku
            cut = text.rfind("\n", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            pieces.append((text[:cut], loc))
            text = text[cut:].lstrip()
        pieces.append((text, loc))

    chunks, buf, locs = [], "", []
    for text, loc in pieces:
        if buf and len(buf) + len(text) > max_chars:
            chunks.append((buf, locs))
            tail = ""
            if overlap:  # prekryv zacina na zaciatku slova
                start = buf.find(" ", len(buf) - overlap)
                tail = buf[start + 1:] if start != -1 else ""
            buf, locs = tail, locs[-1:] if tail else []
        buf = f"{buf}\n\n{text}" if buf else text
        locs.append(loc)
    if buf:
        chunks.append((buf, locs))
    return chunks


def loc_range(locs, label):
    locs = [l for l in locs if l is not None]
    if not locs:
        return ""
    lo, hi = min(locs), max(locs)
    return f"{label} {lo}" if lo == hi else f"{label} {lo}–{hi}"


def shape_texts(shapes):
    for sh in shapes:
        if sh.shape_type == 6 and hasattr(sh, "shapes"):  # skupina tvarov
            yield from shape_texts(sh.shapes)
        if getattr(sh, "has_text_frame", False) and sh.text_frame.text.strip():
            yield sh.text_frame.text
        if getattr(sh, "has_table", False):
            for row in sh.table.rows:
                yield " | ".join(c.text.strip() for c in row.cells)


def read_pptx(path):
    from pptx import Presentation
    prs = Presentation(path)
    slides = list(prs.slides)
    deck_title = ""
    if slides:
        # nazov prednasky = prve dva riadky titulneho slajdu
        lines = [l.strip() for t in shape_texts(slides[0].shapes) for l in clean(t).splitlines() if l.strip()]
        deck_title = " – ".join(lines[:2])[:120]
    out = []
    for i, slide in enumerate(slides, start=1):
        parts = list(shape_texts(slide.shapes))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                parts.append(f"Poznámky prednášajúceho: {notes}")
        text = re.sub(r"(^|\n)\d{1,3}(?=\n|$)", "", clean("\n".join(parts))).strip()  # bez cisla slajdu
        if len(text) < 40:  # titulne a prazdne slajdy
            continue
        out.append({"text": text, "loc": f"slajd {i}", "format": "slajd", "title": deck_title})
    return out


def read_ipynb(path):
    nb = json.loads(path.read_text(encoding="utf-8"))
    units = []
    for i, cell in enumerate(nb.get("cells", []), start=1):
        src = "".join(cell.get("source", []))
        if not src.strip():
            continue
        if cell.get("cell_type") == "code":
            src = f"```python\n{src.strip()}\n```"
        units.append((src, i))
    return [{"text": t, "loc": loc_range(l, "bunka"), "format": "notebook"} for t, l in pack(units)]


def read_py(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r"\n\s*\n(?=\S)", text)
    units, line = [], 1
    for b in blocks:
        units.append((b, line))
        line += b.count("\n") + 2
    return [{"text": f"```python\n{t.strip()}\n```", "loc": loc_range(l, "riadok"), "format": "kod"}
            for t, l in pack(units)]


def read_md(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    sections = re.split(r"\n(?=#{1,3} )", text)
    return [{"text": clean(t), "loc": f"časť {i + 1}", "format": "text"}
            for i, (t, _) in enumerate(pack([(s, None) for s in sections]))]


def read_pdf(path):
    from pypdf import PdfReader
    reader = PdfReader(path)
    title = (reader.metadata or {}).get("/Title") if reader.metadata else None
    units = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = clean(page.extract_text() or "")
        except Exception:
            continue
        lines = [l for l in text.splitlines() if l.strip()]
        if len(text) < 200 or not lines:
            continue
        if sum("...." in l or ". . ." in l for l in lines) / len(lines) > 0.3:  # obsah, register
            continue
        units.append((text, i))
    chunks = pack(units, overlap=OVERLAP_CHARS)
    return [{"text": t, "loc": loc_range(l, "str."), "format": "pdf", "title": title} for t, l in chunks]


READERS = {".pptx": read_pptx, ".ipynb": read_ipynb, ".py": read_py,
           ".md": read_md, ".txt": read_md, ".pdf": read_pdf}


def iter_files(folder):
    for p in sorted(folder.rglob("*")):
        if p.is_file() and p.suffix.lower() in EXTS and not (SKIP_DIRS & set(p.parts)):
            yield p


def main():
    INDEX.mkdir(exist_ok=True)
    out_path = INDEX / "chunks.jsonl"
    seen, stats, n = set(), Counter(), 0
    with out_path.open("w", encoding="utf-8") as out:
        for folder_name, src in SOURCES.items():
            folder = DATA / folder_name
            if not folder.exists():
                print(f"[--] data/{folder_name}/ neexistuje, preskakujem")
                continue
            for path in iter_files(folder):
                try:
                    pieces = READERS[path.suffix.lower()](path)
                except Exception as e:
                    print(f"[!!] {path.relative_to(DATA)}: {e}")
                    continue
                rel = path.relative_to(DATA).as_posix()
                for p in pieces:
                    if len(p["text"]) < 60:  # prazdne a testovacie subory
                        continue
                    digest = hashlib.sha1(re.sub(r"\s+", " ", p["text"]).encode()).hexdigest()[:16]
                    if digest in seen:
                        stats["duplikaty"] += 1
                        continue
                    seen.add(digest)
                    title = p.get("title") or path.stem
                    rec = {
                        "id": digest,
                        "typ": src["typ"],
                        "format": p["format"],
                        "subor": rel,
                        "nazov": title,
                        "poloha": p["loc"],
                        "prednaska": None if src["typ"] == "kniha" else lecture_no(path),
                        "jazyk": guess_lang(p["text"]),
                        "text": p["text"],
                    }
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    stats[(src["typ"], p["format"])] += 1
                    n += 1
                print(f"[ok] {rel}: {len(pieces)} kúskov")

    print(f"\nSpolu {n} kúskov -> {out_path}")
    for key, cnt in sorted(stats.items(), key=lambda kv: str(kv[0])):
        print(f"  {key}: {cnt}")
    if n == 0:
        sys.exit("Žiadne materiály. Skopíruj súbory do data/prednasky a data/knihy.")


if __name__ == "__main__":
    main()
