# ============================================================
# AdaptPy - STRÁŽCA výstupu asistenta (deterministický, nezávisí od modelu).
#
# Prompt modelu hovorí "nikdy nedaj celé riešenie", ale model sa dá ukecať.
# Strážca preto kontroluje odpoveď počas streamovania, skôr než ju študent uvidí:
#
#   Úlohy (task)
#     1. podobnosť bloku kódu s referenčným riešením (riadky + sekvencia znakov),
#     2. overenie spustením: blok bez vynechaných miest sa spustí v sandboxe;
#        ak vypíše očakávaný výstup úlohy, je to riešenie -> zablokuje sa,
#     3. riadky kódu mimo blokov, ktoré sú doslova z riešenia.
#     Zablokovaný blok sa nahradí kostrou (kľúčové slová a odsadenie, bez obsahu).
#   Cvičenia (exercise) - vzorové riešenia nie sú, preto:
#     blok, ktorý úplne implementuje funkciu zo zadania cvičenia (bez vynechaných
#     miest), sa zmení na kostru.
#   Dashboard
#     žiadny kód, žiadne odkazy mimo povolených stránok, žiadne vety o admin
#     rozhraní, API, kóde aplikácie či heslách/tokenoch.
#   Všetky režimy
#     odkazy len na povolené stránky aplikácie (vymyslený odkaz -> obyčajný text).
#
# Každý zásah sa zaznamená (rule, action) a admin ho vidí pri správe.
# ============================================================
import ast
import difflib
import re

from services.capture_output import RunnerUnavailable, capture_output, compare_outputs, expected_output

FENCE = re.compile(r"^\s*(```|~~~)")
PLACEHOLDER = re.compile(r"(\.\.\.|…|\bpass\b|#\s*(TODO|doplň|dopln|sem|your code|tvoj kód)|_{3,}|\?\?\?)",
                         re.I)
CODE_LINE_START = re.compile(
    r"^(\s{4,}\S|\s*(def|class|for|while|if|elif|else|try|except|finally|with|return|print|import|from|yield)\b"
    r"|\s*[A-Za-z_][\w\.\[\]]*\s*(=|\+=|-=|\*=|/=)\s*\S)")
LINK = re.compile(r"\[([^\]\n]{1,200})\]\(([^)\s]{1,300})\)")
BARE_URL = re.compile(r"(?<![\(\w])(https?://[^\s)]+)")
SKELETON_KEYWORD = re.compile(r"^(def|class|for|while|if|elif|else|try|except|finally|with|return)\b")

# Dashboard: čo sa študentovi nikdy nemá ukázať (interné veci aplikácie)
DASHBOARD_FORBIDDEN = re.compile(
    r"(/admin|admin[-_ ]?(rozhran|panel|stránk|strank|interface|page|token|účet|ucet)|/api/|api endpoint|"
    r"ADMIN_TOKEN|APP_ACCESS_CODE|SECRET|password_hash|heslo (iného|ineho|admina|používateľ)|"
    r"\b(flask|gunicorn|postgres|sqlalchemy|redis|ollama|docker)\b|\b\w+\.(py|env|sql|json)\b|"
    r"zdrojov\w* kód\w* (aplikácie|stránky)|source code of the (app|site))",
    re.I)

NOTE = {
    "sk": {
        "skeleton": "_(Strážca: celé riešenie neukážem, toto je len kostra – doplň vynechané miesta.)_",
        "removed": "_(Strážca: tento kód by prezradil riešenie, preto ho neukážem.)_",
        "no_code_dashboard": "_(Kód tu neukazujem – na programovanie použi Cvičenia alebo Úlohy.)_",
        "line_removed": "…",
        "forbidden": "_(Túto informáciu nemôžem poskytnúť.)_",
    },
    "en": {
        "skeleton": "_(Guard: I won't show the full solution, this is only a skeleton – fill in the gaps.)_",
        "removed": "_(Guard: this code would reveal the solution, so I won't show it.)_",
        "no_code_dashboard": "_(I don't show code here – use Exercises or Tasks for programming.)_",
        "line_removed": "…",
        "forbidden": "_(I can't share that information.)_",
    },
}

PROSE_MIN_CHARS = 25         # úlohy: neukončený riadok sa pošle až keď je zjavne veta (nie kód)
LINE_LEAK_SHARE = 0.5        # podiel netriviálnych riadkov riešenia v bloku
SEQ_RATIO = 0.8              # podobnosť znakov (bez medzier) bloku a riešenia
TEXT_LEAK_SHARE = 0.6        # podiel riadkov riešenia v celej odpovedi (záverečná kontrola)
MIN_REF_LINE = 6             # kratšie riadky sa neberú (print(x), return x ...)


