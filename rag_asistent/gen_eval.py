"""Test: LLM generuje ulohy v tvare final_dataset.csv pre danu kategoriu, bez profilu a podla chyb studenta."""
import argparse
import difflib
import json
import random
from collections import Counter
from datetime import datetime

import pandas as pd
import requests

import chyby
import sandbox
from config import DATA
from hw_eval import unload_all
from smoke_test import DATASET, ask
from spolocne import config_name, evaluate, latest, load_model, parse_config

OUT = DATA / "eval" / "gen"
CATEGORIES = ["Syntax", "Data Structures", "Mathematics", "Loops", "Branching",
              "Functions and Advanced Concepts", "Object-Oriented Programming"]
DATASET_COLS = ["ID", "Instruction", "Input", "Output", "Category", "Subcategory", "IncorrectOutput",
                "Instruction_SK", "TranslationReview"]
FIELDS = ["Instruction", "Instruction_SK", "Input", "Output", "IncorrectOutput", "Subcategory", "Focus", "Mistake"]
SCHEMA = {"type": "object", "properties": {f: {"type": "string"} for f in FIELDS}, "required": FIELDS}
MANUAL = {
    "zrozumitelne_0_1": ("Zrozumiteľné zadanie", 1),
    "zodpoveda_kategorii_0_1": ("Zodpovedá kategórii", 1),
    "riesenie_spravne_0_1": ("Správne riešenie", 1),
    "obtiaznost_vhodna_0_1": ("Vhodná obtiažnosť", 1),
    "personalizacia_0_2": ("Personalizácia", 2),
}
RULES = """You create short Python practice tasks for beginner university students, in exactly the same format and style as the course dataset.
Each task has these fields:
- Instruction: the assignment in English, 1-2 sentences, like the examples
- Instruction_SK: the same assignment in natural Slovak
- Input: the input values given to the student (for example "nums = [3, 4, 5]"), or an empty string
- Output: a complete, correct, runnable Python program that solves the task for this input and prints the result.
  Define the input variables inside the program as in the examples. Do not use input(), files, the network or libraries other than math, random and numpy.
- IncorrectOutput: the same program with exactly one realistic beginner mistake. Prefer mistakes in the logic that still
  run but give a wrong result or crash (wrong loop bounds, < instead of <=, wrong operator, wrong initial value,
  = instead of +=, wrong index, return or print inside the loop, print instead of return, missing self., list not copied)
  over simple typos. Use different kinds of mistakes, not always the same one.
- Subcategory: one or two words, like in the examples
- Focus: one sentence in Slovak: which concept the task practises and, if a student profile is given, how it targets the student's mistakes
- Mistake: one sentence in Slovak describing the mistake in IncorrectOutput
The task must practise the given category and must be different from the examples and from the student's previous tasks.
Answer ONLY with JSON."""

PROFILE_RULES = """
The task is personalised: below are the student's recent mistakes in this category.
Create a NEW task that makes the student practise exactly the concept they get wrong (not the same task again).
First find out from the code and the result what kind of mistake the student keeps making.
If the mistakes are in the logic, make the task a bit simpler than the failed ones, so that the concept is clearly visible.
The IncorrectOutput must contain the same kind of mistake the student makes."""


def example_json(ex):
    r = ex["row"]
    return json.dumps({"Instruction": r.Instruction, "Instruction_SK": r.Instruction_SK,
                       "Input": "" if pd.isna(r.Input) else r.Input, "Output": ex["spravny"],
                       "IncorrectOutput": ex["nespravny"], "Subcategory": r.Subcategory},
                      ensure_ascii=False, indent=1)


