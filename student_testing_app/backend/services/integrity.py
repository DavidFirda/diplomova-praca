# ============================================================
# AdaptPy - KONTROLA ORIGINALITY odpovedí (Úlohy, predtest, hlavný test).
#
# Klient (frontend/js/core/originality.js) v editore:
#   - zakáže vkladanie (Ctrl+V, pravé tlačidlo, drag&drop) textu zvonku,
#   - počíta, ako študent píše od posledného započítaného odoslania (úsek):
#     napísané znaky, opravy (mazanie, undo), zablokované vloženia, rytmus kláves.
#
# Tieto metriky pošle spolu s kódom. O tom, či je odpoveď PODOZRIVÁ, rozhoduje
# server (tu), aby pravidlo bolo na jednom mieste. Pri podozrivej odpovedi sa
# kód NEspustí ani nezapočíta - študent najprv v okne potvrdí, či je to jeho
# práca (alebo prizná iný zdroj). Odpoveď sa potom uloží s "red flagom",
# ktorý admin vidí pri pokuse/odpovedi a môže ho zrušiť.
#
# Je to heuristika, nie dôkaz: red flag znamená "pozri sa na to", nie plagiát.
# ============================================================
import json
from datetime import datetime, timezone

MIN_TYPED_FOR_CHECK = 40        # pod týmto počtom napísaných znakov sa úsek nehodnotí
MIN_KEYS_FOR_RHYTHM = 40        # min. počet úderov na posúdenie rytmu
UNIFORM_RHYTHM_CV = 0.25        # variačný koeficient intervalov kláves (človek ~0.5-1.5)
MAX_HUMAN_CPM = 700             # znakov za minútu pri súvislom písaní
MIN_TYPED_FOR_SPEED = 80
INSERT_TOLERANCE = 30           # o koľko môže kód narásť nad napísané znaky (odsadenie, ...)

CONFIRMATIONS = ("own_work", "outside_source")

# poradie = poradie zobrazenia
REASONS = (
    "no_telemetry",         # klient neposlal metriky (obídený editor / priame volanie API)
    "unexplained_insert",   # kód narástol viac, než študent napísal (vloženie obídené)
    "no_corrections",       # súvislo napísané bez jedinej opravy
    "uniform_rhythm",       # strojovo pravidelné údery kláves
    "too_fast",             # nadľudská rýchlosť písania
)


def _int(v, default=0, hi=10_000_000):
    try:
        return max(0, min(int(v), hi))
    except (TypeError, ValueError):
        return default


def _float(v):
    try:
        f = float(v)
        return f if f == f and f >= 0 else None     # NaN / záporné -> None
    except (TypeError, ValueError):
        return None


def sanitize(raw):
    """Očistené metriky od klienta (alebo None, ak chýbajú)."""
    if not isinstance(raw, dict):
        return None
    confirmation = raw.get("confirmation")
    return {
        "typed_chars": _int(raw.get("typed_chars")),
        "keystrokes": _int(raw.get("keystrokes")),
        "corrections": _int(raw.get("corrections")),
        "deleted_chars": _int(raw.get("deleted_chars")),
        "paste_blocked": _int(raw.get("paste_blocked")),
        "internal_chars": _int(raw.get("internal_chars")),
        # kód vložený z AI asistenta po potvrdení študentom (admin to vidí pri pokuse)
        "assistant_chars": _int(raw.get("assistant_chars")),
        "assistant_inserts": _int(raw.get("assistant_inserts")),
        "baseline_len": _int(raw.get("baseline_len")),
        "active_ms": _int(raw.get("active_ms")),
        "interval_cv": _float(raw.get("interval_cv")),
        "confirmation": confirmation if confirmation in CONFIRMATIONS else None,
    }


def evaluate(code, raw):
    """
    -> (metrics | None, [dôvody]). Prázdny zoznam = nič podozrivé.
    `code` je odosielaný kód, `raw` objekt `integrity` z tela požiadavky.
    """
    m = sanitize(raw)
    if m is None:
        return None, ["no_telemetry"]

    reasons = []
    grown = len(code or "") - m["baseline_len"]
    explained = m["typed_chars"] + m["internal_chars"] + INSERT_TOLERANCE
    if grown > explained:
        reasons.append("unexplained_insert")

    typed = m["typed_chars"]
    if typed >= MIN_TYPED_FOR_CHECK and m["corrections"] == 0:
        reasons.append("no_corrections")

    cv = m["interval_cv"]
    if m["keystrokes"] >= MIN_KEYS_FOR_RHYTHM and cv is not None and cv < UNIFORM_RHYTHM_CV:
        reasons.append("uniform_rhythm")

    if typed >= MIN_TYPED_FOR_SPEED and m["active_ms"] > 0:
        cpm = typed / (m["active_ms"] / 60000)
        m["cpm"] = round(cpm)
        if cpm > MAX_HUMAN_CPM:
            reasons.append("too_fast")

    return m, reasons


