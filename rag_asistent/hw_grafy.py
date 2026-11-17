"""Spoji behy hw_eval.py, spravi tabulky, McNemarove testy a grafy do data/eval/grafy/."""
import argparse
import json
from math import comb
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import DATA
from hw_eval import summarize

METRICS = {
    "presnost": "Vyvážená presnosť",
    "ciste_potvrdil": "Potvrdené správne riešenia",
    "chybne_odhalil": "Odhalené chybné riešenia",
    "odhalil_max_0_5b": "Odhalené vážne chyby (≤ 0,5 b)",
}
CONFIG_ORDER = [p + r + z for z in ("", " + zadanie") for p in ("krysanova", "verdikt") for r in ("", " + RAG")]
# farby modelov v pevnom poradi
COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def load(folder, od=None, models=None):
    rows, skipped = [], 0
    for path in sorted(folder.glob("*.jsonl")):
        if od and path.stem[:8] < od:
            continue
        recs = [json.loads(l) for l in path.open(encoding="utf-8")]
        if not recs or "seed" not in recs[0]:
            skipped += 1
            continue
        rows.extend(recs)
    if skipped:
        print(f"Preskočené staršie behy bez seedu: {skipped}")
    if not rows:
        raise SystemExit(f"V {folder} nie sú výsledky s uloženým seedom. Spusti hw_eval.py.")
    df = pd.DataFrame(rows)
    think = df.think.fillna("None").astype(str).str.lower()
    df["model_popis"] = df.model + np.where(think.isin(["none", "nan"]), "", " (think " + think + ")")
    if models:
        df = df[df.model.isin(models) | df.model_popis.isin(models)]
    zad = df["zadanie"].fillna(False).astype(bool) if "zadanie" in df else False
    df["nastavenie"] = df.prompt + np.where(df.rag, " + RAG", "") + np.where(zad, " + zadanie", "")
    # ten isty seed viackrat -> posledny beh
    last = df.groupby(["model_popis", "nastavenie", "seed"]).beh.transform("max")
    df = df[df.beh == last].copy()
    df["said_correct"] = df.said_correct.astype("boolean")
    return df


def metrics_per_seed(df):
    parts = []
    for (label, cfg, seed), g in df.groupby(["model_popis", "nastavenie", "seed"]):
        s = summarize(g.assign(model=label), with_judge=False).reset_index()
        s["nastavenie"], s["seed"], s["pripadov"] = cfg, seed, len(g)
        parts.append(s)
    return pd.concat(parts, ignore_index=True)


def aggregate(per_seed):
    cols = list(METRICS) + ["odhalil_0_75b", "vyhrada_vytkol", "prazdne", "jazyk_ok", "unik_kodu", "cas_s", "tok_per_s"]
    g = per_seed.groupby(["model", "nastavenie"])
    out = g[cols].mean().round(3)
    for c in METRICS:
        out[c + "_sd"] = g[c].std().round(3)
    out["seedov"] = g.seed.nunique()
    out["pripadov"] = g.pripadov.sum()
    return out.reset_index()


def mcnemar(a_ok, b_ok):
    """Presny McNemarov test, vrati (b, c, p)."""
    b, c = int((a_ok & ~b_ok).sum()), int((~a_ok & b_ok).sum())
    n = b + c
    if n == 0:
        return b, c, 1.0
    p = 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return b, c, min(1.0, p)


