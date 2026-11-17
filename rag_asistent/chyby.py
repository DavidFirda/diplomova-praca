"""Typy chyb studenta: vlozenie chyby do spravneho kodu (mutacia) a urcenie typu chyby z dvoch verzii kodu."""
import ast
import copy
import difflib
import re

import sandbox

LABELS = {
    "chyba_dvojbodka": "chýbajúca dvojbodka",
    "preklep_v_nazve": "preklep v názve funkcie alebo premennej",
    "odsadenie": "zlé odsadenie (IndentationError)",
    "ina_syntakticka": "iná syntaktická chyba",
    "hranice_cyklu": "zlé hranice cyklu (o jedna viac alebo menej)",
    "podmienka": "zlé porovnanie v podmienke (napr. < namiesto <=)",
    "logicky_operator": "zlý logický operátor (and/or)",
    "aritmetika": "zlý aritmetický operátor (napr. / namiesto //)",
    "inicializacia": "zlá počiatočná hodnota premennej",
    "akumulator": "prepisuje hodnotu namiesto pripočítania (= namiesto +=)",
    "index": "zlý index (o jedna vedľa)",
    "zly_blok": "príkaz v zlom bloku (napr. return alebo print vnútri cyklu)",
    "print_namiesto_return": "print namiesto return",
    "kopia": "zoznam sa neskopíruje (b = a namiesto b = a.copy())",
    "self": "chýba self. v metóde",
    "chyba_za_behu": "iná chyba za behu",
    "ina_logicka": "iná logická chyba (zlý výstup)",
}
SYNTAX = {"chyba_dvojbodka", "preklep_v_nazve", "odsadenie", "ina_syntakticka"}
# poradie je aj poradie pri urcovani typu
MUTATIONS = ["hranice_cyklu", "podmienka", "logicky_operator", "aritmetika", "inicializacia", "akumulator",
             "index", "zly_blok", "print_namiesto_return", "kopia", "self"]


def label(kind):
    return LABELS.get(kind, kind)


def group(kind):
    if not kind:
        return ""
    return "syntakticka" if kind in SYNTAX else "logicka"


def normalize(code):
    """Rovnaky zapis kodu (bez komentarov a roznych medzier), ak sa da parsovat."""
    try:
        return ast.unparse(ast.parse(sandbox.clean_code(code)))
    except (SyntaxError, ValueError):
        return None


# ---------- mutacie ----------

class _Nth(ast.NodeTransformer):
    """Nahradi n-ty vyskyt uzla, ktory splna podmienku (n=-1 len pocita)."""

    def __init__(self, match, make, n=-1):
        self.match, self.make, self.n, self.i = match, make, n, -1

    def visit(self, node):
        node = self.generic_visit(node)
        if self.match(node):
            self.i += 1
            if self.i == self.n:
                return self.make(node)
        return node


def _shift(e, d):
    if isinstance(e, ast.Constant) and type(e.value) is int:
        return ast.Constant(e.value + d)
    if isinstance(e, ast.BinOp) and isinstance(e.right, ast.Constant) and e.right.value == 1:
        if (isinstance(e.op, ast.Add) and d < 0) or (isinstance(e.op, ast.Sub) and d > 0):
            return e.left  # n + 1 -> n
    return ast.BinOp(e, ast.Add() if d > 0 else ast.Sub(), ast.Constant(1))


def _is_str(e):
    return isinstance(e, ast.JoinedStr) or (isinstance(e, ast.Constant) and isinstance(e.value, str))


def _plus_minus_one(n):
    # n - 1 -> n + 1 je skor zla hranica alebo index, nie aritmetika
    return isinstance(n.op, (ast.Add, ast.Sub)) and isinstance(n.right, ast.Constant) and n.right.value == 1


CMP_SWAP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
ARITH_SWAP = {ast.FloorDiv: ast.Div, ast.Div: ast.FloorDiv, ast.Add: ast.Sub, ast.Sub: ast.Add,
              ast.Mult: ast.Add, ast.Mod: ast.FloorDiv, ast.Pow: ast.Mult}
INDEX_NAMES = {"i", "j", "k", "idx", "index"}


def _range_make(d):
    def make(n):
        k = 1 if len(n.args) >= 2 else 0
        n.args[k] = _shift(n.args[k], d)
        return n
    return make


def _swap_op(n, table):
    n.op = table[type(n.op)]()
    return n


def _swap_cmp(n):
    n.ops = [CMP_SWAP[type(n.ops[0])]()]
    return n


def _swap_bool(n):
    n.op = ast.Or() if isinstance(n.op, ast.And) else ast.And()
    return n


