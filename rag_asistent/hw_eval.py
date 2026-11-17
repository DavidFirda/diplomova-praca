"""Porovnanie modelov s hodnotenim ucitela na domacich ulohach 2024 a 2025.
Vysledky idu do data/eval/vysledky/, je tam kod studentov, takze nejdu na git."""
import argparse
import json
import re
from datetime import datetime

import pandas as pd
import requests

from config import DATA, HERE, OLLAMA
from smoke_test import SK_SUFFIX, ask, checks, vram_share

EVAL = DATA / "eval"
OUT = EVAL / "vysledky"
MAX_CODE = 6000
GROUPS = ("chyba", "ciste", "s_vyhradou")

RAG_HINT = """

COURSE MATERIALS:
The student's code is followed by excerpts from the course lectures. Use them only to choose
the same terminology and concepts as the lectures. Do not cite them and do not mention them."""

ZADANIE_HINT = """

HOMEWORK DESCRIPTION:
The message contains the general homework description from the course website (with the grading
criteria) and the student's file with the specific task in its comments. The solution must fulfil
BOTH: the general requirements in the description (for example the number of implementations,
tests, raised exceptions, answers written into comments) and the specific task in the file.
If the description refers to a picture or file the student had (for example a class diagram),
you cannot see it; judge only what you can check."""

VERDICT_SK = """

LANGUAGE:
- Write the feedback in Slovak. Keep Python keywords, function names and error names in their original form.
- Keep the JSON keys and the verdict values in English."""

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {"verdict": {"type": "string", "enum": ["correct", "incorrect"]},
                   "feedback": {"type": "string"}},
    "required": ["verdict", "feedback"],
}

JUDGE_PROMPT = """You compare two pieces of feedback on the same student's Python homework.

Teacher's comment (ground truth):
{teacher}

Assistant's feedback:
{assistant}

Does the assistant's feedback point out the same problem as the teacher's comment
(the same missing or wrong part of the solution, even if worded differently)?
Answer only with JSON: {{"same_issue": true or false, "reason": "one short sentence"}}"""


def load_cases(n, seed, groups=GROUPS):
    df = pd.read_csv(EVAL / "domace_ulohy.csv")
    if "skupina" not in df:
        raise SystemExit("Dataset je zo starej verzie, spusti znova: python hw_dataset.py")
    df = df[df.skupina.isin(groups) & df.kod.notna()].copy()
    df["komentar"] = df.komentar.fillna("")
    df = df[(df.skupina != "chyba") | (df.komentar.str.len() > 0)]  # chybne len s komentarom
    df["spravne"] = df.skupina != "chyba"
    # z kazdej skupiny a ulohy nahodne n
    # dva pokusy toho isteho studenta v skupine -> len jeden
    parts = [df[df.skupina == g].sample(frac=1, random_state=seed)
             .drop_duplicates(["rok", "student", "uloha"]).groupby(["rok", "uloha"]).head(n)
             for g in groups]
    return pd.concat(parts).sort_values(["rok", "uloha", "skupina"]).reset_index(drop=True)


def task_query(code):
    """Text zadania z komentarov sablony, na hladanie slajdov."""
    lines = [l.strip("# ").strip() for l in code.splitlines() if l.strip().startswith("#")]
    noise = re.compile(r"^(todo|čas|cas|použité|pouzite|nevymažte|-+$|úloha \d+$|uloha \d+$|\d+\.?$)", re.I)
    text = " ".join(l for l in lines if len(l) > 3 and not noise.match(l))
    return text[:500] or code[:500]


def load_spec(rok, uloha):
    """homeworkXX.md bez deadlinu a odkazu na pdf, None ak chyba."""
    path = DATA / "zadania" / str(rok) / f"homework{int(uloha):02d}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").split("## Deadline")[0]
    text = re.sub(r"^.*\]\([^)]*\.pdf\).*$\n?", "", text, flags=re.M)  # odkaz na pdf
    return text.strip()


