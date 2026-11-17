# ============================================================
# AdaptPy RAG - index na disku a vyhľadávanie.
#
# Rozloženie v RAG_INDEX_DIR (volume, nejde na git):
#   chunks/<material_id>.jsonl              kúsky textu s metadátami
#   vectors/<embed_model>/<material_id>.npy normalizované vektory (riadky = kúsky)
#   version.txt                             zmení sa pri každej úprave indexu
#
# Každý gunicorn worker si index načíta do pamäte a znovu ho načíta, keď sa zmení
# version.txt (admin pridal/zmazal materiál). Vyhľadávanie je port retrieval.py
# z rag_asistent: vektory (bge-m3) + BM25, spojené cez RRF, vynásobené váhou zdroja
# (prednášky 1,0, knihy 0,6) a vo výsledku je vždy aspoň `min_lectures` slajdov.
# ============================================================
import json
import math
import os
import re
import threading
import time
import unicodedata
from collections import Counter, defaultdict

import numpy as np

DEFAULT_WEIGHTS = {"prednaska": 1.0, "kniha": 0.6}
KIND_LABEL = {"prednaska": "Prednáška", "kniha": "Kniha"}
RRF_K = 60
POOL = 50

STOP = set("""a aj ako ale alebo ani je sa si sme ste su na do od po pri pre pod nad za z zo v vo
k ku o so to ten tá tie co čo ze že by bol bola byt byť mam mám ma ako preco prečo kde ked keď
the a an is are of to in on for and or with as by be it this that what how why do does can""".split())


# ------------------------------------------------------------
# Súbory indexu
# ------------------------------------------------------------
def _safe(model):
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", model)


def chunks_path(index_dir, material_id):
    return os.path.join(index_dir, "chunks", f"{int(material_id)}.jsonl")


def vectors_path(index_dir, embed_model, material_id):
    return os.path.join(index_dir, "vectors", _safe(embed_model), f"{int(material_id)}.npy")


def bump_version(index_dir):
    os.makedirs(index_dir, exist_ok=True)
    tmp = os.path.join(index_dir, f".version.{os.getpid()}.tmp")
    with open(tmp, "w") as f:
        f.write(f"{time.time():.6f}")
    os.replace(tmp, os.path.join(index_dir, "version.txt"))


def read_version(index_dir):
    try:
        with open(os.path.join(index_dir, "version.txt")) as f:
            return f.read().strip()
    except OSError:
        return ""


def write_material(index_dir, embed_model, material_id, chunks, vectors):
    """Atomicky zapíše kúsky aj vektory jedného materiálu."""
    cpath = chunks_path(index_dir, material_id)
    vpath = vectors_path(index_dir, embed_model, material_id)
    os.makedirs(os.path.dirname(cpath), exist_ok=True)
    os.makedirs(os.path.dirname(vpath), exist_ok=True)
    tmp_c = cpath + ".tmp"
    with open(tmp_c, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    tmp_v = vpath + ".tmp.npy"
    np.save(tmp_v, vectors.astype(np.float32))
    os.replace(tmp_v, vpath)
    os.replace(tmp_c, cpath)
    bump_version(index_dir)


def remove_material(index_dir, material_id):
    for root in (os.path.join(index_dir, "chunks"), os.path.join(index_dir, "vectors")):
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                if name in (f"{int(material_id)}.jsonl", f"{int(material_id)}.npy"):
                    try:
                        os.remove(os.path.join(dirpath, name))
                    except OSError:
                        pass
    bump_version(index_dir)


def load_material(index_dir, embed_model, material_id):
    """(kúsky, vektory | None)."""
    cpath = chunks_path(index_dir, material_id)
    if not os.path.exists(cpath):
        return [], None
    with open(cpath, encoding="utf-8") as f:
        chunks = [json.loads(l) for l in f if l.strip()]
    vpath = vectors_path(index_dir, embed_model, material_id)
    vectors = None
    if os.path.exists(vpath):
        vectors = np.load(vpath)
        if len(vectors) != len(chunks):
            vectors = None
    return chunks, vectors


# ------------------------------------------------------------
# BM25 (presné slová: názvy funkcií, pojmy)
# ------------------------------------------------------------
def tokens(text):
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))  # bez diakritiky
    words = re.findall(r"[a-z_][a-z0-9_]+", text)
    # orezanie na 6 znakov ako jednoduché stemovanie (funkcia/funkcie/funkciou)
    return [w[:6] for w in words if w not in STOP]


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b, self.n = k1, b, len(docs)
        tfs = [Counter(tokens(d)) for d in docs]
        lengths = np.array([sum(t.values()) for t in tfs], dtype=float)
        avg = lengths.mean() if len(lengths) and lengths.mean() > 0 else 1.0
        self.norm = k1 * (1 - b + b * lengths / avg)
        post = defaultdict(lambda: ([], []))
        for i, tf in enumerate(tfs):
            for w, f in tf.items():
                post[w][0].append(i)
                post[w][1].append(f)
        self.post = {w: (np.array(ids), np.array(fs, dtype=float)) for w, (ids, fs) in post.items()}
        self.idf = {w: math.log(1 + (self.n - len(ids) + 0.5) / (len(ids) + 0.5))
                    for w, (ids, _) in self.post.items()}

    def scores(self, query):
        s = np.zeros(self.n)
        for w in set(tokens(query)):
            if w in self.post:
                ids, f = self.post[w]
                s[ids] += self.idf[w] * f * (self.k1 + 1) / (f + self.norm[ids])
        return s


def query_text(model, question):
    # qwen embedding chce inštrukciu, bge-m3 nie
    if "qwen" in model.lower():
        return ("Instruct: Given a student's question about a Python programming course, "
                f"retrieve course material that answers it\nQuery: {question}")
    return question


