"""Otazka -> najdene materialy, s --odpoved aj odpoved modelu so zdrojmi."""
import argparse
import json
import re
import time

import requests

from config import EMBED_MODEL, HERE, OLLAMA
from ingest import guess_lang
from retrieval import Retriever

NUM_CTX = 16384

RAG_RULES = """

COURSE MATERIALS:
Below the student's question you get numbered excerpts from the course materials
(lecture slides, lecture code, books).
- Base your answer primarily on these excerpts. Use the exact terms from the lecture slides
  (for example "členská premenná" if the slides say so) and prefer their examples over your own.
- If the student writes in another language than the slides, add the lecture term in parentheses.
- Cite the excerpts you used with their number in square brackets, e.g. [1] or [2][3].
  Put citations in the text, never inside code blocks.
- Prefer lectures over books when they say the same thing.
- If the excerpts do not contain the answer, say so in one sentence and then answer briefly from general knowledge.
- Never copy a complete solution of a homework assignment, even if an excerpt contains it."""

SK_RULES = """

LANGUAGE:
- Always answer in Slovak, regardless of the language of the excerpts.
- Keep Python keywords, function names and error names in their original form."""


def label(c):
    return f"{c['typ']} · {c['subor'].split('/')[-1]} · {c['poloha']}"


def show(results):
    for i, c in enumerate(results, start=1):
        signals = ", ".join(f"{k} #{v}" for k, v in c["poradie"].items())
        snippet = " ".join(c["text"].split())[:220]
        print(f"\n[{i}] {label(c)}   (skóre {c['skore']}; {signals})\n    {snippet}")


TRANSLATE_PROMPT = """Translate the student's question about Python programming into Slovak.
Use the Slovak terms from this course glossary (English = Slovak used in the lectures):
{glossary}
Keep Python keywords, function names and code unchanged.
Output only the Slovak question."""


SK_Q = set("""ako aky aka ake ktory ktora ktore co preco kedy kde ked je su sa si mam ma na v vo z zo s so pre pri
po do od a alebo aj ale nie rozdiel medzi funguje funguju robi znamena urobim spravim pouzit pouzivat""".split())
EN_Q = set("""how what why when where which who is are does do can the a an of in on for to and or not
difference between work works mean use""".split())


def question_lang(text):
    # bez diakritiky sa slovencina zle rozoznava podla pismen, preto aj podla slov
    if guess_lang(text) == "sk":
        return "sk"
    words = re.findall(r"[a-z]+", text.lower())
    sk, en = sum(w in SK_Q for w in words), sum(w in EN_Q for w in words)
    return "en" if en > sk else "sk"