def _index_make(n):
    s = n.slice
    if isinstance(s, ast.Constant):
        n.slice = ast.Constant(s.value + 1 if s.value >= 0 else s.value - 1)
    else:
        n.slice = ast.BinOp(s, ast.Add(), ast.Constant(1))
    return n


def _uncopy(n):
    if isinstance(n, ast.Call):
        return n.func.value if isinstance(n.func, ast.Attribute) else n.args[0]
    return n.value


def _is_copy(n):
    if isinstance(n, ast.Call) and not n.args and isinstance(n.func, ast.Attribute) and n.func.attr == "copy":
        return isinstance(n.func.value, ast.Name)
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "list" and len(n.args) == 1:
        return isinstance(n.args[0], ast.Name)
    return (isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Slice) and isinstance(n.value, ast.Name)
            and n.slice.lower is None and n.slice.upper is None and n.slice.step is None)


# typ -> (podmienka na uzol, zmena uzla)
EXPR_MUTATIONS = {
    "hranice_cyklu": (lambda n: isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "range"
                      and 1 <= len(n.args) <= 3 and not n.keywords, None),
    "podmienka": (lambda n: isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in CMP_SWAP, _swap_cmp),
    "logicky_operator": (lambda n: isinstance(n, ast.BoolOp), _swap_bool),
    "aritmetika": (lambda n: isinstance(n, ast.BinOp) and type(n.op) in ARITH_SWAP and not _is_str(n.left)
                   and not _is_str(n.right) and not _plus_minus_one(n), lambda n: _swap_op(n, ARITH_SWAP)),
    "inicializacia": (lambda n: isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                      and isinstance(n.value, ast.Constant) and type(n.value.value) in (int, float) and n.value.value in (0, 1),
                      lambda n: ast.Assign(n.targets, ast.Constant(type(n.value.value)(1 - n.value.value)))),
    "akumulator": (lambda n: isinstance(n, ast.AugAssign) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult)),
                   lambda n: ast.Assign([n.target], n.value)),
    "index": (lambda n: isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Load) and (
        (isinstance(n.slice, ast.Constant) and type(n.slice.value) is int)
        or (isinstance(n.slice, ast.Name) and n.slice.id in INDEX_NAMES)), _index_make),
    "print_namiesto_return": (lambda n: isinstance(n, ast.Return) and n.value is not None,
                              lambda n: ast.Expr(ast.Call(ast.Name("print", ast.Load()), [n.value], []))),
    "kopia": (_is_copy, _uncopy),
    "self": (lambda n: isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self"
             and isinstance(n.ctx, ast.Load), lambda n: ast.Name(n.attr, ast.Load())),
}


def _is_print_or_return(s):
    return isinstance(s, ast.Return) or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)
                                         and isinstance(s.value.func, ast.Name) and s.value.func.id == "print")


def _block_sites(tree):
    """Miesta, kde je za cyklom return alebo print (da sa presunut do cyklu)."""
    out = []
    for node in ast.walk(tree):
        for field in ("body", "orelse"):
            body = getattr(node, field, None)
            if isinstance(body, list):
                out += [(body, i) for i in range(len(body) - 1)
                        if isinstance(body[i], (ast.For, ast.While)) and _is_print_or_return(body[i + 1])]
    return out


def _count(tree, kind):
    if kind == "zly_blok":
        return len(_block_sites(tree))
    t = _Nth(EXPR_MUTATIONS[kind][0], None)
    t.visit(copy.deepcopy(tree))
    return t.i + 1


def _apply(tree, kind, n, d=1):
    tree = copy.deepcopy(tree)
    if kind == "zly_blok":
        body, i = _block_sites(tree)[n]
        body[i].body.append(body.pop(i + 1))
    else:
        match, make = EXPR_MUTATIONS[kind]
        tree = _Nth(match, make or _range_make(d), n).visit(tree)
    return ast.unparse(ast.fix_missing_locations(tree))


def all_mutants(code, kind, limit=40):
    """Vsetky verzie kodu s jednou chybou daneho typu."""
    try:
        tree = ast.parse(sandbox.clean_code(code))
    except (SyntaxError, ValueError):
        return []
    out = []
    for n in range(min(_count(tree, kind), limit)):
        for d in ((-1, 1) if kind == "hranice_cyklu" else (1,)):
            try:
                out.append(_apply(tree, kind, n, d))
            except Exception:
                pass
    return out


def mutants(code, rng, kinds=MUTATIONS):
    """Pre kazdy typ jedna nahodna chyba: [(typ, spravny_kod, nespravny_kod)]. Spravny kod je normalizovany."""
    base = normalize(code)
    if base is None:
        return []
    out = []
    for kind in kinds:
        options = [m for m in all_mutants(base, kind) if m != base]
        if options:
            out.append((kind, base, rng.choice(options)))
    return out


