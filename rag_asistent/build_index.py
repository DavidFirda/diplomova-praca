"""Vektory pre index/chunks.jsonl cez ollamu, prepocita len nove kusky."""
import argparse
import json
import time

import numpy as np
import requests

from config import EMBED_MODEL, INDEX, OLLAMA


def embed_text(rec):
    # k textu dam nazov a polohu, nech vektor vie odkial kusok je
    return f"{rec['nazov']} ({rec['poloha']})\n{rec['text']}"[:6000]


def embed(model, texts):
    r = requests.post(f"{OLLAMA}/api/embed", json={"model": model, "input": texts}, timeout=600)
    r.raise_for_status()
    return r.json()["embeddings"]


def model_dir(model):
    return INDEX / model.replace(":", "_").replace("/", "_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=EMBED_MODEL)
    ap.add_argument("--batch", type=int, default=16)
    args = ap.parse_args()

    chunks = [json.loads(l) for l in (INDEX / "chunks.jsonl").open(encoding="utf-8")]
    out = model_dir(args.model)
    out.mkdir(parents=True, exist_ok=True)

    cache = {}
    if (out / "ids.json").exists():  # uz vypocitane vektory netreba znova
        old_ids = json.loads((out / "ids.json").read_text())
        old_vecs = np.load(out / "vectors.npy")
        cache = dict(zip(old_ids, old_vecs))

    todo = [c for c in chunks if c["id"] not in cache]
    print(f"{len(chunks)} kúskov, z toho {len(todo)} treba prepočítať (model {args.model})")
    t0 = time.time()
    for i in range(0, len(todo), args.batch):
        batch = todo[i:i + args.batch]
        for c, v in zip(batch, embed(args.model, [embed_text(c) for c in batch])):
            cache[c["id"]] = np.asarray(v, dtype=np.float32)
        done = i + len(batch)
        rate = done / max(time.time() - t0, 1e-9)
        print(f"\r  {done}/{len(todo)}  ({rate:.1f} kúskov/s)", end="", flush=True)
    print()

    ids = [c["id"] for c in chunks]
    vecs = np.stack([cache[i] for i in ids])
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12  # kosinusova podobnost
    np.save(out / "vectors.npy", vecs)
    (out / "ids.json").write_text(json.dumps(ids))
    (out / "info.json").write_text(json.dumps(
        {"model": args.model, "kuskov": len(ids), "dimenzia": int(vecs.shape[1]),
         "vytvorene": time.strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False, indent=2))
    print(f"Hotovo za {time.time() - t0:.0f} s -> {out}")


if __name__ == "__main__":
    main()