def build_messages(code, lang, context=None, prompt="krysanova", spec=None):
    if prompt == "verdikt":
        system = (HERE / "prompts" / "rules_verdikt.md").read_text(encoding="utf-8")
        lang_rules = VERDICT_SK
    else:
        system = (HERE / "prompts" / "rules_krysanova.md").read_text(encoding="utf-8")
        lang_rules = SK_SUFFIX
    if context:
        system += RAG_HINT
    if spec:
        system += ZADANIE_HINT
    if lang == "sk":
        system += lang_rules
    if spec:
        user = (f"Homework description (course website):\n{spec}\n\n"
                "Student's input (teacher's template with the specific task in comments, "
                f"followed by the student's code):\n{code[:MAX_CODE]}")
    else:
        user = ("Task given to the student:\nThe assignment is written in the comments of the submitted file "
                f"(template from the teacher).\n\nStudent's input:\n{code[:MAX_CODE]}")
    if context:
        user += f"\n\nCourse materials:\n{context}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_verdict(content):
    """Vrati (said_correct, feedback), pri zlom JSON (None, '')."""
    try:
        data = json.loads(content)
        verdict = str(data.get("verdict", "")).lower()
        if verdict not in ("correct", "incorrect"):
            return None, ""
        return verdict == "correct", str(data.get("feedback", "")).strip()
    except (ValueError, AttributeError):
        return None, ""


def ollama_error(e):
    resp = getattr(e, "response", None)
    try:
        return resp.json().get("error", resp.text) if resp is not None else str(e)
    except ValueError:
        return resp.text or str(e)


