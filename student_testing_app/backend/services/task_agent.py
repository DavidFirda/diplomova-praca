# ============================================================
# AdaptPy - agent, ktorý pomáha študentovi v ÚLOHÁCH.
#
# Sprístupní sa po 2. nesprávnom pokuse. Nikdy neprezradí riešenie - len:
#   - vysvetlí, čo je zlé v poslednom pokuse (intent "explain"),
#   - dá nápovedu, ktorá sa so každou ďalšou stupňuje (intent "hint", max 3):
#       1. všeobecná nápoveda podľa kategórie a typu chyby,
#       2. akú konštrukciu jazyka riešenie používa a študentov kód nie,
#       3. kostra riešenia so skrytým obsahom riadkov.
#
# Beží na pravidlách (bez externého modelu). Keď bude napojený vlastný jazykový
# model, stačí nahradiť funkciu `reply()` - route aj logovanie ostanú rovnaké.
# ============================================================
import ast
import json
import re

from services.extract_starter_code import extract_starter_code
from services.task_feedback import error_explanation, feedback_message
from services.task_text import normalize_lang, tt

MAX_HINTS = 3

_CONSTRUCTS = (
    (ast.For, "for"), (ast.While, "while"), (ast.If, "if"), (ast.FunctionDef, "def"),
    (ast.Return, "return"), (ast.ListComp, "comp"), (ast.DictComp, "comp"),
    (ast.SetComp, "comp"), (ast.GeneratorExp, "comp"), (ast.Lambda, "lambda"),
    (ast.Try, "try"), (ast.ClassDef, "class"), (ast.Import, "import"), (ast.ImportFrom, "import"),
)
_KEYWORD_LINE = re.compile(r"^(def|class|for|while|if|elif|else|try|except|finally|with|return)\b")
_SKELETON_MAX_LINES = 25


def _constructs(code):
    """Množina použitých konštrukcií jazyka, alebo None ak kód nejde parsovať."""
    try:
        tree = ast.parse(code or "")
    except (SyntaxError, ValueError):
        return None
    found = set()
    for node in ast.walk(tree):
        for node_type, name in _CONSTRUCTS:
            if isinstance(node, node_type):
                found.add(name)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print":
            found.add("print")
    return found


def _skeleton(solution_code):
    """Kostra riešenia: kľúčové slová a odsadenie ostanú, obsah riadkov sa skryje."""
    lines = []
    for raw in (solution_code or "").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = raw[: len(raw) - len(raw.lstrip())]
        match = _KEYWORD_LINE.match(stripped)
        if stripped.startswith(("import ", "from ")):
            lines.append(indent + stripped)
        elif stripped.startswith("print("):
            lines.append(indent + "print(…)")
        elif match:
            word = match.group(1)
            if word in ("else", "try", "finally"):
                lines.append(indent + word + ":")
            else:
                lines.append(indent + word + " …" + (":" if stripped.endswith(":") else ""))
        else:
            lines.append(indent + "…")
    if len(lines) > _SKELETON_MAX_LINES:
        lines = lines[:_SKELETON_MAX_LINES] + ["…"]
    return "\n".join(lines)


def greeting(lang="sk"):
    return tt(normalize_lang(lang), "agent.greeting")


def _explain(last_attempt, lang):
    """Vysvetlenie poslednej spätnej väzby (nespotrebuje nápovedu)."""
    if last_attempt is None:
        return tt(lang, "agent.no_attempt")
    try:
        feedback = json.loads(last_attempt.feedback_json or "{}")
    except ValueError:
        feedback = {}
    kind = feedback.get("kind")
    if not kind:
        return tt(lang, "agent.no_attempt")
    return feedback_message(kind, feedback.get("params"), lang) + " " + tt(lang, "agent.explain_hint")


def _hint(level, question, student_code, last_attempt, lang):
    """Text nápovedy danej úrovne (1 až MAX_HINTS)."""
    solution = question.output or ""

    if level == 1:
        text = tt(lang, f"cat.{question.category}")
        if text == f"cat.{question.category}":
            text = tt(lang, "cat.generic")
        if last_attempt is not None:
            try:
                feedback = json.loads(last_attempt.feedback_json or "{}")
            except ValueError:
                feedback = {}
            if feedback.get("kind") == "error":
                text += " " + error_explanation(feedback.get("params", {}).get("error_type", ""), lang)
            elif feedback.get("kind") == "no_output":
                text += " " + tt(lang, "agent.hint1_extra_no_output")
        return text

    if level == 2:
        wanted, have = _constructs(solution), _constructs(student_code)
        if wanted is not None and have is not None:
            missing = [tt(lang, f"cons.{name}") for name in sorted(wanted - have)]
            if missing:
                return tt(lang, "agent.hint2_missing", missing=", ".join(missing))
        return tt(lang, "agent.hint2_nothing_missing")

    skeleton = _skeleton(solution)
    # kostra, ktorá je rovnaká ako začiatočný kód z editora, by nič nepovedala
    if not skeleton or skeleton.strip() == extract_starter_code(solution).strip():
        return tt(lang, "agent.hint3_unavailable")
    return tt(lang, "agent.hint3") + "\n" + skeleton


def reply(question, assignment, last_attempt, student_code, intent, lang="sk"):
    """
    Odpoveď agenta. Vráti {"text", "intent", "hint_level"} a pri nápovede zvýši
    assignment.hints_used (commit robí volajúci).
    intent: "explain" | "hint"
    """
    lang = normalize_lang(lang)
    if intent == "explain":
        return {"text": _explain(last_attempt, lang), "intent": "explain", "hint_level": None}

    if assignment.hints_used >= MAX_HINTS:
        return {"text": tt(lang, "agent.no_more_hints"), "intent": "hint", "hint_level": None}

    assignment.hints_used += 1
    level = assignment.hints_used
    text = tt(lang, "agent.hint_prefix", n=level, max=MAX_HINTS) + " " + \
        _hint(level, question, student_code, last_attempt, lang)
    return {"text": text, "intent": "hint", "hint_level": level}


def intent_from_message(message):
    """Voľný text študenta -> zámer (zatiaľ jednoduché pravidlá)."""
    text = (message or "").lower()
    if any(w in text for w in ("chyb", "error", "zle", "zlé", "wrong", "why", "prečo", "preco", "vysvetl", "explain")):
        return "explain"
    return "hint"
