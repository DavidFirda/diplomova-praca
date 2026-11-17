# ============================================================
# AdaptPy RAG - čítanie materiálov a delenie na kúsky.
#
# Prevzaté z rag_asistent/ingest.py (rovnaké delenie, aby výsledky z prieskumu
# platili aj v aplikácii): pptx po slajdoch, pdf po stranách s prekryvom,
# ipynb po bunkách, py po blokoch, md/txt po sekciách. Navyše .zip (napr. kódy
# z prednášky) - prečítajú sa podporované súbory vo vnútri archívu.
# ============================================================
import hashlib
import json
import os
import re
import tempfile
import zipfile

CHUNK_CHARS = 1500
OVERLAP_CHARS = 200
MIN_CHUNK_CHARS = 60
EXTS = {".pptx", ".ipynb", ".py", ".md", ".txt", ".pdf"}
UPLOAD_EXTS = EXTS | {".zip"}
SK_CHARS = re.compile(r"[áäčďéíĺľňóôŕšťúýž]", re.I)
ZIP_MAX_FILES = 200
ZIP_MAX_BYTES = 200 * 1024 * 1024


def clean(text):
    # \x0b = nový riadok v pptx, ˆ robia niektoré pdf
    for bad, good in (("\x0b", "\n"), ("\x00", " "), (" ", " "), ("ˆ", "")):
        text = text.replace(bad, good)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def guess_lang(text):
    letters = re.findall(r"[a-záäčďéíĺľňóôŕšťúýž]", text.lower())
    if not letters:
        return "?"
    return "sk" if len(SK_CHARS.findall(text)) / len(letters) > 0.01 else "en"


def lecture_no(name):
    """Číslo prednášky z názvu súboru (Lecture-05.pptx, prednaska_5, lecture11_codes.zip)."""
    stem = os.path.splitext(os.path.basename(name or ""))[0]
    m = re.search(r"(?<![a-z])(?:lecture|prednaska|prednáška)[ _-]?0*(\d{1,2})(?!\d)", stem, re.I)
    return int(m.group(1)) if m else None


def pack(units, max_chars=CHUNK_CHARS, overlap=0):
    """Spojí malé časti do kúskov do max_chars, príliš dlhé rozdelí."""
    pieces = []
    for text, loc in units:
        text = text.strip()
        if not text:
            continue
        while len(text) > max_chars * 1.3:  # dlhú časť rozdeľ na konci riadku
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
            if overlap:  # prekryv začína na začiatku slova
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


def _shape_texts(shapes):
    for sh in shapes:
        if sh.shape_type == 6 and hasattr(sh, "shapes"):  # skupina tvarov
            yield from _shape_texts(sh.shapes)
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
        # názov prednášky = prvé dva riadky titulného slajdu
        lines = [l.strip() for t in _shape_texts(slides[0].shapes) for l in clean(t).splitlines() if l.strip()]
        deck_title = " – ".join(lines[:2])[:120]
    out = []
    for i, slide in enumerate(slides, start=1):
        parts = list(_shape_texts(slide.shapes))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                parts.append(f"Poznámky prednášajúceho: {notes}")
        text = re.sub(r"(^|\n)\d{1,3}(?=\n|$)", "", clean("\n".join(parts))).strip()  # bez čísla slajdu
        if len(text) < 40:  # titulné a prázdne slajdy
            continue
        out.append({"text": text, "loc": f"slajd {i}", "format": "slajd", "title": deck_title})
    return out


def read_ipynb(path):
    with open(path, encoding="utf-8") as f:
        nb = json.load(f)
    units = []
    for i, cell in enumerate(nb.get("cells", []), start=1):
        src = cell.get("source", "")
        src = "".join(src) if isinstance(src, list) else str(src)
        if not src.strip():
            continue
        if cell.get("cell_type") == "code":
            src = f"```python\n{src.strip()}\n```"
        units.append((src, i))
    return [{"text": t, "loc": loc_range(l, "bunka"), "format": "notebook"} for t, l in pack(units)]


