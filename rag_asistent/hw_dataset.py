"""Ohodnotene domace ulohy 2024 a 2025 -> data/eval/domace_ulohy.csv.
Nejde do RAG, je to len na vyhodnotenie modelov."""
import re
from collections import Counter

import pandas as pd

from config import DATA, HOMEWORKS, HW_YEARS

GRADE = re.compile(r"^#\s*Hodnotenie\s*:?\s*(.*)$", re.I | re.M)
SCORE = re.compile(r"^([0-9]+(?:[.,][0-9]+)?)\s*/\s*1\s*b?\s*(?:[-–:]\s*(.*))?$", re.I)
TEMPLATE = re.compile(r"^#\s*(TODO|-{3,}|Úloha|\d+[.)]?\s|Podrobný popis|Použité zdroje|Čas:)", re.I)
HEADER = re.compile(r"^#\s*(-\*-.*-\*-|Použité zdroje|Čas\s*:|Podrobný popis|Hodnotenie)", re.I)
# slova pochvaly, ine slovo v komentari = vyhrada
PRAISE = set("""super skvelá skvelé skvelý skvele pekné pekná pekný pekne výborná výborné výborne výborný
perfektné perfektná perfektne perfektný paráda parádne dobrá dobré dobre dobrý veľmi velmi fajn ok okej
práca riešenie riešenia robota len tak ďalej dalej aj takto je to celkom naozaj fakt úplne
good great nice job work well done excellent perfect bravo""".split())
EMAIL = re.compile(r"[\w.%+-]+@[\w.-]+\.[a-z]{2,}", re.I)


def read(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp1250", errors="replace")


def parse(text):
    """Vrati (body alebo None, komentar, kod bez hlavicky)."""
    lines = text.splitlines()
    score, comment, skip = None, [], set()
    m = GRADE.search(text)
    if m:
        idx = text[:m.start()].count("\n")
        skip.add(idx)
        sm = SCORE.match(m.group(1).strip())
        if sm:
            score = float(sm.group(1).replace(",", "."))
            if sm.group(2):
                comment.append(sm.group(2).strip())
        # komentar pokracuje po prazdny riadok alebo text sablony
        for j in range(idx + 1, len(lines)):
            line = lines[j].strip()
            if not line.startswith("#") or TEMPLATE.match(line):
                break
            comment.append(line.lstrip("#").strip())
            skip.add(j)
    code = "\n".join(l for i, l in enumerate(lines) if i not in skip and not HEADER.match(l.strip()))
    code = EMAIL.sub("<email>", code).strip()
    return score, EMAIL.sub("<email>", " ".join(c for c in comment if c)), code


def group(score, comment):
    if score is None:
        return "nehodnotene"
    if score < 1:
        return "chyba"
    words = re.findall(r"\w+", comment.lower())
    return "ciste" if all(w in PRAISE for w in words) else "s_vyhradou"


def main():
    rows = []
    for path in sorted(HOMEWORKS.glob("*/*/*.py")):
        year, student = path.parts[-3], path.parts[-2]
        m = re.match(r"h0?(\d+)", path.stem, re.I)
        if not m or not year.isdigit() or int(year) not in HW_YEARS:
            continue
        text = read(path)
        score, comment, code = parse(text)
        link = re.search(r"homework0?(\d+)\.md", text, re.I)
        variant = not re.fullmatch(r"h0?\d+", path.stem, re.I)  # h05-2.py, h05 (1).py, h03Done.py ...
        rows.append({
            "rok": int(year),
            "student": int(student) if student.isdigit() else student,
            "uloha": int(m.group(1)),
            "pokus": 2 if variant else 1,
            "subor_variant": variant,
            "zadanie_odkaz": int(link.group(1)) if link else None,
            "_kod_bez_komentarov": re.sub(r"\s+", "", re.sub(r"#.*", "", code)),
            "hodnotene": score is not None,
            "body": score,
            "skupina": group(score, comment),
            "komentar": comment,
            "kod": code,
            "riadkov": code.count("\n") + 1,
        })

    df = pd.DataFrame(rows)
    n_files = len(df)
    graded_task = df.groupby(["rok", "student", "uloha"]).hodnotene.transform("any")
    graded = df[df.hodnotene].drop_duplicates(["rok", "student", "uloha", "_kod_bez_komentarov"])
    ungraded = (df[~df.hodnotene & ~graded_task & (df._kod_bez_komentarov.str.len() > 20)]  # bez prazdnych sablon
                .sort_values("subor_variant").drop_duplicates(["rok", "student", "uloha"]))
    df = (pd.concat([graded, ungraded]).drop(columns="_kod_bez_komentarov")
            .sort_values(["rok", "student", "uloha", "pokus"]))
    print(f"{n_files} súborov -> {len(df)} riešení (vynechané šablóny, duplikáty a neohodnotené staršie verzie)")
    out = DATA / "eval"
    out.mkdir(exist_ok=True)
    df.to_csv(out / "domace_ulohy.csv", index=False, encoding="utf-8-sig")

    print(f"Spolu {len(df)} riešení -> {out / 'domace_ulohy.csv'}\n")
    print(df.groupby(["rok", "skupina"]).size().unstack(fill_value=0).to_string())
    bad = df[df.zadanie_odkaz.notna() & (df.zadanie_odkaz != df.uloha)]
    if len(bad):
        print("\nNázov súboru a odkaz na zadanie sa nezhodujú:")
        print(bad[["rok", "student", "uloha", "zadanie_odkaz", "body", "komentar"]].to_string(index=False))
    print("\nDruhé pokusy (súbor s príponou) medzi hodnotenými:", int((df.hodnotene & (df.pokus == 2)).sum()))
    g = df[df.hodnotene]
    if len(g):
        print("\nRozdelenie bodov (len hodnotené):")
        print(g.groupby(["rok", "body"]).size().unstack(fill_value=0).to_string())
        print("\nNeplný počet bodov podľa úlohy:")
        print(g[g.body < 1].groupby(["uloha", "rok"]).size().unstack(fill_value=0).to_string())
        words = Counter(w for c in g[g.body < 1].komentar for w in re.findall(r"\w{5,}", c.lower()))
        print("\nNajčastejšie slová v komentároch k chybám:", ", ".join(w for w, _ in words.most_common(15)))


if __name__ == "__main__":
    main()
