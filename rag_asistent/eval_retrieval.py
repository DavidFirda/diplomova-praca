"""Hit@k a MRR vyhladavania na prompts/otazky_vyhladavanie.csv."""
import argparse
import time

import pandas as pd

import retrieval
from ask import question_lang, to_slovak
from config import EMBED_MODEL, HERE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--embed", default=EMBED_MODEL)
    ap.add_argument("--llm", default="gpt-oss:20b", help="model na preklad anglických otázok")
    ap.add_argument("--bez-prekladu", action="store_true")
    ap.add_argument("--min-prednasky", type=int, default=2)
    ap.add_argument("--vaha-knih", type=float, help="prepíše váhu kníh z config.py")
    ap.add_argument("--vypis", action="store_true", help="vypísať nájdené zdroje pri každej otázke")
    args = ap.parse_args()
    if args.vaha_knih is not None:
        retrieval.WEIGHTS["kniha"] = args.vaha_knih

    qs = pd.read_csv(HERE / "prompts" / "otazky_vyhladavanie.csv", sep=";", dtype=str).fillna("")
    r = retrieval.Retriever(args.embed)
    rows, t0 = [], time.time()
    for _, q in qs.iterrows():
        expected = {int(x) for x in q.prednaska.split("|") if x.strip()}
        extra = []
        if not args.bez_prekladu and question_lang(q.otazka) == "en":
            extra = [to_slovak(q.otazka, args.llm)]
        res = r.search(q.otazka, k=args.k, extra_queries=extra, min_prednasky=args.min_prednasky)
        found = [c for c in res if c["skore"] > 0]  # bez kuskov doplnenych kvoli minimu
        rank = next((i for i, c in enumerate(found, start=1)
                     if c["typ"] == "prednaska" and c["prednaska"] in expected), None)
        rows.append({
            "otazka": q.otazka, "jazyk": q.jazyk, "mimo": not expected, "preklad": extra[0] if extra else "",
            "hit": rank is not None, "rr": 1 / rank if rank else 0.0,
            "top1_prednaska": bool(found) and found[0]["typ"] == "prednaska",
            "zdroje": " | ".join(f"{c['typ'][:4]}:{c['subor'].split('/')[-1][:22]} {c['poloha']}" for c in res),
        })
        if args.vypis:
            mark = "MIMO" if not expected else ("OK  " if rank else "CHYBA")
            print(f"{mark} {q.otazka}" + (f"  -> {extra[0]}" if extra else ""))
            print(f"      {rows[-1]['zdroje']}")

    df = pd.DataFrame(rows)
    inside, outside = df[~df.mimo], df[df.mimo]
    print(f"\nembed={args.embed}  k={args.k}  min_prednasky={args.min_prednasky}  "
          f"vaha_knih={retrieval.WEIGHTS['kniha']}  preklad={not args.bez_prekladu}  ({time.time() - t0:.0f} s)")
    print(inside.groupby("jazyk").agg(otazok=("hit", "size"), **{f"hit@{args.k}": ("hit", "mean")},
                                       MRR=("rr", "mean")).round(2).to_string())
    print(f"spolu: hit@{args.k}={inside.hit.mean():.2f}  MRR={inside.rr.mean():.2f}  "
          f"mimo_ok={(~outside.top1_prednaska).mean():.2f} ({len(outside)} otázok mimo prednášok)")
    miss = inside[~inside.hit]
    if len(miss):
        print("\nNenájdené:")
        for _, m in miss.iterrows():
            print(f"  - {m.otazka}" + (f"  ({m.preklad})" if m.preklad else ""))
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    df.to_csv(out / f"retrieval_{time.strftime('%Y%m%d_%H%M%S')}.csv", index=False, encoding="utf-8-sig", sep=";")


if __name__ == "__main__":
    main()