# ------------------------------------------------------------
# Pomocné funkcie nad kódom
# ------------------------------------------------------------
def norm_line(line):
    return re.sub(r"\s+", "", line or "")


def ref_lines(reference):
    return {norm_line(l) for l in (reference or "").splitlines()
            if len(norm_line(l)) >= MIN_REF_LINE and not norm_line(l).startswith("#")}


def line_share(code, reference):
    ref = ref_lines(reference)
    if len(ref) < 2:
        return 0.0
    have = {norm_line(l) for l in (code or "").splitlines()}
    return len(ref & have) / len(ref)


def seq_ratio(code, reference):
    a = norm_line("\n".join(l for l in (code or "").splitlines() if not l.strip().startswith("#")))
    b = norm_line("\n".join(l for l in (reference or "").splitlines() if not l.strip().startswith("#")))
    if not a or not b or len(a) < 0.5 * len(b):
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def has_placeholders(code):
    return bool(PLACEHOLDER.search(code or ""))


def parses(code):
    try:
        ast.parse(code or "")
        return True
    except (SyntaxError, ValueError):
        return False


def statements(code):
    """Počet príkazov (bez docstringov a pass), alebo 0 ak kód nejde parsovať."""
    try:
        tree = ast.parse(code or "")
    except (SyntaxError, ValueError):
        return 0
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and not isinstance(node, ast.Pass):
            if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant) \
                    and isinstance(node.value.value, str):
                continue
            n += 1
    return n


def defined_functions(code):
    """{názov: počet príkazov v tele} pre funkcie definované v kóde."""
    try:
        tree = ast.parse(code or "")
    except (SyntaxError, ValueError):
        return {}
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = [b for b in node.body
                    if not isinstance(b, ast.Pass)
                    and not (isinstance(b, ast.Expr) and isinstance(getattr(b, "value", None), ast.Constant))]
            out[node.name] = sum(1 for b in body for x in ast.walk(b) if isinstance(x, ast.stmt))
    return out


def skeletonize(code, max_lines=25):
    """Kostra: hlavičky def/class ostanú, riadiace kľúčové slová a odsadenie ostanú, obsah sa skryje."""
    lines = []
    for raw in (code or "").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = raw[: len(raw) - len(raw.lstrip())]
        if stripped.startswith(("def ", "class ", "import ", "from ")):
            lines.append(indent + stripped)
            continue
        m = SKELETON_KEYWORD.match(stripped)
        if m:
            word = m.group(1)
            if word in ("else", "try", "finally"):
                lines.append(indent + word + ":")
            elif word == "return":
                lines.append(indent + "return ...")
            else:
                lines.append(indent + word + " ...:")
        elif stripped.startswith("print("):
            lines.append(indent + "print(...)")
        else:
            lines.append(indent + "...")
    # rovnaké po sebe idúce "..." zlúčiť
    out = []
    for line in lines:
        if out and line.strip() == "..." and out[-1].strip() == "..." and \
                len(line) - len(line.lstrip()) == len(out[-1]) - len(out[-1].lstrip()):
            continue
        out.append(line)
    if len(out) > max_lines:
        out = out[:max_lines] + ["..."]
    return "\n".join(out)


