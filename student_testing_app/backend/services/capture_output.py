# ============================================================
# AdaptPy - spúšťanie a porovnávanie kódu v testoch (predtest, hlavný test).
#
# Kód študenta AJ referenčné riešenie sa spúšťajú v izolovanom kontajneri
# 'runner' (rovnako ako cvičenia) - NIE v procese backendu. Backend tak
# nevykonáva cudzí kód, nemôže ho zhodiť nekonečná slučka ani nemôže
# študent siahnuť na jeho súbory/premenné prostredia.
# ============================================================
import ast
import math
import re
import threading
from collections import OrderedDict

from services.code_runner import execute

RANDOM_STATE = 82

# Pôvodné správanie: `import random` sa z kódu odstráni a `random` je vopred
# nasadená inštancia Random(RANDOM_STATE) (+ `shuffle`), aby bol výstup
# študenta a referenčného riešenia deterministický a porovnateľný.
_PRELUDE = (
    "import random as _rnd_mod\n"
    f"random = _rnd_mod.Random({RANDOM_STATE})\n"
    "shuffle = random.shuffle\n"
)
_RANDOM_IMPORT = re.compile(r"^\s*(import random|from random import)")

# Tolerancia pri porovnávaní desatinných čísel (rovnaká ako doteraz).
FLOAT_TOLERANCE = 1e-2


class RunnerUnavailable(Exception):
    """Sandbox na spúšťanie kódu nie je dostupný (nie je to chyba študenta)."""


def capture_output(source_code):
    """
    Spustí kód v sandboxe a vráti (stdout_ako_text, chyba).
    Pri chybe v kóde je výstup "" a chyba je text výnimky (rovnako ako doteraz).
    Ak sandbox nie je dostupný, vyhodí RunnerUnavailable.
    """
    code = "\n".join(
        line for line in (source_code or "").splitlines()
        if not _RANDOM_IMPORT.match(line)
    )
    res = execute(_PRELUDE, code, separate_stderr=True)
    if res.get("runner_down"):
        raise RunnerUnavailable(res.get("error") or "Spúšťač kódu nie je dostupný.")
    if not res.get("ok"):
        return "", res.get("error") or "Chyba pri behu kódu."
    return (res.get("output") or "").strip(), None


# Referenčný výstup je pre otázku deterministický (fixný seed), takže ho stačí
# spočítať raz za proces a nespúšťať sandbox pri každej odpovedi.
# (Gunicorn workery majú vlákna -> prístup k cache chráni zámok.)
_EXPECTED_CACHE = OrderedDict()
_EXPECTED_CACHE_MAX = 512
_cache_lock = threading.Lock()


def expected_output(question_id, solution_code):
    """(výstup, chyba) referenčného riešenia otázky; úspešné výsledky sa cachujú."""
    key = (question_id, hash(solution_code))
    with _cache_lock:
        if key in _EXPECTED_CACHE:
            _EXPECTED_CACHE.move_to_end(key)
            return _EXPECTED_CACHE[key], None

    out, err = capture_output(solution_code)    # sandbox mimo zámku (môže trvať sekundy)
    if err is None:
        with _cache_lock:
            _EXPECTED_CACHE[key] = out
            while len(_EXPECTED_CACHE) > _EXPECTED_CACHE_MAX:
                _EXPECTED_CACHE.popitem(last=False)
    return out, err


# ------------------------------------------------------------
# Porovnávanie výstupov
# ------------------------------------------------------------
_NUMBER = re.compile(r"[-+]?\d*\.\d+|[-+]?\d+")


def normalize_output(output):
    return re.sub(r"\s+", "", output).lower().strip()


def extract_numbers(output):
    """Extrahuje všetky čísla z textu ako floaty."""
    return [float(num) for num in _NUMBER.findall(output)]


def floats_close(a, b, tol=FLOAT_TOLERANCE):
    return abs(a - b) < tol


def _values_equal(a, b):
    """Rekurzívna rovnosť literálov; čísla sa porovnávajú s toleranciou."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=0.0, abs_tol=FLOAT_TOLERANCE)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return (type(a) is type(b) and len(a) == len(b)
                and all(_values_equal(x, y) for x, y in zip(a, b)))
    if isinstance(a, dict) and isinstance(b, dict):
        return (a.keys() == b.keys()
                and all(_values_equal(a[k], b[k]) for k in a))
    return a == b


def _literal(text):
    """Bezpečné vyhodnotenie Python literálu (žiadny eval - výstup je nedôveryhodný)."""
    try:
        return True, ast.literal_eval(text.strip())
    except Exception:
        return False, None


def _numbers_template(text):
    """Text s číslami nahradenými '#' (na porovnanie slov) + zoznam čísel v poradí."""
    nums = extract_numbers(text)
    template = _NUMBER.sub("#", text)
    return normalize_output(template), nums


def compare_outputs(student_output, expected_output):
    """
    Zhoda výstupu študenta s referenčným výstupom. Postupne:
      1. rovnaký text (bez ohľadu na medzery a veľkosť písmen),
      2. rovnaká hodnota po ast.literal_eval (zoznamy/slovníky/čísla, floaty s toleranciou),
      3. rovnaký text okolo čísel A rovnaký počet čísel v rovnakom poradí,
         pričom každé číslo sa zhoduje s toleranciou (napr. 3.14 vs 3.1416).
    Čísla sa už NEporovnávajú "ľubovoľné s ľubovoľným" - zlý výstup so
    zhodou jedného čísla sa neuzná.
    """
    if normalize_output(student_output) == normalize_output(expected_output):
        return True

    ok_s, val_s = _literal(student_output)
    ok_e, val_e = _literal(expected_output)
    if ok_s and ok_e:
        return _values_equal(val_s, val_e)

    tpl_s, nums_s = _numbers_template(student_output)
    tpl_e, nums_e = _numbers_template(expected_output)
    if nums_s and nums_e and tpl_s == tpl_e and len(nums_s) == len(nums_e):
        return all(floats_close(s, e) for s, e in zip(nums_s, nums_e))

    return False