def check(code, raw):
    """
    Rozhodnutie pre odoslanie:
      ("ok", record)                     -> nič podozrivé, pokračuj
      ("confirm", reasons)               -> treba potvrdenie študenta, NEspúšťať
      ("flagged", record)                -> podozrivé, študent potvrdil -> uložiť s red flagom
    record = slovník na uloženie (metriky, dôvody, potvrdenie).
    """
    metrics, reasons = evaluate(code, raw)
    confirmation = (metrics or {}).get("confirmation")
    if reasons and confirmation is None:
        return "confirm", reasons
    record = {
        "metrics": metrics,
        "reasons": reasons,
        "confirmation": confirmation if reasons else None,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    return ("flagged" if reasons else "ok"), record


def confirm_response(reasons, extra=None):
    """Telo odpovede, keď je potrebné potvrdenie (pokus sa nezapočíta)."""
    return {
        "correct": False, "counted": False, "needs_confirmation": True,
        "reason": "integrity", "integrity_reasons": reasons, **(extra or {}),
    }


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False) if obj is not None else None


def loads(text):
    try:
        return json.loads(text) if text else None
    except ValueError:
        return None


def admin_view(integrity_json, flag, dismissed):
    """Čo vidí admin pri pokuse/odpovedi."""
    data = loads(integrity_json) or {}
    # odpoveď testu: zoznam podozrivých odoslaní (aj z predošlých opráv) + metriky posledného
    flagged = data.get("flagged") if isinstance(data.get("flagged"), list) else (
        [data] if data.get("reasons") else [])
    reasons, confirmations = [], []
    for f in flagged:
        for r in f.get("reasons") or []:
            if r not in reasons:
                reasons.append(r)
        if f.get("confirmation"):
            confirmations.append(f["confirmation"])
    return {
        "flag": bool(flag),
        "dismissed": bool(dismissed),
        "active": bool(flag) and not bool(dismissed),
        "reasons": [r for r in REASONS if r in reasons],
        "confirmation": ("outside_source" if "outside_source" in confirmations
                         else ("own_work" if confirmations else None)),
        # metriky podozrivého odoslania (vysvetľujú flag), inak posledného
        "metrics": (flagged[-1].get("metrics") if flagged else None) or data.get("metrics"),
        "code": flagged[-1].get("code") if flagged else None,   # cvičenia: podozrivý kód bunky
        "dismissed_by": data.get("dismissed_by"),
        "dismissed_at": data.get("dismissed_at"),
    }


# ------------------------------------------------------------
# Cvičenia: flagy sa držia po bunkách v ExerciseProgress.integrity_json
# ------------------------------------------------------------
def exercise_add_flag(integrity_json, code_index, record):
    """Pridá podozrivé spustenie bunky; nový flag bunky je znova aktívny (zrušenie sa zmaže)."""
    data = loads(integrity_json) or {}
    cells = data.setdefault("cells", {})
    cell = cells.setdefault(str(code_index), {"flagged": []})
    cell.setdefault("flagged", []).append(record)
    cell["dismissed"] = False
    cell.pop("dismissed_by", None)
    cell.pop("dismissed_at", None)
    return dumps(data)


def exercise_cells(integrity_json):
    """{"<code_index>": admin_view} pre bunky, ktoré majú red flag."""
    cells = (loads(integrity_json) or {}).get("cells") or {}
    out = {}
    for ci, cell in cells.items():
        if cell.get("flagged"):
            out[ci] = admin_view(dumps(cell), True, cell.get("dismissed"))
    return out


def exercise_active_count(integrity_json):
    return sum(1 for v in exercise_cells(integrity_json).values() if v["active"])


def exercise_set_dismissed(integrity_json, code_index, dismissed, admin_id):
    """-> nový JSON, alebo None, ak bunka red flag nemá."""
    data = loads(integrity_json) or {}
    cell = (data.get("cells") or {}).get(str(code_index))
    if not cell or not cell.get("flagged"):
        return None
    cell["dismissed"] = bool(dismissed)
    if dismissed:
        cell["dismissed_by"] = admin_id
        cell["dismissed_at"] = datetime.now(timezone.utc).isoformat()
    else:
        cell.pop("dismissed_by", None)
        cell.pop("dismissed_at", None)
    return dumps(data)


def set_dismissed(integrity_json, dismissed, admin_id):
    """Vráti nový JSON so zápisom, kto a kedy red flag zrušil/obnovil."""
    data = loads(integrity_json) or {}
    if dismissed:
        data["dismissed_by"] = admin_id
        data["dismissed_at"] = datetime.now(timezone.utc).isoformat()
    else:
        data.pop("dismissed_by", None)
        data.pop("dismissed_at", None)
    return dumps(data)
