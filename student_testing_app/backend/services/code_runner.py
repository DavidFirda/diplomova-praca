# ============================================================
# AdaptPy - klient pre sandbox "runner".
#
# Kód študenta sa NEspúšťa v procese backendu. Posiela sa HTTP-čkom
# do izolovaného kontajnera 'runner'. Backend teda nemôže spadnúť.
# ============================================================
import json
import os
import urllib.error
import urllib.request

RUNNER_URL = os.environ.get("RUNNER_URL", "http://runner:6000")
# musí byť väčší než najväčší možný beh (per-cvičenie timeout), aby backend
# "neodpadol" skôr, než runner stihne bunku zastaviť a odpovedať
HTTP_TIMEOUT = float(os.environ.get("RUN_HTTP_TIMEOUT", "75"))


def execute(prelude, code, workdir_rel=None, timeout=None):
    """
    Spustí kód v sandboxe. Vráti dict:
      { ok, output, error, images, timed_out?, timeout? }
    timeout = želaný limit v sekundách (None/0 -> default runnera).
    """
    body = json.dumps({
        "prelude": prelude or "",
        "code": code or "",
        "workdir": workdir_rel,
        "timeout": timeout,
    }).encode("utf-8")

    req = urllib.request.Request(
        RUNNER_URL + "/run",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            data.setdefault("images", [])
            return data
    except urllib.error.URLError:
        return {"ok": False, "output": "", "images": [],
                "error": "Spúšťač kódu je momentálne nedostupný. Skús to o chvíľu."}
    except Exception:
        return {"ok": False, "output": "", "images": [],
                "error": "Kód sa nepodarilo spustiť."}