# ------------------------------------------------------------
# Pravidlá podľa režimu
# ------------------------------------------------------------
class Policy:
    """Kontrola jedného bloku kódu a jedného riadku textu pre daný režim."""

    def __init__(self, mode, lang="sk", reference=None, question_id=None, starter=None,
                 target_functions=(), allowed_links=(), run_check=True):
        self.mode = mode
        self.lang = lang if lang in NOTE else "sk"
        self.reference = reference or ""
        self.question_id = question_id
        self.starter = starter or ""
        self.target_functions = set(target_functions or ())
        self.allowed_links = list(allowed_links or ())
        self.run_check = run_check
        self.hits = []
        self._expected = None
        self._ref_lines = ref_lines(self.reference)

    def note(self, key):
        return NOTE[self.lang][key]

    def hit(self, rule, action, detail=None):
        self.hits.append({"rule": rule, "action": action, **({"detail": detail} if detail else {})})

    # --- odkazy ---
    def link_allowed(self, url):
        url = url.strip()
        for allowed in self.allowed_links:
            if allowed.endswith("*"):
                if url.startswith(allowed[:-1]):
                    return True
            elif url == allowed or url.split("#")[0] == allowed:
                return True
        return False

    def filter_links(self, line):
        def repl_link(m):
            text, url = m.group(1), m.group(2)
            if self.link_allowed(url):
                return m.group(0)
            self.hit("link_not_allowed", "unlinked", url[:120])
            return text

        line = LINK.sub(repl_link, line)

        def repl_bare(m):
            self.hit("link_not_allowed", "removed", m.group(1)[:120])
            return ""
        return BARE_URL.sub(repl_bare, line)

    # --- riadok textu (mimo blokov kódu) ---
    def check_line(self, line):
        line = self.filter_links(line)
        if self.mode == "dashboard" and DASHBOARD_FORBIDDEN.search(line):
            self.hit("dashboard_forbidden", "line_removed", DASHBOARD_FORBIDDEN.search(line).group(0)[:60])
            return self.note("forbidden")
        if self.mode == "task" and self._ref_lines:
            n = norm_line(line.strip().strip("`"))
            if len(n) >= MIN_REF_LINE and n in self._ref_lines and n not in ref_lines(self.starter):
                self.hit("solution_line_in_text", "line_removed")
                return self.note("line_removed")
        return line

    # --- blok kódu ---
    def check_block(self, code):
        """-> (nový_obsah_bloku | None ak sa má blok vynechať, poznámka | None)."""
        if self.mode == "dashboard":
            self.hit("code_in_dashboard", "removed")
            return None, self.note("no_code_dashboard")
        if self.mode == "task":
            return self._check_task_block(code)
        if self.mode == "exercise":
            return self._check_exercise_block(code)
        return code, None

    def _replace_with_skeleton(self, code, rule, detail=None):
        skeleton = skeletonize(code)
        if not skeleton.strip() or norm_line(skeleton) == norm_line(code) or \
                (self.mode == "task" and seq_ratio(skeleton, self.reference) >= SEQ_RATIO):
            self.hit(rule, "removed", detail)
            return None, self.note("removed")
        self.hit(rule, "skeleton", detail)
        return skeleton, self.note("skeleton")

    def _check_task_block(self, code):
        share = line_share(code, self.reference)
        if share >= LINE_LEAK_SHARE:
            return self._replace_with_skeleton(code, "similar_to_solution", f"riadky {share:.2f}")
        ratio = seq_ratio(code, self.reference)
        if ratio >= SEQ_RATIO:
            return self._replace_with_skeleton(code, "similar_to_solution", f"podobnosť {ratio:.2f}")
        if self.run_check and self._solves_task(code):
            return self._replace_with_skeleton(code, "solves_task", "výstup = očakávaný výstup")
        return code, None

    def _solves_task(self, code):
        """Overenie spustením: kód bez vynechaných miest vypíše očakávaný výstup úlohy?"""
        if has_placeholders(code) or statements(code) < 2 or not parses(code):
            return False
        try:
            if self._expected is None:
                out, err = expected_output(self.question_id, self.reference)
                self._expected = out if err is None else ""
            if not (self._expected or "").strip():
                return False                  # úloha bez výstupu sa spustením overiť nedá
            out, err = capture_output(code)
        except RunnerUnavailable:
            self.hit("run_check_unavailable", "skipped")
            return False
        except Exception:  # noqa: BLE001 - strážca nesmie zhodiť odpoveď
            return False
        return err is None and compare_outputs(out, self._expected)

    def _check_exercise_block(self, code):
        if has_placeholders(code) or not parses(code):
            return code, None
        funcs = defined_functions(code)
        full = [name for name, body in funcs.items() if name in self.target_functions and body >= 2]
        if full:
            return self._replace_with_skeleton(code, "full_exercise_solution", ", ".join(full))
        if statements(code) > 30:
            return self._replace_with_skeleton(code, "long_code", f"{statements(code)} príkazov")
        return code, None

    # --- záverečná kontrola celej odpovede ---
    def check_final(self, text):
        """Úlohy: riadok riešenia, ktorý by prekĺzol v texte, sa nahradí '…' (klient dostane `replace`)."""
        if self.mode != "task" or not self._ref_lines:
            return text
        starter = ref_lines(self.starter)
        share = line_share(text, self.reference)
        out, in_fence, changed = [], False, 0
        for line in text.splitlines():
            if FENCE.match(line):
                in_fence = not in_fence
                out.append(line)
                continue
            n = norm_line(line.strip().strip("`"))
            leak = n in self._ref_lines and n not in starter and (not in_fence or share >= TEXT_LEAK_SHARE)
            if leak:
                changed += 1
                out.append(self.note("line_removed"))
            else:
                out.append(line)
        if changed:
            self.hit("solution_in_answer" if share >= TEXT_LEAK_SHARE else "solution_line_in_text",
                     "lines_removed", f"{changed} riadkov")
            return "\n".join(out)
        return text


