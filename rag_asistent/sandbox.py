"""Spustenie kodu z datasetu alebo od modelu v samostatnom procese s casovym limitom."""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# kod od modelu moze robit hocico, toto sa radsej nespusta
DANGER = re.compile(r"\b(import\s+(os|subprocess|shutil|socket|requests|urllib|ctypes)|from\s+(os|subprocess|shutil|socket|urllib)\s+import"
                    r"|__import__|os\.(system|remove|rmdir|unlink)|shutil\.|eval\(|exec\()")


def clean_code(code):
    code = str(code or "").replace("\r\n", "\n").strip()
    m = re.search(r"```(?:python)?\n(.*?)```", code, re.S)  # model obcas obali kod do ```
    return m.group(1).strip() if m else code


def error_type(stderr):
    last = (stderr.strip().splitlines() or [""])[-1]
    m = re.match(r"(\w+(Error|Exception|Interrupt))\b", last)
    return m.group(1) if m else ""


def run(code, timeout=5, force=False):
    code = clean_code(code)
    if not code:
        return {"spustene": False, "dovod": "prazdny kod"}
    if DANGER.search(code) and not force:
        return {"spustene": False, "dovod": "nebezpecny kod (os/subprocess/eval...)"}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "riesenie.py"
        path.write_text(code, encoding="utf-8")
        try:
            p = subprocess.run([sys.executable, "-I", str(path)], cwd=tmp, capture_output=True, text=True,
                               timeout=timeout, stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            return {"spustene": True, "ok": False, "stdout": "", "chyba": f"prekroceny cas {timeout} s", "typ_chyby": "Timeout"}
    last = (p.stderr.strip().splitlines() or [""])[-1]
    return {"spustene": True, "ok": p.returncode == 0, "stdout": p.stdout[:2000],
            "chyba": last[:300] if p.returncode else "", "typ_chyby": error_type(p.stderr) if p.returncode else ""}