def read_py(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    blocks = re.split(r"\n\s*\n(?=\S)", text)
    units, line = [], 1
    for b in blocks:
        units.append((b, line))
        line += b.count("\n") + 2
    return [{"text": f"```python\n{t.strip()}\n```", "loc": loc_range(l, "riadok"), "format": "kod"}
            for t, l in pack(units)]


def read_md(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    sections = re.split(r"\n(?=#{1,3} )", text)
    return [{"text": clean(t), "loc": f"časť {i + 1}", "format": "text"}
            for i, (t, _) in enumerate(pack([(s, None) for s in sections]))]


def read_pdf(path):
    from pypdf import PdfReader
    reader = PdfReader(path)
    title = None
    try:
        title = (reader.metadata or {}).get("/Title") if reader.metadata else None
    except Exception:
        title = None
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


def _read_zip(path):
    """Podporované súbory z archívu (bez rozbaľovania na disk pod pôvodnými menami)."""
    out = []
    total = 0
    with zipfile.ZipFile(path) as zf:
        members = [m for m in zf.infolist() if not m.is_dir()][:ZIP_MAX_FILES]
        for m in members:
            name = m.filename
            parts = set(re.split(r"[\\/]", name))
            if parts & {"__MACOSX", ".ipynb_checkpoints", "__pycache__"}:
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in EXTS:
                continue
            total += m.file_size
            if total > ZIP_MAX_BYTES:
                break
            data = zf.read(m)
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            try:
                for piece in READERS[ext](tmp_path):
                    piece["member"] = name.replace("\\", "/").split("/")[-1]
                    if piece.get("loc"):
                        piece["loc"] = f"{piece['member']}, {piece['loc']}"
                    else:
                        piece["loc"] = piece["member"]
                    out.append(piece)
            finally:
                os.unlink(tmp_path)
    return out


def read_file(path, original_name):
    ext = os.path.splitext(original_name)[1].lower()
    if ext == ".zip":
        return _read_zip(path)
    if ext not in READERS:
        raise ValueError(f"Nepodporovaný typ súboru: {ext}")
    return READERS[ext](path)


def chunk_material(path, material):
    """Kúsky jedného materiálu (zoznam slovníkov pripravených na index)."""
    pieces = read_file(path, material.original_name)
    seen, out = set(), []
    for p in pieces:
        text = p["text"]
        if len(text) < MIN_CHUNK_CHARS:
            continue
        digest = hashlib.sha1(f"{material.id}:{re.sub(r'\s+', ' ', text)}".encode()).hexdigest()[:16]
        if digest in seen:
            continue
        seen.add(digest)
        out.append({
            "id": digest,
            "material_id": material.id,
            "typ": material.kind,
            "format": p["format"],
            "subor": material.original_name,
            "nazov": material.title or p.get("title") or os.path.splitext(material.original_name)[0],
            "poloha": p.get("loc") or "",
            "prednaska": material.lecture_no if material.kind == "prednaska" else None,
            "jazyk": guess_lang(text),
            "text": text,
        })
    return out


def sha256_of(fileobj):
    h = hashlib.sha256()
    pos = fileobj.tell()
    for block in iter(lambda: fileobj.read(1024 * 1024), b""):
        h.update(block)
    fileobj.seek(pos)
    return h.hexdigest()


def first_slide_title(path, original_name):
    """Navrhnutý názov materiálu (titulný slajd pptx / metadáta pdf), inak None."""
    ext = os.path.splitext(original_name)[1].lower()
    try:
        if ext == ".pptx":
            from pptx import Presentation
            slides = list(Presentation(path).slides)
            if slides:
                lines = [l.strip() for t in _shape_texts(slides[0].shapes)
                         for l in clean(t).splitlines() if l.strip()]
                return " – ".join(lines[:2])[:200] or None
        if ext == ".pdf":
            from pypdf import PdfReader
            meta = PdfReader(path).metadata
            title = meta.get("/Title") if meta else None
            return str(title)[:200] if title else None
    except Exception:
        return None
    return None