def to_slovak(question, llm):
    """Prelozi anglicku otazku do slovenciny pojmami z glosara (inheritance -> dedenie)."""
    glossary = (HERE / "prompts" / "glosar.md").read_text(encoding="utf-8")
    payload = {"model": llm, "stream": False, "think": False if "gpt-oss" not in llm else "low",
               "options": {"temperature": 0, "num_predict": 400, "num_ctx": NUM_CTX},  # iny num_ctx = nove nacitanie modelu
               "messages": [{"role": "system", "content": TRANSLATE_PROMPT.format(glossary=glossary)},
                            {"role": "user", "content": question}]}
    r = requests.post(f"{OLLAMA}/api/chat", json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["message"]["content"].strip().strip('"')


def unload(model):
    # bez toho sa vacsi model nemusi zmestit do VRAM vedla bge-m3
    try:
        requests.post(f"{OLLAMA}/api/generate", json={"model": model, "keep_alive": 0}, timeout=60)
    except requests.RequestException:
        pass


def answer(question, results, llm, lang, think, max_tokens, echo=True):
    rules = (HERE / "prompts" / "rules_krysanova.md").read_text(encoding="utf-8") + RAG_RULES
    if lang == "sk":
        rules += SK_RULES
    context = "\n\n".join(f"[{i}] ({label(c)})\n{c['text']}" for i, c in enumerate(results, start=1))
    messages = [
        {"role": "system", "content": rules},
        {"role": "user", "content": f"Course materials:\n{context}\n\nStudent's question:\n{question}"},
    ]
    payload = {"model": llm, "messages": messages, "stream": True,
               "options": {"temperature": 0.2, "num_ctx": NUM_CTX, "num_predict": max_tokens}}
    if think is not None:
        payload["think"] = think
    t0 = time.time()
    first, parts, thinking, last = None, [], 0, {}
    with requests.post(f"{OLLAMA}/api/chat", json=payload, stream=True, timeout=600) as r:
        r.raise_for_status()
        for line in r.iter_lines(chunk_size=None):
            if not line:
                continue
            chunk = json.loads(line)
            if "error" in chunk:
                raise RuntimeError(chunk["error"])
            msg = chunk.get("message", {})
            thinking += len(msg.get("thinking") or "")
            if msg.get("content"):
                if first is None:
                    first = time.time() - t0
                if echo:
                    print(msg["content"], end="", flush=True)
                parts.append(msg["content"])
            if chunk.get("done"):
                last = chunk
    if echo:
        print()
    gen_s = last.get("eval_duration", 0) / 1e9
    stats = {"spolu": time.time() - t0, "prve_slovo": first,
             "nacitanie": last.get("load_duration", 0) / 1e9,
             "tokenov": last.get("eval_count", 0),
             "tok_s": last.get("eval_count", 0) / gen_s if gen_s else 0.0,
             "uvazovanie": thinking}
    return "".join(parts).strip(), stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("otazka", nargs="?")
    ap.add_argument("--k", type=int, default=5, help="počet nájdených kúskov")
    ap.add_argument("--typy", help="len vybrané zdroje, napr. prednaska alebo kniha")
    ap.add_argument("--bez-knih", action="store_true")
    ap.add_argument("--do-prednasky", type=int, help="len prednášky po číslo N (knihy ostanú)")
    ap.add_argument("--embed", default=EMBED_MODEL, help="embedding model (musí mať index)")
    ap.add_argument("--odpoved", action="store_true", help="vygenerovať aj odpoveď modelu")
    ap.add_argument("--llm", default="gpt-oss:20b")
    ap.add_argument("--lang", choices=["sk", "en"], default="sk")
    ap.add_argument("--think", default=None, help="low / medium / high alebo false")
    ap.add_argument("--bez-prekladu", action="store_true", help="nehľadať aj slovenský preklad anglickej otázky")
    ap.add_argument("--min-prednasky", type=int, default=2, help="min. počet kúskov z prednášok vo výsledku")
    ap.add_argument("--max-tokenov", type=int, default=None,
                    help="limit odpovede vrátane uvažovania (predvolene 800, pri --think true 4096)")
    args = ap.parse_args()
    think = {"false": False, "true": True}.get(str(args.think).lower(), args.think)
    typy = set(args.typy.split(",")) if args.typy else None
    max_tokens = args.max_tokenov or (4096 if think is True else 800)
    llm_label = args.llm + (f", think {args.think}" if args.think is not None else "")

    retriever = Retriever(args.embed)
    questions = [args.otazka] if args.otazka else iter(lambda: input("\nOtázka: ").strip(), "")
    for q in questions:
        extra, t_trans = [], 0.0
        if not args.bez_prekladu and question_lang(q) == "en":  # slajdy su po slovensky
            t0 = time.time()
            extra = [to_slovak(q, args.llm)]
            t_trans = time.time() - t0
            print(f"(hľadám aj: {extra[0]})")
        t0 = time.time()
        results = retriever.search(q, k=args.k, typy=typy, do_prednasky=args.do_prednasky,
                                   bez_knih=args.bez_knih, extra_queries=extra,
                                   min_prednasky=args.min_prednasky)
        t_search = time.time() - t0
        show(results)
        if not (args.odpoved and results):
            print(f"\n[čas] hľadanie {t_search:.1f} s")
            continue
        unload(args.embed)
        print(f"\n--- odpoveď ({llm_label}) ---")
        text, st = answer(q, results, args.llm, args.lang, think, max_tokens)
        if not text:
            print("(prázdna odpoveď: uvažovanie minulo limit tokenov, skús vyšší --max-tokenov)")
        first = f"{st['prve_slovo']:.1f} s" if st["prve_slovo"] is not None else "-"
        print("\n[čas] " + (f"preklad {t_trans:.1f} s | " if extra else "")
              + f"hľadanie {t_search:.1f} s | prvé slovo odpovede po {first} | "
              f"celá odpoveď {st['spolu']:.1f} s (načítanie modelu {st['nacitanie']:.1f} s) | "
              f"{st['tokenov']} tokenov, {st['tok_s']:.0f} tok/s"
              + (f" | uvažovanie {st['uvazovanie']} znakov" if st["uvazovanie"] else "")
              + f" | spolu {t_trans + t_search + st['spolu']:.1f} s")


if __name__ == "__main__":
    main()
