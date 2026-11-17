"""Rychly test modelov na final_dataset.csv (spravne aj chybne riesenia, sk/en)."""
import argparse
import json
import random
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
DATASET = HERE.parent / "student_testing_app" / "final_dataset.csv"
RULES = HERE / "prompts" / "rules_krysanova.md"
RESULTS = HERE / "results"
OLLAMA = "http://127.0.0.1:11434"

DEFAULT_MODELS = ["gpt-oss:20b", "gemma4:12b", "qwen3:14b"]
CORRECT_REPLY = {"en": "everything is correct", "sk": "všetko je správne"}

# doplnok pre slovencinu, pravidla ostavaju po anglicky
SK_SUFFIX = """

LANGUAGE:
- Always answer in Slovak, regardless of the language of the task or the code.
- If the solution is correct, reply ONLY with: "Všetko je správne. Výborne!"
- Keep Python keywords, function names and error names in their original form."""

# hruby odhad jazyka podla castych slov
SK_WORDS = {"je", "sa", "na", "že", "tvoj", "tvoje", "tvoja", "si", "kód", "ako", "alebo", "nie",
            "chyba", "funkcia", "skús", "musíš", "treba", "výborne", "všetko", "správne", "ktorý"}
EN_WORDS = {"the", "is", "you", "your", "and", "to", "of", "it", "this", "that", "should",
            "try", "make", "sure", "everything", "correct", "missing", "function"}


def build_messages(rules, row, code, lang):
    # rovnako ako build_messages u Krysanovej
    instruction = row["Instruction_SK"] if lang == "sk" and pd.notna(row.get("Instruction_SK")) else row["Instruction"]
    task = f"{instruction}\n\nInput: {row['Input'] if pd.notna(row['Input']) else 'None'}"
    system = rules + (SK_SUFFIX if lang == "sk" else "")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Task given to the student:\n{task}\n\nStudent's input:\n{code}"},
    ]


def ask(model, messages, think=None, num_predict=800, fmt=None):
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.2, "top_p": 0.95, "num_predict": num_predict, "num_ctx": 8192},
    }
    if think is not None:  # gpt-oss: low/medium/high, qwen a gemma: true/false
        payload["think"] = think
    if fmt is not None:
        payload["format"] = fmt
    t0 = time.time()
    r = requests.post(f"{OLLAMA}/api/chat", json=payload, timeout=600)
    r.raise_for_status()
    data = r.json()
    data["_wall_s"] = time.time() - t0
    return data


def vram_share(model):
    # kolko modelu je vo VRAM (1.0 = cely na GPU)
    try:
        for m in requests.get(f"{OLLAMA}/api/ps", timeout=10).json().get("models", []):
            if m.get("name") == model or m.get("model") == model:
                return round(m["size_vram"] / m["size"], 2) if m.get("size") else None
    except requests.RequestException:
        pass
    return None


def answer_lang(answer):
    prose = re.sub(r"```.*?```|`[^`]*`", " ", answer, flags=re.S).lower()
    words = re.findall(r"[a-záäčďéíĺľňóôŕšťúýž]+", prose)
    sk = sum(w in SK_WORDS for w in words) + 2 * len(re.findall(r"[áäčďéíĺľňóôŕšťúýž]", prose)) / max(len(words), 1)
    en = sum(w in EN_WORDS for w in words)
    return "sk" if sk > en else "en"


def checks(answer, is_correct_code, lang):
    text = answer.lower()
    said_correct = CORRECT_REPLY[lang] in text or CORRECT_REPLY["en"] in text
    has_code = bool(re.search(r"```|^\s*(def |for |while |print\()", answer, re.M))
    return {
        "verdict_ok": said_correct if is_correct_code else not said_correct,
        "said_correct": said_correct,
        "possible_leak": has_code and not is_correct_code,
        "lang_ok": answer_lang(answer) == lang,
        "words": len(answer.split()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--n", type=int, default=10, help="počet úloh (každá sa pošle 2x: chybná + správna)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--think", default=None, help="napr. low / medium / high alebo false")
    ap.add_argument("--lang", choices=["en", "sk", "both"], default="en")
    args = ap.parse_args()
    think = {"false": False, "true": True}.get(str(args.think).lower(), args.think)
    langs = ["sk", "en"] if args.lang == "both" else [args.lang]

    rules = RULES.read_text(encoding="utf-8")
    df = pd.read_csv(DATASET).dropna(subset=["Instruction", "Output", "IncorrectOutput"])
    sample = df.sample(n=min(args.n, len(df)), random_state=args.seed)

    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS / f"{stamp}.jsonl"
    rows = []

    with out_path.open("w", encoding="utf-8") as out:
        for model in args.models:
            print(f"\n=== {model} ===")
            try:  # zahriatie, aby sa nepocitalo nacitanie modelu
                ask(model, [{"role": "user", "content": "Hi"}], think)
            except requests.RequestException as e:
                print(f"  preskakujem ({e}); stiahni model: ollama pull {model}")
                continue
            share = vram_share(model)
            for _, row in sample.iterrows():
                for lang in langs:
                    for kind, code in (("incorrect", row["IncorrectOutput"]), ("correct", row["Output"])):
                        data = ask(model, build_messages(rules, row, code, lang), think)
                        answer = data["message"]["content"].strip()
                        rec = {
                            "model": model, "lang": lang, "think": args.think, "task_id": int(row["ID"]),
                            "category": row["Category"], "kind": kind, "answer": answer,
                            "thinking": data["message"].get("thinking"),
                            "tok_per_s": round(data["eval_count"] / (data["eval_duration"] / 1e9), 1)
                            if data.get("eval_duration") else None,
                            "prompt_s": round(data.get("prompt_eval_duration", 0) / 1e9, 2),
                            "total_s": round(data["_wall_s"], 2),
                            "vram_share": share,
                            **checks(answer, kind == "correct", lang),
                        }
                        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        rows.append(rec)
                        print(f"  #{rec['task_id']:<5} {lang} {kind:<9} ok={rec['verdict_ok']!s:<5} lang_ok={rec['lang_ok']!s:<5} "
                              f"{rec['tok_per_s']} tok/s  {rec['total_s']} s")

    if not rows:
        print("Žiadne výsledky – beží Ollama (ollama serve) a sú modely stiahnuté?")
        return
    res = pd.DataFrame(rows)
    summary = res.groupby(["model", "lang"]).agg(
        verdict_ok=("verdict_ok", "mean"),
        possible_leak=("possible_leak", "mean"),
        lang_ok=("lang_ok", "mean"),
        avg_words=("words", "mean"),
        tok_per_s=("tok_per_s", "median"),
        avg_total_s=("total_s", "mean"),
        vram_share=("vram_share", "first"),
    ).round(2)
    summary.to_csv(RESULTS / f"{stamp}_summary.csv")
    # tabulka na rucne hodnotenie v exceli
    review = res[["model", "lang", "task_id", "kind", "verdict_ok", "answer"]].copy()
    for col in ("spravnost_1_5", "jazyk_1_5", "uzitocnost_1_5", "poznamka"):
        review[col] = ""
    review.to_csv(RESULTS / f"{stamp}_review.csv", index=False, encoding="utf-8-sig", sep=";")
    print("\n", summary.to_string())
    print(f"\nOdpovede: {out_path}")
    print(f"Na ručné hodnotenie: {RESULTS / (stamp + '_review.csv')}")


if __name__ == "__main__":
    main()
