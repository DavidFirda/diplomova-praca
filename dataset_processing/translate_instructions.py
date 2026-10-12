"""
    pip install argostranslate
    python translate_instructions.py                    # offline engine Argos (en->sk)
    DEEPL_API_KEY=... python translate_instructions.py --engine deepl
    python translate_instructions.py --limit 20        
    python translate_instructions.py --sample 100       
"""
import argparse
import csv
import json
import os
import random
import re
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "..", "student_testing_app", "final_dataset.csv")
CACHE = os.path.join(HERE, "translate_cache.jsonl")
SAMPLE_OUT = os.path.join(HERE, "translation_sample.csv")

SK_COLUMN = "Instruction_SK"
REVIEW_COLUMN = "TranslationReview"
ENGINES = ("argos", "deepl", "mock")

# `kód`, "text", 'text' (apostrof v slove ako don't sa nepočíta)
_PROTECT_RE = re.compile(r"`[^`\n]+`|\"[^\"\n]+\"|(?<!\w)'[^'\n]+'(?!\w)")
_TOKEN = "QQ{}QQ"


# ------------------------------------------------------------
# Ochrana častí, ktoré sa nemajú prekladať
# ------------------------------------------------------------
def protect(text):
    """Nahradí chránené časti zástupnými znakmi. Vráti (text, zoznam pôvodných častí)."""
    spans = []

    def repl(match):
        spans.append(match.group(0))
        return _TOKEN.format(len(spans) - 1)

    return _PROTECT_RE.sub(repl, text), spans


def restore(text, spans):
    """Vráti chránené časti späť; None, ak niektorý zástupný znak chýba/je navyše."""
    for i, original in enumerate(spans):
        if text.count(_TOKEN.format(i)) != 1:
            return None
        text = text.replace(_TOKEN.format(i), original)
    return text


# ------------------------------------------------------------
# Engines
# ------------------------------------------------------------
def make_engine(name):
    """Vráti funkciu translate(list[str]) -> list[str]."""
    if name == "mock":                       # len na skúšku pipeline bez prekladača
        return lambda texts: [f"[SK] {t}" for t in texts]

    if name == "argos":
        try:
            import argostranslate.package as package
            import argostranslate.translate as translate
        except ImportError:
            sys.exit("Chýba balík: pip install argostranslate")
        langs = {l.code: l for l in translate.get_installed_languages()}
        en, sk = langs.get("en"), langs.get("sk")
        if not (en and sk and en.get_translation(sk)):
            print("[argos] sťahujem jazykový balík en->sk ...")
            package.update_package_index()
            pkg = next((p for p in package.get_available_packages()
                        if p.from_code == "en" and p.to_code == "sk"), None)
            if pkg is None:
                sys.exit("Argos nemá balík en->sk.")
            package.install_from_path(pkg.download())
        return lambda texts: [translate.translate(t, "en", "sk") for t in texts]

    if name == "deepl":
        import requests
        key = os.getenv("DEEPL_API_KEY")
        if not key:
            sys.exit("Nastav premennú prostredia DEEPL_API_KEY.")
        url = "https://api-free.deepl.com/v2/translate" if key.endswith(":fx") \
            else "https://api.deepl.com/v2/translate"

        def deepl(texts):
            wait = 2.0
            for attempt in range(8):
                r = requests.post(
                    url, timeout=60,
                    headers={"Authorization": f"DeepL-Auth-Key {key}"},
                    json={"text": texts, "source_lang": "EN", "target_lang": "SK",
                          "preserve_formatting": True},
                )
                if r.status_code == 456:
                    sys.exit("\nDeepL: vyčerpaný mesačný limit znakov (chyba 456). "
                             "Hotové preklady sú v cache - spusti znova po obnovení limitu.")
                if r.status_code in (429, 503):          # príliš veľa požiadaviek / dočasný výpadok
                    delay = float(r.headers.get("Retry-After", wait))
                    print(f"\n  DeepL {r.status_code} - čakám {delay:.0f}s (pokus {attempt + 1}/8)")
                    time.sleep(delay)
                    wait = min(wait * 2, 60)
                    continue
                r.raise_for_status()
                time.sleep(0.5)                           # nezahlcovať API
                return [t["text"] for t in r.json()["translations"]]
            sys.exit("\nDeepL stále odmieta požiadavky (429). Skús to znova o pár minút - "
                     "hotové preklady sú v cache.")
        return deepl

    sys.exit(f"Neznámy engine: {name} (možnosti: {', '.join(ENGINES)})")


