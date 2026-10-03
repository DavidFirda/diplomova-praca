"""
Runner API - jediný endpoint POST /run.
Spustí executor.py ako samostatný proces s wall-clock timeoutom. Pri prekročení
času zabije celú procesovú skupinu (aj deti) -> nekonečná slučka sa zastaví
a backend nie je nijako dotknutý.

Timeout môže prísť v požiadavke (per-cvičenie); oreže sa na [1, RUN_MAX_TIMEOUT].
"""
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading

from flask import Flask, request, jsonify

app = Flask(__name__)

RUN_TIMEOUT = float(os.environ.get("RUN_TIMEOUT", "10"))          # default (s)
RUN_MAX_TIMEOUT = float(os.environ.get("RUN_MAX_TIMEOUT", "60"))  # horná poistka (s)
EXERCISES_DIR = os.path.abspath(os.environ.get("EXERCISES_DIR", "/exercises"))
MAX_CONCURRENCY = int(os.environ.get("MAX_CONCURRENCY", "2"))
_HERE = os.path.dirname(os.path.abspath(__file__))
_sem = threading.Semaphore(MAX_CONCURRENCY)


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/run")
def run():
    data = request.get_json(silent=True) or {}

    # pracovný priečinok cvičenia (napr. "sources/lab11") - len na čítanie
    workdir = None
    rel = data.get("workdir")
    if rel:
        cand = os.path.normpath(os.path.join(EXERCISES_DIR, rel))
        if (cand == EXERCISES_DIR or cand.startswith(EXERCISES_DIR + os.sep)) and os.path.isdir(cand):
            workdir = cand

    # timeout z požiadavky (per-cvičenie), orezaný na rozumné medze
    try:
        req_to = float(data.get("timeout") or 0)
    except (TypeError, ValueError):
        req_to = 0
    timeout = RUN_TIMEOUT if req_to <= 0 else min(max(req_to, 1.0), RUN_MAX_TIMEOUT)

    payload = {
        "prelude": data.get("prelude", ""),
        "code": data.get("code", ""),
        "workdir": workdir,
    }

    with _sem:
        return jsonify(_execute(payload, timeout))


def _execute(payload, timeout):
    d = tempfile.mkdtemp(prefix="run_")
    in_path = os.path.join(d, "in.json")
    out_path = os.path.join(d, "out.json")
    try:
        with open(in_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        env = dict(os.environ)
        env.setdefault("MPLBACKEND", "Agg")
        env.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
        env.setdefault("HOME", "/tmp")

        proc = subprocess.Popen(
            ["python", "-I", "executor.py", in_path, out_path],
            cwd=_HERE,
            env=env,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            return {
                "ok": False, "output": "", "images": [],
                "timed_out": True, "timeout": int(timeout),
                "error": f"⏱ Kód prekročil časový limit {int(timeout)} s a bol zastavený "
                         f"(napríklad nekonečná slučka).",
            }

        if os.path.exists(out_path):
            try:
                with open(out_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        return {
            "ok": False, "output": "", "images": [],
            "error": "Beh kódu bol ukončený (napr. priveľa pamäte alebo pád procesu).",
        }
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _kill_group(proc):
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    try:
        proc.wait(timeout=3)
    except Exception:
        pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6000)