def verified_mutants(code, rng, correct_run=None, kinds=MUTATIONS):
    """Mutacie, ktore naozaj pokazia program (spadne alebo vypise nieco ine), s vysledkami spustenia."""
    base = normalize(code)
    if base is None:
        return []
    ok = correct_run or sandbox.run(base)
    if not (ok.get("ok") and ok["stdout"].strip()):
        return []
    out = []
    for kind, good, bad_code in mutants(base, rng, kinds):
        bad = sandbox.run(bad_code)
        if bad.get("spustene") and bad.get("typ_chyby") != "Timeout" and (not bad["ok"] or bad["stdout"] != ok["stdout"]):
            out.append({"typ": kind, "spravny": good, "nespravny": bad_code, "ok": ok, "bad": bad})
    return out


# ---------- urcenie typu chyby ----------

def _diff_kind(correct, wrong):
    a, b = normalize(correct), normalize(wrong)
    if a is None or b is None:
        return None
    for kind in MUTATIONS:  # presne ako niektora mutacia
        if b in all_mutants(a, kind):
            return kind
    la, lb = a.splitlines(), b.splitlines()
    old, new = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, la, lb).get_opcodes():
        if op != "equal":
            old += la[i1:i2]
            new += lb[j1:j2]
    if not old and not new:
        return None
    if old and sorted(x.strip() for x in old) == sorted(x.strip() for x in new):
        return "zly_blok"
    o, n = "\n".join(old), "\n".join(new)

    def diff(pattern):
        return sorted(re.findall(pattern, o, re.M)) != sorted(re.findall(pattern, n, re.M))

    if "range(" in o and "range(" in n and diff(r"range\(.*?\)"):
        return "hranice_cyklu"
    if diff(r"<=|>=|==|!=|<|>"):
        return "podmienka"
    if diff(r"\b(?:and|or|not)\b"):
        return "logicky_operator"
    if re.search(r"\breturn\b", o) and "print(" in n and not re.search(r"\breturn\b", n):
        return "print_namiesto_return"
    if re.search(r"[+\-*]=", o) and not re.search(r"[+\-*]=", n):
        return "akumulator"
    if o.count("self.") > n.count("self."):
        return "self"
    if re.search(r"\.copy\(\)|\[:\]|\blist\(", o) and not re.search(r"\.copy\(\)|\[:\]|\blist\(", n):
        return "kopia"
    if diff(r"//|\*\*|[+\-*/%]"):
        return "aritmetika"
    if diff(r"\[[^\]]*\]"):
        return "index"
    if diff(r"^\s*\w+ = -?[\d.]+$"):
        return "inicializacia"
    return None


def classify(correct, wrong, correct_run, wrong_run):
    """Typ chyby podla spustenia a rozdielu medzi spravnym a nespravnym kodom."""
    if not wrong_run.get("spustene"):
        return "nespustene"
    if wrong_run["ok"] and wrong_run["stdout"] == correct_run.get("stdout"):
        return "rovnaky_vystup"
    if not wrong_run["ok"]:
        msg, typ = wrong_run["chyba"], wrong_run["typ_chyby"]
        if "expected ':'" in msg:
            return "chyba_dvojbodka"
        if typ in ("IndentationError", "TabError"):
            return "odsadenie"
        if typ == "SyntaxError":
            return "ina_syntakticka"
    kind = _diff_kind(correct, wrong)
    if kind:
        return kind
    if not wrong_run["ok"]:
        return "preklep_v_nazve" if wrong_run["typ_chyby"] == "NameError" else "chyba_za_behu"
    return "ina_logicka"


def output_pair(wrong, expected, limit=150):
    """Kratke ukazky zleho a ocakavaneho vystupu. Pri dlhom vystupe ukaze miesto, kde sa lisia,
    a pocet riadkov, inak by po skrateni vyzerali rovnako."""
    w, e = wrong.strip(), expected.strip()
    if len(w) <= limit and len(e) <= limit:
        return repr(w), repr(e)
    wl, el = w.splitlines(), e.splitlines()
    i = next((k for k in range(min(len(wl), len(el))) if wl[k] != el[k]), min(len(wl), len(el)))

    def cut(lines):
        start = max(0, i - 1)
        part = repr("\n".join(lines[start:i + 2])[:limit])
        return ("... " if start else "") + part + (" ..." if i + 2 < len(lines) else "") + f" [{len(lines)} lines]"
    return cut(wl), cut(el)


def run_text(ok, bad):
    """Co sa stalo pri spusteni nespravneho kodu, jednou vetou (EN, pre prompt)."""
    if bad["ok"]:
        w, e = output_pair(bad["stdout"], ok["stdout"])
        return f"wrong output {w}, expected {e}"
    return bad["chyba"]