def split_instruction(text):
    """Prvý riadok je veta na preklad, zvyšok (kód) ostáva nedotknutý."""
    head, sep, tail = text.partition("\n")
    return head, sep + tail


def translate_all(instructions, translate, batch_size=16):
    """Generátor: po každej dávke vráti (hotovo, spolu, {id: (text_sk, needs_review)}),
    aby sa výsledok dal hneď uložiť - pri páde sa nestratí už preložené."""
    prepared = {}
    for qid, text in instructions.items():
        head, tail = split_instruction(text)
        protected, spans = protect(head)
        prepared[qid] = (protected, spans, tail, head)

    ids = list(prepared)
    for start in range(0, len(ids), batch_size):
        chunk = ids[start:start + batch_size]
        outputs = translate([prepared[i][0] for i in chunk])

        results, retry = {}, []
        for qid, out in zip(chunk, outputs):
            _, spans, tail, _ = prepared[qid]
            restored = restore(out, spans)
            if restored is None:
                retry.append(qid)
            else:
                results[qid] = (restored + tail, int("\n" in tail))
        if retry:                            # zástupné znaky sa stratili -> preklad bez ochrany
            raw = translate([prepared[i][3] for i in retry])
            for qid, text in zip(retry, raw):
                results[qid] = (text + prepared[qid][2], 1)
        yield start + len(chunk), len(ids), results


def load_cache():
    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                cache[(row["engine"], row["source"])] = row
    return cache


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", choices=ENGINES, default="argos")
    ap.add_argument("--limit", type=int, help="preložiť len prvých N úloh (skúška)")
    ap.add_argument("--sample", type=int, default=0, help="uložiť náhodnú vzorku N prekladov na kontrolu")
    ap.add_argument("--batch-size", type=int, default=16, help="počet zadaní v jednej požiadavke (pri 429 skús menej)")
    ap.add_argument("--dataset", default=DATASET)
    args = ap.parse_args()

    csv.field_size_limit(10 ** 9)
    with open(args.dataset, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    targets = rows[: args.limit] if args.limit else rows
    cache = load_cache()
    todo = {r["ID"]: r["Instruction"] for r in targets
            if (args.engine, r["Instruction"]) not in cache}
    print(f"úloh: {len(rows)} | na preklad: {len(todo)} | z cache: {len(targets) - len(todo)}")

    if todo:
        translate = make_engine(args.engine)
        with open(CACHE, "a", encoding="utf-8") as cache_file:
            for done, total, results in translate_all(todo, translate, args.batch_size):
                for qid, (text_sk, review) in results.items():
                    cache_file.write(json.dumps({"engine": args.engine, "source": todo[qid],
                                                 "sk": text_sk, "review": review}, ensure_ascii=False) + "\n")
                cache_file.flush()                       
                print(f"\r  {done}/{total}", end="", flush=True)
        print()
        cache = load_cache()

    for col in (SK_COLUMN, REVIEW_COLUMN):
        if col not in fieldnames:
            fieldnames.append(col)
    review_count = 0
    for r in targets:
        hit = cache[(args.engine, r["Instruction"])]
        r[SK_COLUMN], r[REVIEW_COLUMN] = hit["sk"], hit["review"]
        review_count += hit["review"]

    # zápis cez dočasný súbor - pri páde sa pôvodný dataset nepoškodí
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(args.dataset)), suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, args.dataset)
    print(f"zapísané do {os.path.normpath(args.dataset)} | na ručnú kontrolu: {review_count}")

    if args.sample:
        picked = random.Random(42).sample(targets, min(args.sample, len(targets)))
        with open(SAMPLE_OUT, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ID", "Instruction", SK_COLUMN, "Hodnotenie (1-5)"])
            for r in picked:
                w.writerow([r["ID"], r["Instruction"], r[SK_COLUMN], ""])
        print(f"vzorka na kontrolu: {SAMPLE_OUT}")


if __name__ == "__main__":
    main()
