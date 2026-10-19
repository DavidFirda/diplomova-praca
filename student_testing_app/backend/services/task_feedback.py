# ============================================================
# AdaptPy - spätná väzba k nesprávnemu pokusu v úlohách ("čo bolo zlé").
#
# Počíta sa deterministicky zo spusteného kódu (NIE pomocou AI) a neprezrádza
# očakávaný výstup ani riešenie - len povie, v čom sa výstup líši.
# build_feedback() vracia jazykovo neutrálne {"kind", "params"} (to sa ukladá),
# feedback_payload() k nim pridá text v jazyku študenta.
# ============================================================
import re

from services.capture_output import _NUMBER, _literal, extract_numbers, normalize_output
from services.task_text import normalize_lang, tt


def error_summary(error):
    """(typ chyby, posledný riadok chyby) z textu výnimky."""
    lines = [ln.strip() for ln in (error or "").strip().splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    match = re.match(r"([A-Za-z_]*(?:Error|Exception|Interrupt))\b", last)
    return (match.group(1) if match else ""), last[:300]


def error_explanation(error_type, lang="sk"):
    key = f"err.{error_type}"
    text = tt(lang, key)
    return text if text != key else tt(lang, "err.generic")


def _non_empty_lines(text):
    return [ln for ln in (text or "").splitlines() if ln.strip()]


def build_feedback(student_out, student_err, expected_out):
    """
    {"kind", "params"} - čo je na výstupe študenta zlé.
    kind: error | no_output | line_count | type_differs | numbers_count |
          numbers_value | text_differs
    """
    if student_err:
        etype, last = error_summary(student_err)
        return {"kind": "error", "params": {"error_type": etype, "error": last or "?"}}

    student_out, expected_out = student_out or "", expected_out or ""
    if not student_out.strip():
        return {"kind": "no_output", "params": {}}

    got, exp = len(_non_empty_lines(student_out)), len(_non_empty_lines(expected_out))
    if got != exp:
        return {"kind": "line_count", "params": {"got": got, "expected": exp}}

    ok_s, val_s = _literal(student_out)
    ok_e, val_e = _literal(expected_out)
    if ok_s and ok_e and type(val_s) is not type(val_e):
        return {"kind": "type_differs",
                "params": {"got": type(val_s).__name__, "expected": type(val_e).__name__}}

    nums_s, nums_e = extract_numbers(student_out), extract_numbers(expected_out)
    text_s = normalize_output(_NUMBER.sub("#", student_out))
    text_e = normalize_output(_NUMBER.sub("#", expected_out))
    if text_s == text_e:
        if len(nums_s) != len(nums_e):
            return {"kind": "numbers_count", "params": {"got": len(nums_s), "expected": len(nums_e)}}
        wrong = sum(1 for a, b in zip(nums_s, nums_e) if abs(a - b) >= 1e-2)
        return {"kind": "numbers_value", "params": {"wrong": wrong, "total": len(nums_e)}}

    return {"kind": "text_differs", "params": {}}


def feedback_message(kind, params, lang="sk"):
    """Text spätnej väzby v danom jazyku (pri chybe kódu aj vysvetlenie chyby)."""
    lang = normalize_lang(lang)
    params = params or {}
    message = tt(lang, f"fb.{kind}", **{k: params.get(k, "") for k in (
        "error", "got", "expected", "wrong", "total")})
    if kind == "error":
        message += " " + error_explanation(params.get("error_type", ""), lang)
    return message


def feedback_payload(feedback, lang="sk"):
    """Slovník pre klienta: kind + params + text v jazyku študenta."""
    if not feedback:
        return None
    return {
        "kind": feedback["kind"],
        "params": feedback.get("params", {}),
        "message": feedback_message(feedback["kind"], feedback.get("params"), lang),
    }