def task_variants(r, rng):
    """Vsetky pouzitelne nespravne verzie ulohy: IncorrectOutput z datasetu + vlozene chyby (chyby.py)."""
    ok = sandbox.run(r.Output)
    if not (ok.get("ok") and ok["stdout"].strip()):
        return []
    out = []
    bad = sandbox.run(r.IncorrectOutput)
    if bad.get("spustene") and not (bad["ok"] and bad["stdout"] == ok["stdout"]):
        out.append({"typ": chyby.classify(r.Output, r.IncorrectOutput, ok, bad), "spravny": sandbox.clean_code(r.Output),
                    "nespravny": sandbox.clean_code(r.IncorrectOutput), "ok": ok, "bad": bad})
    out += chyby.verified_mutants(r.Output, rng, ok)
    return [dict(v, row=r) for v in out]


def build_profiles(df, categories, n, rng, mode="vsetky"):
    """Pre kazdu kategoriu n zadani: 3 priklady do promptu + simulovany student s 3 chybami rovnakeho typu.
    Typ chyby sa vyberie tak, aby sa typy co najviac striedali."""
    jobs, used = [], Counter()
    want = {"logicke": "logicka", "syntakticke": "syntakticka"}.get(mode)
    for cat in categories:
        pool = df[df.Category == cat].dropna(subset=["Instruction_SK", "Output", "IncorrectOutput"])
        pool = pool.sample(n=min(len(pool), 30), random_state=rng.randint(0, 10**6))
        by_task = [v for v in (task_variants(r, rng) for _, r in pool.iterrows()) if v]
        if len(by_task) < 6:
            print(f"[!] {cat}: málo použiteľných úloh ({len(by_task)}), preskakujem")
            continue
        tasks_of = {}  # typ -> zoznam uloh, kde sa da takato chyba urobit
        for k, variants in enumerate(by_task):
            for v in variants:
                if want is None or chyby.group(v["typ"]) == want:
                    tasks_of.setdefault(v["typ"], {}).setdefault(k, v)
        kinds = [kind for kind, ts in tasks_of.items() if len(ts) >= 3] or [kind for kind, ts in tasks_of.items() if len(ts) >= 2]
        if not kinds:
            print(f"[!] {cat}: žiadny typ chyby sa neopakuje, preskakujem")
            continue
        for i in range(n):
            rng.shuffle(kinds)
            kind = min(kinds, key=lambda x: used[x])
            used[kind] += 1
            ids = list(tasks_of[kind])
            rng.shuffle(ids)
            mistakes = [tasks_of[kind][k] for k in ids[:3]]
            rest = [k for k in range(len(by_task)) if k not in ids[:3]]
            rng.shuffle(rest)
            examples = [rng.choice(by_task[k]) for k in rest[:3]]  # priklady s roznymi chybami
            jobs.append({"kategoria": cat, "c": i + 1, "typ_chyby_studenta": kind, "priklady": examples, "chyby": mistakes})
    print("Typy chýb v profiloch:", dict(used))
    return jobs


def profile_text(mistakes, with_kind=False):
    parts = []
    for k, m in enumerate(mistakes, 1):
        parts.append(f"{k}. Task: {m['row'].Instruction}\nStudent's code:\n```python\n{m['nespravny']}\n```\n"
                     f"Result: {chyby.run_text(m['ok'], m['bad'])}")
    text = "\n\n".join(parts)
    if with_kind:
        text += f"\n\nDiagnosed mistake: {chyby.label(mistakes[0]['typ'])}"
    return text


def build_messages(job, mode, with_kind=False):
    system = RULES + (PROFILE_RULES if mode == "s_profilom" else "")
    user = f"Category: {job['kategoria']}\n\nExamples from the dataset:\n" + \
        "\n".join(example_json(x) for x in job["priklady"])
    if mode == "s_profilom":
        user += "\n\nStudent profile - recent mistakes:\n\n" + profile_text(job["chyby"], with_kind)
    return [{"role": "system", "content": system}, {"role": "user", "content": user + "\n\nCreate one new task."}]


def most_similar(instruction, df_cat):
    best, text = 0.0, ""
    for other in df_cat.Instruction.dropna():
        s = difflib.SequenceMatcher(None, instruction.lower(), other.lower()).ratio()
        if s > best:
            best, text = s, other
    return round(best, 2), text