def paired_tests(df):
    """Porovnanie na tych istych rieseniach (chyba + ciste)."""
    d = df[df.skupina.isin(["chyba", "ciste"]) & ~df.prazdna.astype(bool) & df.said_correct.notna()].copy()
    d["ok"] = d.said_correct.astype(bool) == d.spravne.astype(bool)
    d["kluc"] = d[["seed", "rok", "uloha", "student", "skupina", "body"]].astype(str).agg("|".join, axis=1)
    pivot = d.pivot_table(index="kluc", columns=["model_popis", "nastavenie"], values="ok", aggfunc="first")

    def compare(a, b, what):
        if a not in pivot or b not in pivot:
            return None
        pair = pivot[[a, b]].dropna()
        if pair.empty:
            return None
        aa, bb = pair[a].astype(bool), pair[b].astype(bool)
        n01, n10, p = mcnemar(aa, bb)
        return {"porovnanie": what, "A": " / ".join(a), "B": " / ".join(b), "riesenii": len(pair),
                "A_spravne": round(aa.mean(), 3), "B_spravne": round(bb.mean(), 3),
                "len_A": n01, "len_B": n10, "p": round(p, 4), "vyznamne_0_05": p < 0.05}

    tests = []
    models = sorted(d.model_popis.unique())
    cfgs = [c for c in CONFIG_ORDER if c in set(d.nastavenie)]
    for cfg in cfgs:  # modely medzi sebou
        for i, m1 in enumerate(models):
            for m2 in models[i + 1:]:
                tests.append(compare((m1, cfg), (m2, cfg), "model"))
    for m in models:  # RAG a prompt v ramci modelu
        for z in ("", " + zadanie"):
            for p in ("krysanova", "verdikt"):
                tests.append(compare((m, p + z), (m, p + " + RAG" + z), "RAG"))
            for r in ("", " + RAG"):
                tests.append(compare((m, "krysanova" + r + z), (m, "verdikt" + r + z), "prompt"))
        for p in ("krysanova", "verdikt"):
            for r in ("", " + RAG"):
                tests.append(compare((m, p + r), (m, p + r + " + zadanie"), "zadanie"))
    return pd.DataFrame([t for t in tests if t])


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def chart_metrics(agg, models, cfgs, path):
    fig, axes = plt.subplots(2, 2, figsize=(max(11, 2.4 * len(cfgs)), 7.5), sharey=True)
    x = np.arange(len(cfgs))
    width = 0.8 / len(models)
    for ax, (col, title) in zip(axes.flat, METRICS.items()):
        style(ax)
        for j, m in enumerate(models):
            sub = agg[agg.model == m].set_index("nastavenie").reindex(cfgs)
            pos = x - 0.4 + width * (j + 0.5)
            sd = sub[col + "_sd"].fillna(0).values
            ax.bar(pos, sub[col].values, width * 0.92, color=COLORS[j % len(COLORS)], label=m,
                   yerr=sd if sd.any() else None, error_kw={"ecolor": INK2, "elinewidth": 1, "capsize": 3})
            for xi, v in zip(pos, sub[col].values):
                if pd.notna(v):
                    ax.text(xi, 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=8, color="white")
        if col == "presnost":
            ax.axhline(0.5, color=INK2, linestyle="--", linewidth=1)
            ax.text(len(cfgs) - 0.45, 0.51, "náhoda", ha="right", va="bottom", fontsize=8, color=INK2)
        ax.set_title(title, fontsize=11, color=INK, loc="left")
        ax.set_xticks(x, [c.replace(" + zadanie", "\n+ zadanie") for c in cfgs])
        ax.set_ylim(0, 1)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(models), frameon=False, fontsize=10)
    seeds = int(agg.seedov.max())
    fig.text(0.01, 0.005, f"Stĺpec = priemer cez {seeds} seed{'y' if 1 < seeds < 5 else 'ov' if seeds >= 5 else ''}"
             + (", čiara = smerodajná odchýlka." if seeds > 1 else "."), fontsize=8, color=INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 0.94))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def chart_tradeoff(per_seed, agg, models, cfgs, path):
    markers = dict(zip(CONFIG_ORDER, ["o", "s", "^", "D", "v", "P", "X", "*"]))
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    style(ax)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    lo = min(0.3, np.floor(min(per_seed.ciste_potvrdil.min(), per_seed.chybne_odhalil.min()) * 10) / 10)
    ax.plot([lo, 1 - lo], [1 - lo, lo], color=INK2, linestyle="--", linewidth=1)
    ax.text(1 - lo - 0.02, lo + 0.04, "náhoda", ha="right", fontsize=8, color=INK2, rotation=-45)
    for j, m in enumerate(models):
        color = COLORS[j % len(COLORS)]
        for cfg in cfgs:
            pts = per_seed[(per_seed.model == m) & (per_seed.nastavenie == cfg)]
            ax.scatter(pts.ciste_potvrdil, pts.chybne_odhalil, s=22, color=color, alpha=0.3,
                       marker=markers[cfg], linewidths=0)
            mean = agg[(agg.model == m) & (agg.nastavenie == cfg)]
            ax.scatter(mean.ciste_potvrdil, mean.chybne_odhalil, s=90, color=color, marker=markers[cfg],
                       edgecolors="white", linewidths=1.5, zorder=3)
    for j, m in enumerate(models):  # legenda: farba = model, tvar = nastavenie
        ax.scatter([], [], color=COLORS[j % len(COLORS)], s=60, label=m)
    for cfg in cfgs:
        ax.scatter([], [], color=INK2, marker=markers[cfg], s=50, label=cfg)
    ax.legend(frameon=False, fontsize=9, loc="lower left")
    ax.set_xlim(lo, 1)
    ax.set_ylim(lo, 1)
    ax.set_xlabel("Potvrdené správne riešenia (viac = menej falošných poplachov)", color=INK2)
    ax.set_ylabel("Odhalené chybné riešenia", color=INK2)
    ax.set_title("Kompromis medzi potvrdzovaním a odhaľovaním chýb", loc="left", color=INK, fontsize=11)
    fig.text(0.01, 0.005, "Veľké body = priemer, malé = jednotlivé seedy. Ideál je vpravo hore.",
             fontsize=8, color=INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def chart_speed(df, models, path):
    fig, ax = plt.subplots(figsize=(7.5, 0.9 + 0.7 * len(models)))
    style(ax)
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    times = [df[df.model_popis == m].total_s.mean() for m in models]
    toks = [df[df.model_popis == m].tok_per_s.median() for m in models]
    y = np.arange(len(models))[::-1]
    ax.barh(y, times, 0.55, color=[COLORS[j % len(COLORS)] for j in range(len(models))])
    for yi, t, tk in zip(y, times, toks):
        ax.text(t, yi, f"  {t:.1f} s  ({tk:.0f} tokenov/s)", va="center", fontsize=9, color=INK)
    ax.set_yticks(y, models)
    ax.set_xlim(0, max(times) * 1.45)
    ax.set_xlabel("Priemerný čas na jednu odpoveď (s)", color=INK2)
    ax.set_title("Rýchlosť na lokálnom PC", loc="left", color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def chart_tasks(df, agg, models, path):
    rows, labels = [], []
    for m in models:
        best = agg[agg.model == m].sort_values("presnost", ascending=False).nastavenie.iloc[0]
        d = df[(df.model_popis == m) & (df.nastavenie == best) & df.skupina.isin(["chyba", "ciste"])
               & ~df.prazdna.astype(bool) & df.said_correct.notna()].copy()
        d["ok"] = d.said_correct.astype(bool) == d.spravne.astype(bool)
        per = d.groupby(["rok", "uloha", "skupina"]).ok.mean().unstack()
        rows.append(per.mean(axis=1))  # vyvazena presnost v ulohe
        labels.append(f"{m}\n({best})")
    table = pd.concat(rows, axis=1).T
    cols = [f"{r % 100}/h{u:02d}" for r, u in table.columns]
    fig, ax = plt.subplots(figsize=(max(8, 0.48 * len(cols)), 1.2 + 0.9 * len(models)))
    im = ax.imshow(table.values.astype(float), cmap="Blues", vmin=0, vmax=1, aspect="auto")
    for i in range(table.shape[0]):
        for j in range(table.shape[1]):
            v = table.values[i, j]
            if pd.notna(v):
                ax.text(j, i, f"{v:.2f}".lstrip("0"), ha="center", va="center", fontsize=7,
                        color="white" if v > 0.6 else INK)
    ax.set_xticks(range(len(cols)), cols, rotation=90, fontsize=8, color=INK2)
    ax.set_yticks(range(len(labels)), labels, fontsize=9, color=INK)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=8, colors=INK2)
    ax.set_title("Presnosť podľa úlohy (rok/úloha), najlepšie nastavenie modelu", loc="left", color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vstup", type=Path, default=DATA / "eval" / "vysledky")
    ap.add_argument("--vystup", type=Path, default=DATA / "eval" / "grafy")
    ap.add_argument("--od", default=None, help="len behy od dátumu RRRRMMDD")
    ap.add_argument("--models", nargs="+", default=None)
    args = ap.parse_args()

    df = load(args.vstup, args.od, args.models)
    models = sorted(df.model_popis.unique(), key=lambda m: (m.split(":")[0] != "gpt-oss", m))
    cfgs = [c for c in CONFIG_ORDER if c in set(df.nastavenie)]
    args.vystup.mkdir(parents=True, exist_ok=True)

    per_seed = metrics_per_seed(df)
    agg = aggregate(per_seed)
    agg.to_csv(args.vystup / "porovnanie.csv", index=False)
    tests = paired_tests(df)
    tests.to_csv(args.vystup / "testy.csv", index=False)

    chart_metrics(agg, models, cfgs, args.vystup / "1_metriky.png")
    chart_tradeoff(per_seed, agg, models, cfgs, args.vystup / "2_kompromis.png")
    chart_speed(df, models, args.vystup / "3_rychlost.png")
    chart_tasks(df, agg, models, args.vystup / "4_ulohy.png")

    pd.set_option("display.width", 200)
    show = ["model", "nastavenie", "seedov", "pripadov"] + list(METRICS) + ["presnost_sd", "jazyk_ok", "cas_s"]
    print("\nPriemer cez seedy:\n" + agg[show].to_string(index=False))
    if len(tests):
        print("\nPárové testy (rovnaké riešenia, McNemar; p < 0,05 = rozdiel nie je náhoda):")
        print(tests[["porovnanie", "A", "B", "riesenii", "A_spravne", "B_spravne", "p", "vyznamne_0_05"]]
              .to_string(index=False))
    print(f"\nGrafy a tabuľky: {args.vystup}")


if __name__ == "__main__":
    main()
