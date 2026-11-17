"""Spolocne veci pre qa_eval.py a gen_eval.py: konfiguracie modelov, nacitanie modelu, vyhodnotenie tabulky."""
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import requests

from config import OLLAMA

NUM_CTX = 8192  # rovnake ako v smoke_test.ask, inak ollama model nacita znova
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#8a5cd1"]


def parse_config(text):
    model, _, think = text.partition("@")
    think = {"true": True, "false": False}.get(think.lower(), think or None)
    return model, think


def config_name(model, think):
    return model + (f" (think {str(think).lower()})" if think is not None else "")


def load_model(model):
    requests.post(f"{OLLAMA}/api/generate", json={"model": model, "options": {"num_ctx": NUM_CTX}}, timeout=900)


def latest(folder, pattern="*_review.csv"):
    files = sorted(Path(folder).glob(pattern))
    if not files:
        raise SystemExit(f"V {folder} nie je žiadna tabuľka. Najprv spusti test.")
    return files[-1]


def evaluate(paths, manual, group_by=("model",)):
    """Priemery rucne vyplnenych stlpcov podla modelu (a dalsich stlpcov) + graf. Viac tabuliek sa spoji."""
    paths = [Path(p) for p in ([paths] if isinstance(paths, (str, Path)) else paths)]
    df = pd.concat([pd.read_csv(p, sep=";", encoding="utf-8-sig") for p in paths], ignore_index=True)
    cols = [c for c in manual if c in df]
    for c in cols:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "."), errors="coerce")
    filled = df[cols].notna().any(axis=1)
    if not filled.any():
        raise SystemExit("Tabuľka ešte nie je vyplnená.")
    g = df[filled].groupby(list(group_by), sort=False)
    res = g[cols].mean().round(2)
    res["ohodnotenych"] = g.size()
    if len(paths) == 1:
        out = Path(str(paths[0]).replace("_review.csv", "_hodnotenie.csv"))
    else:
        out = paths[0].parent / f"spolu_{datetime.now():%Y%m%d_%H%M%S}_hodnotenie.csv"
    res.to_csv(out)
    print("Tabuľky:", *paths, sep="\n  ")
    print()
    print(res.to_string())

    by_model = df[filled].groupby("model", sort=False)[cols].mean()
    fig, ax = plt.subplots(figsize=(max(8, 2.2 * len(cols)), 4.5))
    width = 0.8 / len(by_model)
    for j, (m, row) in enumerate(by_model.iterrows()):
        pos = [i - 0.4 + width * (j + 0.5) for i in range(len(cols))]
        vals = [row[c] / manual[c][1] for c in cols]
        ax.bar(pos, vals, width * 0.92, color=COLORS[j % len(COLORS)], label=m)
        for x, v in zip(pos, vals):
            if pd.notna(v):
                ax.text(x, v + 0.01, f"{v:.2f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(range(len(cols)), [manual[c][0] for c in cols])
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("podiel z maxima")
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, color="#e4e3df")
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=len(by_model))
    fig.tight_layout()
    png = out.with_suffix(".png")
    fig.savefig(png, dpi=200)
    print(f"\nSúhrn: {out}\nGraf: {png}")
