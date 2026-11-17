"""Porovnanie odpovedi modelov na otazky z prednasok (RAG), tabulka na rucne hodnotenie."""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import requests

from ask import NUM_CTX, answer, label, to_slovak, unload
from config import DATA, EMBED_MODEL, HERE, OLLAMA
from retrieval import Retriever
from smoke_test import answer_lang

OUT = DATA / "eval" / "rag"
MANUAL = {  # stlpec -> (popis, maximum)
    "spravnost_0_2": ("Správnosť", 2),
    "citacie_sedia_0_1": ("Citácie sedia", 1),
    "pojmy_z_prednasok_0_1": ("Pojmy z prednášok", 1),
    "jazyk_1_5": ("Jazyk", 5),
}
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]


def parse_config(text):
    model, _, think = text.partition("@")
    think = {"true": True, "false": False}.get(think.lower(), think or None)
    return model, think


def config_name(model, think):
    return model + (f" (think {str(think).lower()})" if think is not None else "")


def load_model(model):
    # nacitanie s rovnakym num_ctx ako pri odpovedi, aby sa do casu nepocitalo
    requests.post(f"{OLLAMA}/api/generate", json={"model": model, "options": {"num_ctx": NUM_CTX}}, timeout=900)


def citations(text):
    prose = re.sub(r"```.*?```|`[^`]*`", " ", text, flags=re.S)
    return sorted({int(n) for n in re.findall(r"\[(\d+)\]", prose)})


