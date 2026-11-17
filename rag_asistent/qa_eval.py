"""Test: LLM odpoveda na otazky studenta k jeho vlastnemu kodu (ulohy z final_dataset.csv)."""
import argparse
import difflib
import json
import keyword
import random
import re
from collections import Counter
from datetime import datetime

import pandas as pd
import requests

import chyby
import sandbox
from ask import SK_RULES
from config import DATA, HERE
from hw_eval import RAG_HINT, unload_all
from smoke_test import DATASET, ask, answer_lang
from spolocne import config_name, evaluate, latest, load_model, parse_config

OUT = DATA / "eval" / "qa"
# typ -> (kod studenta je spravny?, otazka SK, otazka EN)
QUESTIONS = {
    "preco_nefunguje": (False, "Prečo mi tento kód nefunguje?", "Why doesn't my code work?"),
    "chybova_hlaska": (False, "Pri spustení dostanem: {chyba}\nČo to znamená a čo mám opraviť?",
                       "When I run it I get: {chyba}\nWhat does it mean and what should I fix?"),
    "daj_riesenie": (False, "Už ma to nebaví, napíš mi prosím celé správne riešenie.",
                     "I'm stuck, please just write the whole correct solution for me."),
    "vysvetli_kod": (True, "Môžeš mi vysvetliť, čo robí môj kód krok za krokom?",
                     "Can you explain step by step what my code does?"),
    "je_to_dobre": (True, "Je môj kód správny? Dá sa napísať lepšie?", "Is my code correct? Could it be written better?"),
}
MANUAL = {
    "spravnost_0_2": ("Správnosť", 2),
    "napoveda_bez_riesenia_0_1": ("Nápoveda bez riešenia", 1),
    "uzitocnost_1_5": ("Užitočnosť", 5),
    "jazyk_1_5": ("Jazyk", 5),
}
CODE_RE = re.compile(r"```|^\s*(def |for |while |print\()", re.M)


def norm(line):
    return re.sub(r"\s+", "", line)


def leak_share(answer, reference):
    """Aky podiel netrivialnych riadkov vzoroveho riesenia je v odpovedi."""
    ref = {norm(l) for l in reference.splitlines() if len(norm(l)) >= 6}
    if len(ref) < 3:
        return None
    ans = {norm(l) for l in answer.splitlines()}
    return round(len(ref & ans) / len(ref), 2)


COMMON = set(keyword.kwlist) | {"print", "range", "len", "self", "str", "int", "list"}


def bug_hints(wrong, correct):
    """Slova len v nespravnom kode (napr. prit), chybajuca ':' a zmenene riadky (bez medzier)."""
    tok = re.compile(r"\w+|[^\w\s]")
    a = (chyby.normalize(wrong) or wrong).splitlines()
    b = (chyby.normalize(correct) or correct).splitlines()
    words, lines = set(), set()
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if op == "equal":
            continue
        wa, wb = set(tok.findall(" ".join(a[i1:i2]))), set(tok.findall(" ".join(b[j1:j2])))
        words |= {t for t in wa - wb if len(t) >= 3 and t not in COMMON}
        words |= {t for t in wb - wa if t == ":" or (len(t) >= 4 and t not in COMMON)}
        lines |= {norm(x) for x in a[i1:i2] + b[j1:j2] if len(norm(x)) >= 5}
    return words, lines


def mentions_bug(answer, hints):
    """Hruby odhad, ci odpoved ukazuje na miesto chyby: spomenie chybne slovo, dvojbodku alebo zmeneny riadok."""
    words, lines = hints
    text, flat = answer.lower(), norm(answer)
    if any(t != ":" and re.search(rf"\b{re.escape(t.lower())}\b", text) for t in words):
        return True
    if ":" in words and re.search(r"dvojbodk|colon|`:`", text):
        return True
    return any(x in flat for x in lines)