def unload_all():
    """Uvolni modely z pamate, inak ollama vracia 500."""
    try:
        for m in requests.get(f"{OLLAMA}/api/ps", timeout=10).json().get("models", []):
            requests.post(f"{OLLAMA}/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=60)
    except requests.RequestException:
        pass


def judge(model, teacher, assistant):
    payload = {"model": model, "stream": False, "format": "json",
               "options": {"temperature": 0, "num_ctx": 8192},
               "messages": [{"role": "user", "content": JUDGE_PROMPT.format(teacher=teacher, assistant=assistant)}]}
    if "gpt-oss" in model:
        payload["think"] = "low"
    try:
        r = requests.post(f"{OLLAMA}/api/chat", json=payload, timeout=600)
        r.raise_for_status()
        data = json.loads(r.json()["message"]["content"])
        return bool(data.get("same_issue")), str(data.get("reason", ""))
    except requests.RequestException as e:
        return None, f"chyba sudcu: {ollama_error(e)}"
    except (ValueError, KeyError) as e:
        return None, f"chyba sudcu: {e}"


def share(series):
    return series.mean() if len(series) else float("nan")


def summarize(res, with_judge):
    stats = []
    for (model, rag, prompt), g_all in res.groupby(["model", "rag", "prompt"]):
        g = g_all[~g_all.prazdna]  # prazdne odpovede sa do presnosti nepocitaju
        wrong, clean, remark = (g[g.skupina == s] for s in GROUPS)
        row = {"model": model, "rag": rag, "prompt": prompt,
               "prazdne": g_all.prazdna.mean(),
               "ciste_potvrdil": share(clean.said_correct),
               "chybne_odhalil": share(~wrong.said_correct.astype(bool)),
               }
        row["presnost"] = (row["ciste_potvrdil"] + row["chybne_odhalil"]) / 2  # vyvazena presnost, nahoda = 0.5
        row.update({
            "odhalil_0_75b": share(~wrong[wrong.body == 0.75].said_correct.astype(bool)),
            "odhalil_max_0_5b": share(~wrong[wrong.body <= 0.5].said_correct.astype(bool)),
            "vyhrada_vytkol": share(~remark.said_correct.astype(bool)),
        })
        if with_judge:
            row["rovnaka_chyba"] = share(wrong.get("rovnaka_chyba", pd.Series(dtype=object)) == True)
            row["vyhrada_rovnaka"] = share(remark.get("rovnaka_chyba", pd.Series(dtype=object)) == True)
        row.update({"unik_kodu": share(wrong.possible_leak), "jazyk_ok": share(g.lang_ok),
                    "slov": share(g.words), "tok_per_s": g.tok_per_s.median(), "cas_s": share(g.total_s)})
        stats.append(row)
    return pd.DataFrame(stats).set_index(["model", "rag", "prompt"]).round(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["gpt-oss:20b"])
    ap.add_argument("--n", type=int, default=3, help="počet riešení z každej skupiny na úlohu a rok")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--lang", choices=["sk", "en"], default="sk")
    ap.add_argument("--think", default=None, help="low / medium / high alebo false")
    ap.add_argument("--prompt", choices=["krysanova", "verdikt"], default="krysanova")
    ap.add_argument("--rag", action="store_true", help="pridať súvisiace slajdy z prednášok")
    ap.add_argument("--zadanie", action="store_true", help="pridať text homeworkXX.md z daného roka")
    ap.add_argument("--max-tokenov", type=int, default=2048,
                    help="limit tokenov odpovede vrátane uvažovania (pri --think true napr. 4096)")
    ap.add_argument("--judge", default=None, help="model, ktorý porovná odpoveď s komentárom vyučujúceho")
    ap.add_argument("--bez-vyhrad", action="store_true", help="vynechať riešenia 1 b s výhradou")
    args = ap.parse_args()
    think = {"false": False, "true": True}.get(str(args.think).lower(), args.think)

    groups = ("chyba", "ciste") if args.bez_vyhrad else GROUPS
    cases = load_cases(args.n, args.seed, groups)
    counts = cases.skupina.value_counts()
    print(f"{len(cases)} riešení z {cases.groupby(['rok', 'uloha']).ngroups} úloh: "
          + ", ".join(f"{g} {counts.get(g, 0)}" for g in groups) + f" | prompt: {args.prompt}"
          + (" | so zadaním" if args.zadanie else ""))

    specs = {}
    if args.zadanie:
        specs = {(r, u): load_spec(r, u) for r, u in cases[["rok", "uloha"]].drop_duplicates().itertuples(index=False)}
        missing = sorted(k for k, v in specs.items() if v is None)
        if missing:
            raise SystemExit(f"Chýbajú zadania {missing} v {DATA / 'zadania'}. Spusti: python ziskaj_zadania.py")

    contexts = {}
    if args.rag:
        from retrieval import Retriever
        print("Hľadám súvisiace slajdy k úlohám...")
        retriever = Retriever()
        for n_done, (i, row) in enumerate(cases.iterrows(), start=1):
            hits = retriever.search(task_query(row.kod), k=3, typy={"prednaska"}, min_prednasky=0)
            contexts[i] = "\n\n".join(f"({h['subor'].split('/')[-1]}, {h['poloha']})\n{h['text']}" for h in hits)
            print(f"\r  {n_done}/{len(cases)}", end="", flush=True)
        print()

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fmt = VERDICT_SCHEMA if args.prompt == "verdikt" else None
    rows = []
    for model in args.models:
        print(f"\n=== {model}{' + RAG' if args.rag else ''}{' + zadanie' if args.zadanie else ''} ({args.prompt}) ===")
        unload_all()
        try:
            ask(model, [{"role": "user", "content": "Hi"}], think)
        except requests.RequestException as e:
            print(f"  preskakujem, Ollama hlási: {ollama_error(e)}")
            continue
        vram = vram_share(model)
        for i, row in cases.iterrows():
            messages = build_messages(row.kod, args.lang, contexts.get(i), args.prompt,
                                      specs.get((row.rok, row.uloha)))
            try:
                data = ask(model, messages, think, num_predict=args.max_tokenov, fmt=fmt)
            except requests.RequestException as e:
                print(f"  {row.rok} h{row.uloha:02d} chyba: {ollama_error(e)}")
                continue
            content = data["message"]["content"].strip()
            if args.prompt == "verdikt":
                said_correct, answer = parse_verdict(content)
                empty = said_correct is None
            else:
                answer, empty, said_correct = content, not content, None
            rec = {"model": model, "rag": args.rag, "prompt": args.prompt, "lang": args.lang,
                   "seed": args.seed, "n": args.n, "think": str(think), "beh": stamp, "zadanie": args.zadanie,
                   "rok": int(row.rok), "uloha": int(row.uloha), "student": str(row.student),
                   "body": float(row.body), "skupina": row.skupina, "spravne": bool(row.spravne),
                   "komentar_ucitela": row.komentar, "odpoved": answer, "surova_odpoved": content,
                   "prazdna": empty,
                   "tok_per_s": round(data["eval_count"] / (data["eval_duration"] / 1e9), 1)
                   if data.get("eval_duration") else None,
                   "total_s": round(data["_wall_s"], 2), "vram_share": vram,
                   **checks(answer, bool(row.spravne), args.lang)}
            if said_correct is not None:  # verdikt z JSON ma prednost
                rec["said_correct"] = said_correct
                rec["verdict_ok"] = said_correct == rec["spravne"]
            rows.append(rec)
            mark = "PRÁZDNA" if empty else ("potvrdil" if rec["said_correct"] else "vytkol  ")
            print(f"  {row.rok} h{row.uloha:02d} {row.skupina:<10} body={row.body:<4} {mark} {rec['total_s']} s")

    if not rows:
        return

    if args.judge:  # sudca az na konci, aby neboli v pamati dva modely
        print(f"\n=== sudca {args.judge} ===")
        unload_all()
        errors = 0
        for rec in rows:
            if rec["skupina"] != "ciste" and not rec["said_correct"] and not rec["prazdna"]:
                rec["rovnaka_chyba"], rec["dovod_sudcu"] = judge(args.judge, rec["komentar_ucitela"], rec["odpoved"])
                errors += rec["rovnaka_chyba"] is None
        if errors:
            print(f"  [!] sudca zlyhal pri {errors} odpovediach, napr.: "
                  + next(r["dovod_sudcu"] for r in rows if r.get("rovnaka_chyba") is None and "dovod_sudcu" in r))

    with (OUT / f"{stamp}.jsonl").open("w", encoding="utf-8") as out:
        for rec in rows:
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")

    res = pd.DataFrame(rows)
    summary = summarize(res, bool(args.judge))
    summary.to_csv(OUT / f"{stamp}_summary.csv")

    # podiel potvrdenych podla ulohy a skupiny
    by_task = (res[~res.prazdna].groupby(["model", "rok", "uloha", "skupina"]).said_correct.mean()
               .unstack().round(2).add_prefix("potvrdil_"))
    by_task.to_csv(OUT / f"{stamp}_ulohy.csv")

    cols = ["model", "prompt", "rok", "uloha", "skupina", "body", "komentar_ucitela", "odpoved", "verdict_ok"]
    review = res[cols + (["rovnaka_chyba", "dovod_sudcu"] if args.judge and "rovnaka_chyba" in res else [])].copy()
    for col in ("nasiel_rovnaku_chybu_0_1", "uzitocnost_1_5", "slovencina_1_5", "poznamka"):
        review[col] = ""
    review.to_csv(OUT / f"{stamp}_review.csv", index=False, encoding="utf-8-sig", sep=";")

    print("\n", summary.to_string())
    print("\npresnost = priemer (ciste_potvrdil, chybne_odhalil); náhodné hádanie = 0,5")
    print(f"Podľa úloh: {OUT / (stamp + '_ulohy.csv')}")
    print(f"Na ručné hodnotenie (Excel): {OUT / (stamp + '_review.csv')}")


if __name__ == "__main__":
    main()
