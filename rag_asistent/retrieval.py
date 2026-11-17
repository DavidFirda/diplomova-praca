"""Hladanie v materialoch: vektory + BM25, spojene cez RRF a vahy zdrojov."""
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict

import numpy as np
import requests

from config import EMBED_MODEL, INDEX, OLLAMA, SOURCES

STOP = set("""a aj ako ale alebo ani je sa si sme ste su na do od po pri pre pod nad za z zo v vo
k ku o so to ten tá tie co čo ze že by bol bola byt byť mam mám ma ako preco prečo kde ked keď
the a an is are of to in on for and or with as by be it this that what how why do does can""".split())
WEIGHTS = {s["typ"]: s["vaha"] for s in SOURCES.values()}
RRF_K = 60


def tokens(text):
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))  # bez diakritiky
    words = re.findall(r"[a-z_][a-z0-9_]+", text)
    # orezanie na 6 znakov ako jednoduche stemovanie (funkcia/funkcie/funkciou)
    return [w[:6] for w in words if w not in STOP]


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b, self.n = k1, b, len(docs)
        tfs = [Counter(tokens(d)) for d in docs]
        lengths = np.array([sum(t.values()) for t in tfs], dtype=float)
        avg = lengths.mean() if len(lengths) else 1.0
        self.norm = k1 * (1 - b + b * lengths / avg)
        post = defaultdict(lambda: ([], []))
        for i, tf in enumerate(tfs):
            for w, f in tf.items():
                post[w][0].append(i)
                post[w][1].append(f)
        self.post = {w: (np.array(ids), np.array(fs, dtype=float)) for w, (ids, fs) in post.items()}
        self.idf = {w: math.log(1 + (self.n - len(ids) + 0.5) / (len(ids) + 0.5)) for w, (ids, _) in self.post.items()}

    def scores(self, query):
        s = np.zeros(self.n)
        for w in set(tokens(query)):
            if w in self.post:
                ids, f = self.post[w]
                s[ids] += self.idf[w] * f * (self.k1 + 1) / (f + self.norm[ids])
        return s


def query_text(model, question):
    # qwen embedding chce instrukciu, bge-m3 nie
    if "qwen" in model.lower():
        return ("Instruct: Given a student's question about a Python programming course, "
                f"retrieve course material that answers it\nQuery: {question}")
    return question


class Retriever:
    def __init__(self, embed_model=EMBED_MODEL):
        self.model = embed_model
        self.chunks = [json.loads(l) for l in (INDEX / "chunks.jsonl").open(encoding="utf-8")]
        self.bm25 = BM25([f"{c['nazov']} {c['text']}" for c in self.chunks])
        self.vectors = None
        vdir = INDEX / embed_model.replace(":", "_").replace("/", "_")
        if (vdir / "vectors.npy").exists():
            ids = json.loads((vdir / "ids.json").read_text())
            if ids == [c["id"] for c in self.chunks]:
                self.vectors = np.load(vdir / "vectors.npy")
            else:
                print("[!] chunks.jsonl sa zmenil od posledného build_index.py -> len BM25")
        else:
            print(f"[!] chýbajú vektory pre {embed_model} (spusti build_index.py) -> len BM25")

    def _embed_query(self, question):
        r = requests.post(f"{OLLAMA}/api/embed",
                          json={"model": self.model, "input": [query_text(self.model, question)]}, timeout=120)
        r.raise_for_status()
        v = np.asarray(r.json()["embeddings"][0], dtype=np.float32)
        return v / (np.linalg.norm(v) + 1e-12)

    def search(self, question, k=5, typy=None, do_prednasky=None, bez_knih=False, pool=50,
               extra_queries=(), min_prednasky=2):
        """typy napr. {"prednaska"}, do_prednasky = len prednasky <= N,
        extra_queries = dalsie znenia otazky (preklad), min_prednasky = kolko kuskov z prednasok vzdy"""
        base = np.array([
            (not typy or c["typ"] in typy)
            and not (bez_knih and c["typ"] == "kniha")
            and not (do_prednasky is not None and c["prednaska"] is not None and c["prednaska"] > do_prednasky)
            for c in self.chunks])
        types = np.array([c["typ"] for c in self.chunks])

        signals = []
        for q in (question, *extra_queries):
            label = "" if q == question else "'"
            signals.append(("bm25" + label, self.bm25.scores(q)))
            if self.vectors is not None:
                signals.append(("vektor" + label, self.vectors @ self._embed_query(q)))

        def rrf(allowed):
            fused, ranks = np.zeros(len(self.chunks)), {}
            for name, s in signals:
                s = np.where(allowed, s, -np.inf)
                for rank, i in enumerate(np.argsort(-s)[:pool]):
                    if np.isfinite(s[i]) and s[i] > 0:
                        fused[i] += 1 / (RRF_K + rank + 1)
                        ranks.setdefault(i, {})[name] = rank + 1
            return fused / len(signals), ranks

        fused, ranks = rrf(base)
        fused *= np.array([WEIGHTS.get(c["typ"], 1.0) for c in self.chunks])
        order = [i for i in np.argsort(-fused) if fused[i] > 0]
        lectures = [i for i in order if types[i] == "prednaska"][:min_prednasky]

        if len(lectures) < min_prednasky:  # ziadna prednaska medzi kandidatmi -> doplnim najlepsie zvlast
            lec_fused, lec_ranks = rrf(base & (types == "prednaska"))
            extra = [i for i in np.argsort(-lec_fused) if lec_fused[i] > 0 and i not in lectures]
            for i in extra[:min_prednasky - len(lectures)]:
                lectures.append(i)
                fused[i] = 0.0  # skore 0 = doplnene kvoli minimu
                ranks[i] = {f"{n} (len prednášky)": r for n, r in lec_ranks[i].items()}

        best = lectures + [i for i in order if i not in lectures][:k - len(lectures)]
        best.sort(key=lambda i: -fused[i])
        return [dict(self.chunks[i], skore=round(float(fused[i]) * 1000, 2), poradie=ranks.get(i, {}))
                for i in best]
