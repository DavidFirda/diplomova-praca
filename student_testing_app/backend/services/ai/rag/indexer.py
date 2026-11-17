# ============================================================
# AdaptPy RAG - indexovanie materiálov (na pozadí) a vyhľadávanie pre asistenta.
#
# Po nahratí súboru admin nečaká: vlákno prečíta materiál, rozdelí ho na kúsky,
# vypočíta vektory cez Ollamu (bge-m3) a zapíše ich do indexu. Stav vidno v admin
# rozhraní (pending -> indexing -> ready / error). Ak worker medzitým spadne,
# materiál ostane v stave "indexing" a admin ho môže reindexovať.
# ============================================================
import os
import threading
import time
from datetime import datetime, timezone

import numpy as np
from flask import current_app

from models import db
from models_ai import CourseMaterial
from services.ai import config as ai_config
from services.ai import llm
from services.ai.rag import readers, store

EMBED_BATCH = 16
EMBED_TEXT_MAX = 6000


def material_path(cfg, material):
    return os.path.join(cfg.materials_dir, material.stored_name)


def embed_text(chunk):
    # k textu dám názov a polohu, nech vektor vie, odkiaľ kúsok je
    return f"{chunk['nazov']} ({chunk['poloha']})\n{chunk['text']}"[:EMBED_TEXT_MAX]


def _normalize(vectors):
    vectors = np.asarray(vectors, dtype=np.float32)
    return vectors / (np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-12)


def index_material(material_id):
    """Synchrónne zaindexuje jeden materiál (volá sa vo vlákne alebo z CLI)."""
    cfg = ai_config.load()
    m = db.session.get(CourseMaterial, material_id)
    if m is None:
        return
    m.status, m.error = "indexing", None
    db.session.commit()
    path = material_path(cfg, m)
    try:
        chunks = readers.chunk_material(path, m)
        if not chunks:
            raise ValueError("V súbore sa nenašiel žiadny text (je to sken alebo prázdny súbor?).")
        vectors = []
        for i in range(0, len(chunks), EMBED_BATCH):
            batch = chunks[i:i + EMBED_BATCH]
            vectors.extend(llm.embed(cfg, [embed_text(c) for c in batch], keep_alive="5m"))
        store.write_material(cfg.index_dir, cfg.embed_model, m.id, chunks, _normalize(vectors))
        m = db.session.get(CourseMaterial, material_id)
        if m is None:                     # medzitým zmazaný
            store.remove_material(cfg.index_dir, material_id)
            return
        m.status, m.chunks, m.error = "ready", len(chunks), None
        m.embed_model = cfg.embed_model
        m.indexed_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception as e:  # noqa: BLE001 - každá chyba sa ukáže adminovi
        db.session.rollback()
        m = db.session.get(CourseMaterial, material_id)
        if m is not None:
            m.status, m.error = "error", str(e)[:1000]
            db.session.commit()
        current_app.logger.exception("Indexovanie materiálu %s zlyhalo", material_id)


def index_in_background(material_ids):
    """Spustí indexovanie vo vlákne (postupne, aby sa Ollama nezahltila)."""
    app = current_app._get_current_object()
    ids = list(material_ids)

    def run():
        with app.app_context():
            for mid in ids:
                index_material(mid)
                time.sleep(0.05)
            db.session.remove()

    t = threading.Thread(target=run, name="rag-indexer", daemon=True)
    t.start()
    return t


# ------------------------------------------------------------
# Vyhľadávanie pre asistenta
# ------------------------------------------------------------
def usable_materials():
    rows = (CourseMaterial.query
            .filter(CourseMaterial.use_in_assistant.is_(True), CourseMaterial.status == "ready")
            .order_by(CourseMaterial.kind.desc(), CourseMaterial.lecture_no, CourseMaterial.id).all())
    return [{"id": m.id, "kind": m.kind, "title": m.title, "lecture_no": m.lecture_no, "weight": m.weight}
            for m in rows]


def current_index(cfg):
    return store.get_index(cfg.index_dir, cfg.embed_model, usable_materials())


def retrieve(cfg, question, extra_queries=(), k=None, min_lectures=2, kinds=None):
    """
    -> (kúsky, info). Pri nedostupnom embedding modeli sa hľadá len cez BM25
    (info["vectors"] = False), asistent tak funguje aj bez vektorov.
    """
    info = {"query": question, "extra_queries": [q for q in extra_queries if q], "vectors": True,
            "chunks_total": 0, "error": None}
    try:
        index = current_index(cfg)
    except Exception as e:  # noqa: BLE001
        info["error"] = f"index: {e}"
        return [], info
    info["chunks_total"] = len(index)
    if not len(index):
        return [], info

    failed = {"v": False}

    def embed_fn(text):
        if failed["v"]:
            return None
        try:
            v = np.asarray(llm.embed(cfg, [text], timeout=60)[0], dtype=np.float32)
            return v / (np.linalg.norm(v) + 1e-12)
        except llm.LlmUnavailable as e:
            failed["v"] = True
            info["error"] = str(e)
            return None

    results = store.search(index, question, embed_fn=embed_fn, k=k or cfg.rag_k,
                           extra_queries=extra_queries, min_lectures=min_lectures, kinds=kinds)
    info["vectors"] = index.vectors is not None and not failed["v"]
    return results, info