def run(args):
    df = pd.read_csv(args.dataset)
    rng = random.Random(args.seed)
    jobs = build_profiles(df, args.kategorie, args.n, rng, args.chyby)
    configs = [parse_config(c) for c in args.konfig]
    print(f"{len(jobs)} zadaní x {len(args.rezimy)} režimy x {len(configs)} modelov = {len(jobs) * len(args.rezimy) * len(configs)} úloh")

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
        max_tokens = args.max_tokenov or (6000 if think is True else 3000)
        for j, job in enumerate(jobs, 1):
            for mode in args.rezimy:
                rec = {"model": name, "rezim": mode, "kategoria": job["kategoria"], "zadanie_c": job["c"],
                       "typ_chyby_studenta": chyby.label(job["typ_chyby_studenta"]) if mode == "s_profilom" else "",
                       "profil": profile_text(job["chyby"], args.s_typom_chyby) if mode == "s_profilom" else ""}
                try:
                    data = ask(model, build_messages(job, mode, args.s_typom_chyby), think, num_predict=max_tokens, fmt=SCHEMA)
                    task = json.loads(data["message"]["content"])
                    task = {f: str(task.get(f, "")).strip() for f in FIELDS}
                    rec.update(task, json_ok=all(task[f] for f in FIELDS if f != "Input"), chyba="")
                except (requests.RequestException, ValueError) as e:
                    data, task = {}, None
                    rec.update(json_ok=False, chyba=str(e)[:300])
                rec["cas_s"] = round(data.get("_wall_s", 0), 2) if data else None
                if task:
                    ok = {"spustene": False} if args.bez_spustania else sandbox.run(task["Output"])
                    bad = {"spustene": False} if args.bez_spustania else sandbox.run(task["IncorrectOutput"])
                    kind = chyby.classify(task["Output"], task["IncorrectOutput"], ok, bad) if ok.get("ok") else ""
                    sim, similar = most_similar(task["Instruction"], df[df.Category == job["kategoria"]])
                    rec.update({
                        "output_bezi": bool(ok.get("ok") and ok.get("stdout", "").strip()),
                        "vystup": ok.get("stdout", "")[:300], "output_chyba": ok.get("chyba") or ok.get("dovod", ""),
                        "incorrect_ina": bool(bad.get("spustene") and (not bad["ok"] or bad["stdout"] != ok.get("stdout"))),
                        "typ_chyby_ulohy": chyby.label(kind), "skupina_chyby_ulohy": chyby.group(kind),
                        "rovnaky_typ_chyby": (kind == job["typ_chyby_studenta"]) if mode == "s_profilom" and kind else None,
                        "pouziva_input": "input(" in task["Output"],
                        "sk_ok": any(ch in task["Instruction_SK"] for ch in "áäčďéíľĺňóôŕšťúýž"),
                        "podobnost_s_datasetom": sim, "najpodobnejsia_uloha": similar,
                    })
                rows.append(rec)
                r = rec
                print(f"  [{j}/{len(jobs)}] {job['kategoria'][:22]:<22} {mode:<12} "
                      + ("JSON CHYBA" if not task else
                         f"{r['cas_s']:5.1f} s  beží={'áno' if r['output_bezi'] else 'NIE'}  "
                         f"chybná_iná={'áno' if r['incorrect_ina'] else 'NIE'}  podobnosť={r['podobnost_s_datasetom']}"))
        unload_all()

    if not rows:
        return
    with (OUT / f"{stamp}.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    res = pd.DataFrame(rows)

    # ulohy v rovnakom tvare ako final_dataset.csv (len tie, ktore sa podarilo vygenerovat)
    good = res[res.json_ok].copy()
    tasks = pd.DataFrame({
        "ID": range(900001, 900001 + len(good)), "Instruction": good.Instruction, "Input": good.Input,
        "Output": good.Output.map(sandbox.clean_code).str.replace("\n", "\r\n"), "Category": good.kategoria,
        "Subcategory": good.Subcategory, "IncorrectOutput": good.IncorrectOutput.map(sandbox.clean_code).str.replace("\n", "\r\n"),
        "Instruction_SK": good.Instruction_SK, "TranslationReview": 0})[DATASET_COLS]
    tasks.to_csv(OUT / f"{stamp}_ulohy.csv", index=False)
    good.insert(0, "ID", range(900001, 900001 + len(good)))

    agg = {"uloh": ("json_ok", "size"), "json_ok": ("json_ok", "mean")}
    for col in ("output_bezi", "incorrect_ina", "rovnaky_typ_chyby", "pouziva_input", "sk_ok"):
        if col in res:
            agg[col] = (col, lambda s: s.dropna().astype(bool).mean() if s.notna().any() else None)
    if "skupina_chyby_ulohy" in res:
        agg["logicka_chyba"] = ("skupina_chyby_ulohy", lambda s: (s.dropna() == "logicka").mean() if (s.dropna() != "").any() else None)
    if "podobnost_s_datasetom" in res:
        agg["podobnost_s_datasetom"] = ("podobnost_s_datasetom", "mean")
    agg["cas_s"] = ("cas_s", "mean")
    summary = res.groupby(["model", "rezim"], sort=False).agg(**agg).round(2)
    summary.to_csv(OUT / f"{stamp}_summary.csv")

    review = good.reindex(columns=["ID", "model", "rezim", "kategoria", "typ_chyby_studenta", "profil", "Instruction_SK", "Instruction", "Input",
                   "Output", "vystup", "IncorrectOutput", "Mistake", "typ_chyby_ulohy", "skupina_chyby_ulohy", "rovnaky_typ_chyby", "Focus", "output_bezi", "incorrect_ina",
                   "podobnost_s_datasetom", "najpodobnejsia_uloha"])
    for col in MANUAL:
        review[col] = ""
    review["poznamka"] = ""
    review.to_csv(OUT / f"{stamp}_review.csv", index=False, sep=";", encoding="utf-8-sig")

    pd.set_option("display.width", 200)
    print("\n" + summary.to_string())
    print(f"\nÚlohy vo formáte datasetu: {OUT / (stamp + '_ulohy.csv')}")
    print(f"Na ručné hodnotenie (Excel): {OUT / (stamp + '_review.csv')}")
    print("  zrozumitelne / zodpoveda_kategorii / riesenie_spravne / obtiaznost_vhodna: 0 alebo 1"
          "\n  personalizacia_0_2 (len s_profilom): 0 nesúvisí s chybami, 1 čiastočne, 2 cielene precvičí chybu študenta")
    print("Po vyplnení: python gen_eval.py --vyhodnot")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--konfig", nargs="+", default=["gpt-oss:20b", "qwen3.8:27b@false", "qwen3.8:27b@true"],
                    help="model alebo model@think, napr. qwen3.8:27b@true")
    ap.add_argument("--kategorie", nargs="+", default=CATEGORIES)
    ap.add_argument("--n", type=int, default=2, help="zadaní na kategóriu (každé v oboch režimoch)")
    ap.add_argument("--rezimy", nargs="+", choices=["bez_profilu", "s_profilom"], default=["bez_profilu", "s_profilom"])
    ap.add_argument("--chyby", choices=["vsetky", "logicke", "syntakticke"], default="vsetky",
                    help="aké chyby má mať simulovaný študent")
    ap.add_argument("--s-typom-chyby", action="store_true", help="v profile povedať modelu aj typ chyby")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-tokenov", type=int, default=None)
    ap.add_argument("--bez-spustania", action="store_true", help="nespúšťať vygenerovaný kód")
    ap.add_argument("--dataset", default=str(DATASET))
    ap.add_argument("--vyhodnot", nargs="*", default=None, help="tabuľky na vyhodnotenie (viac sa spojí), bez cesty posledná")
    args = ap.parse_args()
    if args.vyhodnot is not None:
        evaluate(args.vyhodnot or [latest(OUT)], MANUAL, group_by=("model", "rezim"))
    else:
        run(args)


if __name__ == "__main__":
    main()