def run(args):
    qs = pd.read_csv(HERE / "prompts" / "otazky_vyhladavanie.csv", sep=";", dtype=str).fillna("")
    if args.n:
        qs = qs.head(args.n)
    configs = [parse_config(c) for c in args.konfig]
    print(f"{len(qs)} otázok x {len(configs)} modelov")

    translations = {}
    en = [q for q, j in zip(qs.otazka, qs.jazyk) if j == "en"]
    if en and not args.bez_prekladu:
        print(f"Prekladám {len(en)} anglických otázok ({args.preklad})...")
        for q in en:
            translations[q] = to_slovak(q, args.preklad)
        unload(args.preklad)

    print("Hľadám v materiáloch...")
    retriever = Retriever(args.embed)
    found = {}
    for q in qs.otazka:
        extra = [translations[q]] if q in translations else []
        found[q] = retriever.search(q, k=args.k, extra_queries=extra)
    unload(args.embed)

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rows = []
    for model, think in configs:
        name = config_name(model, think)
        max_tokens = args.max_tokenov or (4096 if think is True else 2048)
        print(f"\n=== {name} ===")
        try:
            load_model(model)
        except requests.RequestException as e:
            print(f"  preskakujem: {e}")
            continue
        for i, q in enumerate(qs.itertuples(index=False), start=1):
            res = found[q.otazka]
            expected = {int(x) for x in q.prednaska.split("|") if x.strip()}
            try:
                text, st = answer(q.otazka, res, model, q.jazyk, think, max_tokens, echo=False)
                error = ""
            except (requests.RequestException, RuntimeError) as e:
                text, st, error = "", {}, str(e)
            cited = citations(text)
            cited_ok = [n for n in cited if 1 <= n <= len(res)]
            rows.append({
                "model": name, "otazka": q.otazka, "jazyk": q.jazyk, "mimo_prednasok": not expected,
                "preklad": translations.get(q.otazka, ""),
                "zdroje": "\n".join(f"[{j}] {label(c)}" for j, c in enumerate(res, start=1)),
                "nasiel_prednasku": any(c["typ"] == "prednaska" and c["prednaska"] in expected for c in res),
                "odpoved": text, "chyba": error, "prazdna": not text,
                "cituje": bool(cited), "citacie": " ".join(f"[{n}]" for n in cited),
                "zle_cislo_citacie": len(cited_ok) < len(cited),
                "cituje_spravnu_prednasku": any(res[n - 1]["typ"] == "prednaska" and res[n - 1]["prednaska"] in expected
                                                for n in cited_ok) if expected else None,
                "jazyk_ok": bool(text) and answer_lang(text) == q.jazyk,
                "kod_v_odpovedi": "```" in text,
                "slov": len(text.split()),
                "prve_slovo_s": round(st["prve_slovo"], 2) if st.get("prve_slovo") is not None else None,
                "odpoved_s": round(st.get("spolu", 0), 2),
                "tokenov": st.get("tokenov"), "tok_s": round(st.get("tok_s", 0), 1),
                "uvazovanie_znakov": st.get("uvazovanie", 0),
            })
            r = rows[-1]
            status = "CHYBA" if error else ("PRÁZDNA" if not text else f"{r['odpoved_s']:5.1f} s, prvé slovo {r['prve_slovo_s']} s")
            print(f"  [{i}/{len(qs)}] {q.jazyk} {status} {r['citacie']}  {q.otazka[:50]}")
        unload(model)

    if not rows:
        return
    with (OUT / f"{stamp}.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    df = pd.DataFrame(rows)

    summary = df.groupby("model", sort=False).agg(
        odpovedi=("odpoved", "size"), prazdne=("prazdna", "mean"),
        prve_slovo_s=("prve_slovo_s", "median"), odpoved_s=("odpoved_s", "mean"), tok_s=("tok_s", "median"),
        slov=("slov", "mean"), cituje=("cituje", "mean"), zle_cislo_citacie=("zle_cislo_citacie", "mean"),
        cituje_spravnu_prednasku=("cituje_spravnu_prednasku", lambda s: s.dropna().astype(bool).mean()),
        jazyk_ok=("jazyk_ok", "mean"), kod_v_odpovedi=("kod_v_odpovedi", "mean")).round(2)
    summary.to_csv(OUT / f"{stamp}_summary.csv")

    review = df[["model", "otazka", "jazyk", "mimo_prednasok", "zdroje", "odpoved", "citacie"]].copy()
    for col in MANUAL:
        review[col] = ""
    review["poznamka"] = ""
    review.to_csv(OUT / f"{stamp}_review.csv", index=False, sep=";", encoding="utf-8-sig")

    hits = df.drop_duplicates("otazka")
    hits = hits[~hits.mimo_prednasok]
    print(f"\nVyhľadávanie: správna prednáška medzi {args.k} kúskami pri {hits.nasiel_prednasku.mean():.0%} otázok")
    print("\n" + summary.to_string())
    print(f"\nNa ručné hodnotenie (Excel): {OUT / (stamp + '_review.csv')}")
    print("  spravnost_0_2: 0 zlá, 1 čiastočne, 2 správna | citacie_sedia_0_1: citovaný kúsok naozaj hovorí to, čo odpoveď"
          "\n  pojmy_z_prednasok_0_1: používa pojmy zo slajdov | jazyk_1_5: gramatika a prirodzenosť")
    print("Po vyplnení: python rag_eval.py --vyhodnot")


def evaluate(path):
    if path == "posledny":
        files = sorted(OUT.glob("*_review.csv"))
        if not files:
            raise SystemExit(f"V {OUT} nie je žiadna tabuľka. Najprv spusti: python rag_eval.py")
        path = str(files[-1])
    elif not Path(path).exists():
        raise SystemExit(f"Súbor {path} neexistuje. Bez cesty sa vezme posledná tabuľka: python rag_eval.py --vyhodnot")
    print(f"Tabuľka: {path}\n")
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    cols = [c for c in MANUAL if c in df]
    for c in cols:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "."), errors="coerce")
    filled = df[cols].notna().any(axis=1)
    if not filled.any():
        raise SystemExit("Tabuľka ešte nie je vyplnená.")
    g = df[filled].groupby("model", sort=False)
    res = g[cols].mean().round(2)
    res["ohodnotenych"] = g.size()
    if "mimo_prednasok" in df:
        out = df[filled & df.mimo_prednasok.astype(str).str.lower().eq("true")]
        if len(out):
            res["spravnost_mimo_prednasok"] = out.groupby("model", sort=False).spravnost_0_2.mean().round(2)
    res.to_csv(path.replace("_review.csv", "_hodnotenie.csv"))
    print(res.to_string())

    models = list(res.index)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = range(len(cols))
    width = 0.8 / len(models)
    for j, m in enumerate(models):
        vals = [res.loc[m, c] / MANUAL[c][1] for c in cols]
        pos = [i - 0.4 + width * (j + 0.5) for i in x]
        ax.bar(pos, vals, width * 0.92, color=COLORS[j % len(COLORS)], label=m)
        for xi, v in zip(pos, vals):
            ax.text(xi, v + 0.01, f"{v:.2f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(list(x), [MANUAL[c][0] for c in cols])
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("podiel z maxima")
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, color="#e4e3df")
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=len(models))
    fig.tight_layout()
    png = path.replace("_review.csv", "_hodnotenie.png")
    fig.savefig(png, dpi=200)
    print(f"\nGraf: {png}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--konfig", nargs="+", default=["gpt-oss:20b", "qwen3.8:27b@false", "qwen3.8:27b@true"],
                    help="model alebo model@think, napr. qwen3.8:27b@true")
    ap.add_argument("--n", type=int, default=None, help="len prvých N otázok")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--embed", default=EMBED_MODEL)
    ap.add_argument("--preklad", default="gpt-oss:20b", help="model na preklad anglických otázok (rovnaký pre všetky)")
    ap.add_argument("--bez-prekladu", action="store_true")
    ap.add_argument("--max-tokenov", type=int, default=None, help="predvolene 2048, pri think true 4096")
    ap.add_argument("--vyhodnot", nargs="?", const="posledny", default=None,
                    help="vyplnená tabuľka _review.csv (bez cesty = posledná)")
    args = ap.parse_args()
    if args.vyhodnot:
        evaluate(args.vyhodnot)
    else:
        run(args)


if __name__ == "__main__":
    main()