# ------------------------------------------------------------
# Index v pamäti
# ------------------------------------------------------------
class Index:
    """Všetky kúsky povolených materiálov + BM25 + vektory (ak sú pre všetky kúsky)."""

    def __init__(self, index_dir, embed_model, materials):
        self.embed_model = embed_model
        self.chunks, vec_parts = [], []
        all_vectors = True
        self.weights = []
        for m in materials:
            chunks, vectors = load_material(index_dir, embed_model, m["id"])
            if not chunks:
                continue
            weight = m["weight"] if m.get("weight") is not None else DEFAULT_WEIGHTS.get(m["kind"], 1.0)
            for c in chunks:
                c["material_id"] = m["id"]
                c["typ"] = m["kind"]
                c["nazov"] = m.get("title") or c.get("nazov")
                c["prednaska"] = m.get("lecture_no") if m["kind"] == "prednaska" else None
            self.chunks.extend(chunks)
            self.weights.extend([weight] * len(chunks))
            if vectors is None:
                all_vectors = False
            else:
                vec_parts.append(vectors)
        self.weights = np.array(self.weights, dtype=float)
        self.types = np.array([c["typ"] for c in self.chunks])
        self.bm25 = BM25([f"{c['nazov']} {c['text']}" for c in self.chunks])
        self.vectors = np.vstack(vec_parts) if (all_vectors and vec_parts) else None

    def __len__(self):
        return len(self.chunks)


_cache = {"key": None, "index": None}
_cache_lock = threading.Lock()


def get_index(index_dir, embed_model, materials):
    """Index z cache; znovu sa načíta pri zmene version.txt alebo zoznamu materiálov."""
    key = (read_version(index_dir), embed_model,
           tuple((m["id"], m.get("weight"), m.get("title"), m.get("lecture_no"), m["kind"]) for m in materials))
    with _cache_lock:
        if _cache["key"] != key:
            _cache["index"] = Index(index_dir, embed_model, materials)
            _cache["key"] = key
        return _cache["index"]


def search(index, question, embed_fn=None, k=5, extra_queries=(), min_lectures=2, kinds=None):
    """
    Najlepšie kúsky k otázke.
      embed_fn(text) -> normalizovaný vektor (alebo None pri chybe -> len BM25)
      extra_queries   ďalšie znenia otázky (slovenský preklad, názov sekcie cvičenia ...)
      min_lectures    koľko kúskov z prednášok je vo výsledku vždy (ak existujú)
    Vráti zoznam kópií kúskov so `skore` a `poradie` (poradie v jednotlivých signáloch).
    """
    if index is None or not len(index):
        return []
    n = len(index)
    base = np.ones(n, dtype=bool)
    if kinds:
        base &= np.isin(index.types, list(kinds))

    signals = []
    for q in (question, *[e for e in extra_queries if e]):
        label = "" if q == question else "'"
        signals.append(("bm25" + label, index.bm25.scores(q)))
        if index.vectors is not None and embed_fn is not None:
            v = embed_fn(query_text(index.embed_model, q))
            if v is not None:
                signals.append(("vektor" + label, index.vectors @ v))
    if not signals:
        return []

    def rrf(allowed):
        fused, ranks = np.zeros(n), {}
        for name, s in signals:
            s = np.where(allowed, s, -np.inf)
            for rank, i in enumerate(np.argsort(-s)[:POOL]):
                if np.isfinite(s[i]) and s[i] > 0:
                    fused[i] += 1 / (RRF_K + rank + 1)
                    ranks.setdefault(i, {})[name] = rank + 1
        return fused / len(signals), ranks

    fused, ranks = rrf(base)
    fused *= index.weights
    order = [i for i in np.argsort(-fused) if fused[i] > 0]
    lectures = [i for i in order if index.types[i] == "prednaska"][:min_lectures]

    if len(lectures) < min_lectures and (not kinds or "prednaska" in kinds):
        # žiadna prednáška medzi kandidátmi -> doplním najlepšie zvlášť (skóre 0)
        lec_fused, lec_ranks = rrf(base & (index.types == "prednaska"))
        extra = [i for i in np.argsort(-lec_fused) if lec_fused[i] > 0 and i not in lectures]
        for i in extra[:min_lectures - len(lectures)]:
            lectures.append(i)
            fused[i] = 0.0
            ranks[i] = {f"{name} (len prednášky)": r for name, r in lec_ranks[i].items()}

    best = lectures + [i for i in order if i not in lectures][:max(0, k - len(lectures))]
    best.sort(key=lambda i: -fused[i])
    return [dict(index.chunks[i], skore=round(float(fused[i]) * 1000, 2), poradie=ranks.get(i, {}))
            for i in best]


def source_label(chunk, lang="sk"):
    """Krátky popis zdroja pre študenta: 'Prednáška 5 · slajd 12' / 'Kniha: Python for Everybody · str. 40'."""
    if chunk.get("typ") == "prednaska":
        head = (f"Prednáška {chunk['prednaska']}" if lang == "sk" else f"Lecture {chunk['prednaska']}") \
            if chunk.get("prednaska") is not None else (chunk.get("nazov") or "Prednáška")
    else:
        head = f"{'Kniha' if lang == 'sk' else 'Book'}: {chunk.get('nazov') or chunk.get('subor')}"
    loc = chunk.get("poloha") or ""
    if lang != "sk":
        loc = loc.replace("slajd", "slide").replace("str.", "p.").replace("bunka", "cell").replace("riadok", "line")
    return f"{head} · {loc}" if loc else head