# ------------------------------------------------------------
# Strážca nad prúdom textu (SSE)
# ------------------------------------------------------------
class StreamGuard:
    """
    feed(delta) -> text, ktorý sa smie poslať študentovi hneď.
    Bloky kódu sa zadržia, kým sa neuzavrú, a skontrolujú sa celé. Riadky, ktoré
    môžu obsahovať odkaz alebo kód (alebo všetky riadky na dashboarde), sa pošlú
    až celé, po kontrole. Ostatný text ide k študentovi hneď (plynulé písanie).
    """

    def __init__(self, policy):
        self.policy = policy
        self.buf = ""            # nespracovaný text (posledný neukončený riadok)
        self.emitted_partial = 0  # koľko znakov z neukončeného riadku už odišlo
        self.in_fence = False
        self.fence_open = ""
        self.fence_lines = []
        self.out = []            # všetko, čo študent dostal (po kontrole)

    def _emit(self, text):
        if text:
            self.out.append(text)
        return text

    def _line_needs_hold(self, line):
        s = line.lstrip()
        if self.policy.mode == "dashboard":
            return True
        if not s or s.startswith(("`", "~")) or "[" in line or "http" in line:
            return True
        if self.policy.mode == "task":
            # v úlohách pustíme neukončený riadok len vtedy, keď je zjavne obyčajná veta:
            # dosť dlhý, nezačína ako kód a neobsahuje znaky typické pre kód
            return (len(s) < PROSE_MIN_CHARS or line[:1].isspace() or CODE_LINE_START.match(line) is not None
                    or any(ch in s for ch in "=()[]{}:"))
        return False

    def _complete_line(self, line):
        """Spracuje celý riadok (bez \\n) -> text na odoslanie."""
        if self.in_fence:
            if FENCE.match(line):
                self.in_fence = False
                code = "\n".join(self.fence_lines)
                self.fence_lines = []
                new_code, note = self.policy.check_block(code)
                parts = []
                if new_code is not None:
                    parts.append(f"{self.fence_open}\n{new_code}\n```\n")
                if note:
                    parts.append(note + "\n")
                return "".join(parts)
            self.fence_lines.append(line)
            return ""
        if FENCE.match(line):
            self.in_fence = True
            lang = line.strip()[3:].strip() or "python"
            self.fence_open = "```" + lang
            return ""
        return self.policy.check_line(line) + "\n"

    def feed(self, delta):
        self.buf += delta
        sent = []
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            already = self.emitted_partial
            self.emitted_partial = 0
            if already and not self.in_fence:
                # začiatok riadku už odišiel (bezpečný text) -> pošli zvyšok
                rest = line[already:]
                checked = self.policy.filter_links(rest)
                sent.append(self._emit(checked + "\n"))
            else:
                sent.append(self._emit(self._complete_line(line)))
        # neukončený riadok: bezpečný text pošli hneď
        if self.buf and not self.in_fence and not self._line_needs_hold(self.buf):
            new = self.buf[self.emitted_partial:]
            if new:
                sent.append(self._emit(new))
                self.emitted_partial = len(self.buf)
        return "".join(sent)

    def finish(self):
        """Dokončí zvyšok (aj neuzavretý blok kódu) -> text na odoslanie."""
        sent = []
        if self.buf:
            line, self.buf = self.buf, ""
            if self.emitted_partial and not self.in_fence:
                sent.append(self._emit(self.policy.filter_links(line[self.emitted_partial:])))
            else:
                sent.append(self._emit(self._complete_line(line).rstrip("\n")))
            self.emitted_partial = 0
        if self.in_fence:                       # model neuzavrel blok
            sent.append(self._emit(self._complete_line("```")))
        return "".join(sent)

    def text(self):
        return "".join(self.out).strip()


def guard_text(policy, text):
    """Celý text naraz (záloha bez streamovania, testy)."""
    g = StreamGuard(policy)
    g.feed(text)
    g.finish()
    return policy.check_final(g.text())