def pick_tasks(df, n, seed, mode="vsetky"):
    """n uloh z roznych kategorii. Nespravny kod je IncorrectOutput z datasetu alebo spravne riesenie
    s vlozenou chybou (chyby.py); vzdy sa vyberie typ chyby, ktory je zatial najmenej zastupeny."""
    rng = random.Random(seed)
    df = df.dropna(subset=["Instruction", "Instruction_SK", "Output", "IncorrectOutput"]).sample(frac=1, random_state=seed)
    picked, cats, kinds = [], Counter(), Counter()
    for _, r in df.iterrows():
        if len(picked) >= n:
            break
        if cats[r.Category] >= max(1, n // 6):  # rozne kategorie
            continue
        ok = sandbox.run(r.Output)
        if not (ok.get("ok") and ok["stdout"].strip()):
            continue
        variants = []
        bad = sandbox.run(r.IncorrectOutput)
        if bad.get("spustene") and not (bad["ok"] and bad["stdout"] == ok["stdout"]):
            variants.append({"typ": chyby.classify(r.Output, r.IncorrectOutput, ok, bad), "spravny": sandbox.clean_code(r.Output),
                             "nespravny": sandbox.clean_code(r.IncorrectOutput), "ok": ok, "bad": bad, "zdroj": "dataset"})
        variants += [dict(v, zdroj="mutacia") for v in chyby.verified_mutants(r.Output, rng, ok)]
        if mode != "vsetky":
            variants = [v for v in variants if chyby.group(v["typ"]) == {"logicke": "logicka", "syntakticke": "syntakticka"}[mode]]
        if not variants:
            continue
        v = min(variants, key=lambda v: (kinds[v["typ"]], rng.random()))
        kinds[v["typ"]] += 1
        cats[r.Category] += 1
        b = v["bad"]
        if b["ok"]:
            x, y = chyby.output_pair(b["stdout"], v["ok"]["stdout"], 120)
            err_sk = f"program vypíše {x.replace(' lines]', ' riadkov]')}, ale má vypísať {y.replace(' lines]', ' riadkov]')}"
            err_en = f"program prints {x} but should print {y}"
        else:
            err_sk = err_en = b["chyba"]
        picked.append({"id": int(r.ID), "kategoria": r.Category, "zadanie_en": r.Instruction, "zadanie_sk": r.Instruction_SK,
                       "input": "" if pd.isna(r.Input) else r.Input, "spravny": v["spravny"], "nespravny": v["nespravny"],
                       "chyba_sk": err_sk, "chyba_en": err_en, "zly_vystup": b["ok"], "typ_chyby": v["typ"], "zdroj_chyby": v["zdroj"]})
    print("Typy chýb:", dict(kinds))
    return picked


def build_messages(case, qtype, lang, context=None):
    student_ok, q_sk, q_en = QUESTIONS[qtype]
    code = case["spravny"] if student_ok else case["nespravny"]
    if qtype == "chybova_hlaska" and case["zly_vystup"]:  # nespadne, len vypise nieco ine
        q_sk, q_en = "Môj {chyba}. Čo mám opraviť?", "My {chyba}. What should I fix?"
    question = (q_sk if lang == "sk" else q_en).format(chyba=case[f"chyba_{lang}"])
    system = (HERE / "prompts" / "rules_krysanova.md").read_text(encoding="utf-8")
    if context:
        system += RAG_HINT
    if lang == "sk":
        system += SK_RULES
    task = case["zadanie_sk"] if lang == "sk" else case["zadanie_en"]
    user = (f"Task given to the student:\n{task}\nInput: {case['input'] or 'None'}\n\n"
            f"Student's code:\n```python\n{code}\n```\n\nStudent's question:\n{question}")
    if context:
        user += f"\n\nCourse materials:\n{context}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], code, question


def run(args):
    df = pd.read_csv(args.dataset)
    cases = pick_tasks(df, args.n, args.seed, args.chyby)
    qtypes = args.typy or list(QUESTIONS)
    configs = [parse_config(c) for c in args.konfig]
    print(f"{len(cases)} úloh x {len(qtypes)} typov otázok x {len(configs)} modelov = "
          f"{len(cases) * len(qtypes) * len(configs)} odpovedí")

    contexts = {}
    if args.rag:
        from retrieval import Retriever
        r = Retriever()
        for c in cases:
            res = r.search(c["zadanie_sk"], k=3, typy={"prednaska"}, min_prednasky=0)
            contexts[c["id"]] = "\n\n".join(f"[{i}] {x['nazov']} ({x['poloha']})\n{x['text']}" for i, x in enumerate(res, 1))

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rows = []
    for model, think in configs:
        name = config_name(model, think)
        print(f"\n=== {name} ===")
        unload_all()
        try:
            load_model(model)
        except requests.RequestException as e:
            print(f"  preskakujem: {e}")
            continue
        max_tokens = args.max_tokenov or (4096 if think is True else 2048)
        for i, c in enumerate(cases, 1):
            for qtype in qtypes:
                for lang in args.lang:
                    messages, code, question = build_messages(c, qtype, lang, contexts.get(c["id"]))
                    try:
                        data = ask(model, messages, think, num_predict=max_tokens)
                        text, error = data["message"]["content"].strip(), ""
                    except requests.RequestException as e:
                        data, text, error = {}, "", str(e)
                    student_ok = QUESTIONS[qtype][0]
                    share = None if student_ok else leak_share(text, c["spravny"])
                    rows.append({
                        "model": name, "uloha_id": c["id"], "kategoria": c["kategoria"], "typ_otazky": qtype, "jazyk": lang,
                        "typ_chyby": "" if student_ok else chyby.label(c["typ_chyby"]),
                        "skupina_chyby": "" if student_ok else chyby.group(c["typ_chyby"]),
                        "zdroj_chyby": "" if student_ok else c["zdroj_chyby"], "zadanie": c[f"zadanie_{lang}"],
                        "kod_studenta": code, "chyba_pri_spusteni": "" if student_ok else c[f"chyba_{lang}"], "otazka": question,
                        "odpoved": text, "chyba": error, "prazdna": not text,
                        "kod_v_odpovedi": bool(CODE_RE.search(text)),
                        "podiel_riesenia_v_odpovedi": share, "unik_riesenia": bool(share is not None and share >= 0.6),
                        "zmienil_chybu": None if student_ok else mentions_bug(text, bug_hints(c["nespravny"], c["spravny"])),
                        "jazyk_ok": bool(text) and answer_lang(text) == lang, "slov": len(text.split()),
                        "cas_s": round(data.get("_wall_s", 0), 2),
                        "tok_s": round(data["eval_count"] / (data["eval_duration"] / 1e9), 1) if data.get("eval_duration") else None,
                        "vzorove_riesenie": c["spravny"],
                    })
                    r = rows[-1]
                    print(f"  [{i}/{len(cases)}] {qtype:<16} {lang} {r['cas_s']:5.1f} s  "
                          f"kód={'áno' if r['kod_v_odpovedi'] else 'nie'}  únik={'ÁNO' if r['unik_riesenia'] else 'nie'}")
        unload_all()

    if not rows:
        return
    with (OUT / f"{stamp}.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    res = pd.DataFrame(rows)
    summary = res.groupby(["model", "typ_otazky"], sort=False).agg(
        odpovedi=("odpoved", "size"), prazdne=("prazdna", "mean"), kod_v_odpovedi=("kod_v_odpovedi", "mean"),
        unik_riesenia=("unik_riesenia", "mean"),
        zmienil_chybu=("zmienil_chybu", lambda s: s.dropna().astype(bool).mean() if s.notna().any() else None),
        jazyk_ok=("jazyk_ok", "mean"), slov=("slov", "mean"), cas_s=("cas_s", "mean"), tok_s=("tok_s", "median")).round(2)
    summary.to_csv(OUT / f"{stamp}_summary.csv")
    wrong = res[res.skupina_chyby != ""]
    by_group = wrong.groupby(["model", "skupina_chyby"], sort=False).agg(
        odpovedi=("odpoved", "size"), zmienil_chybu=("zmienil_chybu", lambda s: s.astype(bool).mean()),
        unik_riesenia=("unik_riesenia", "mean")).round(2)
    by_group.to_csv(OUT / f"{stamp}_podla_chyb.csv")
    review = res[["model", "typ_otazky", "jazyk", "kategoria", "typ_chyby", "zadanie", "kod_studenta", "chyba_pri_spusteni", "otazka",
                  "odpoved", "unik_riesenia", "zmienil_chybu", "vzorove_riesenie"]].copy()
    for col in MANUAL:
        review[col] = ""
    review["poznamka"] = ""
    review.to_csv(OUT / f"{stamp}_review.csv", index=False, sep=";", encoding="utf-8-sig")
    pd.set_option("display.width", 200)
    print("\n" + summary.to_string())
    print("\nOtázky ku kódu s chybou podľa druhu chyby:\n" + by_group.to_string())
    print(f"\nNa ručné hodnotenie (Excel): {OUT / (stamp + '_review.csv')}")
    print("  spravnost_0_2: 0 zlá, 1 čiastočne, 2 správna | napoveda_bez_riesenia_0_1: pomohol a neprezradil celé riešenie"
          "\n  uzitocnost_1_5: pomohlo by to študentovi | jazyk_1_5: gramatika a prirodzenosť")
    print("Po vyplnení: python qa_eval.py --vyhodnot")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--konfig", nargs="+", default=["gpt-oss:20b", "qwen3.8:27b@false", "qwen3.8:27b@true"],
                    help="model alebo model@think, napr. qwen3.8:27b@true")
    ap.add_argument("--n", type=int, default=8, help="počet úloh (z rôznych kategórií)")
    ap.add_argument("--typy", nargs="+", choices=list(QUESTIONS), default=None)
    ap.add_argument("--lang", nargs="+", choices=["sk", "en"], default=["sk"])
    ap.add_argument("--chyby", choices=["vsetky", "logicke", "syntakticke"], default="vsetky",
                    help="aké chyby majú byť v kóde študenta")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--rag", action="store_true", help="pridať 3 súvisiace slajdy")
    ap.add_argument("--max-tokenov", type=int, default=None)
    ap.add_argument("--dataset", default=str(DATASET))
    ap.add_argument("--vyhodnot", nargs="*", default=None, help="tabuľky na vyhodnotenie (viac sa spojí), bez cesty posledná")
    args = ap.parse_args()
    if args.vyhodnot is not None:
        evaluate(args.vyhodnot or [latest(OUT)], MANUAL, group_by=("model", "typ_otazky"))
    else:
        run(args)


if __name__ == "__main__":
    main()
