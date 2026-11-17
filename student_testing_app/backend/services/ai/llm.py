# ============================================================
# AdaptPy - klient pre Ollama (lokálny jazykový a embedding model).
#
#   chat_stream()  odpoveď po kúskoch (pre SSE), uvažovanie (think) sa NEposiela študentovi
#   chat()         celá odpoveď naraz (preklad otázky, krátke úlohy)
#   embed()        vektory pre RAG (bge-m3)
#
# Model, think a teplota prichádzajú z services/ai/config.py. Všetky chyby siete
# alebo modelu sa menia na LlmUnavailable, aby volajúci vedel použiť zálohu.
# ============================================================
import json
import os
import threading
import time

import requests


class LlmUnavailable(Exception):
    """Ollama neodpovedá, model neexistuje alebo vrátil chybu."""


# Lokálny model zvládne naraz len pár odpovedí; ďalšie by čakali v Ollame a prekročili
# timeout. Semafor je na proces (gunicorn worker), limit nastavuje AI_MAX_CONCURRENT.
_slots = None
_slots_lock = threading.Lock()


def _semaphore(limit):
    global _slots
    with _slots_lock:
        if _slots is None or _slots[0] != limit:
            _slots = (limit, threading.BoundedSemaphore(max(1, limit)))
        return _slots[1]


class Busy(Exception):
    """Všetky miesta pre generovanie sú obsadené."""


class slot:
    """with slot(cfg): ... - zaberie miesto na generovanie alebo vyhodí Busy."""

    def __init__(self, cfg, wait_s=20):
        self.sem = _semaphore(cfg.max_concurrent)
        self.wait_s = wait_s

    def __enter__(self):
        if not self.sem.acquire(timeout=self.wait_s):
            raise Busy()
        return self

    def __exit__(self, *exc):
        self.sem.release()
        return False


def _options(cfg, max_tokens=None, temperature=None):
    think_on = cfg.think not in (None, False)
    return {
        "temperature": cfg.temperature if temperature is None else temperature,
        "top_p": 0.95,
        "num_ctx": cfg.num_ctx,
        "num_predict": max_tokens or (cfg.max_tokens_think if think_on else cfg.max_tokens),
    }


def _payload(cfg, messages, stream, max_tokens=None, temperature=None, think="cfg"):
    payload = {
        "model": cfg.chat_model,
        "messages": messages,
        "stream": stream,
        "options": _options(cfg, max_tokens, temperature),
        "keep_alive": os.getenv("AI_CHAT_KEEP_ALIVE", "30m"),
    }
    think = cfg.think if think == "cfg" else think
    if think is not None:
        payload["think"] = think
    return payload


def chat_stream(cfg, messages, max_tokens=None, temperature=None):
    """
    Generátor udalostí:
      {"type": "thinking", "text": ...}   (len informácia, že model premýšľa)
      {"type": "content", "text": ...}
      {"type": "done", "stats": {...}}
    """
    t0 = time.time()
    first = None
    try:
        with requests.post(f"{cfg.ollama_url}/api/chat",
                           json=_payload(cfg, messages, True, max_tokens, temperature),
                           stream=True, timeout=(10, cfg.request_timeout)) as r:
            if r.status_code != 200:
                raise LlmUnavailable(_error_text(r))
            for line in r.iter_lines(chunk_size=None):
                if not line:
                    continue
                chunk = json.loads(line)
                if "error" in chunk:
                    raise LlmUnavailable(chunk["error"])
                msg = chunk.get("message") or {}
                if msg.get("thinking"):
                    yield {"type": "thinking", "text": msg["thinking"]}
                if msg.get("content"):
                    if first is None:
                        first = time.time() - t0
                    yield {"type": "content", "text": msg["content"]}
                if chunk.get("done"):
                    yield {"type": "done", "stats": _stats(chunk, t0, first)}
                    return
    except requests.RequestException as e:
        raise LlmUnavailable(f"Ollama nie je dostupná: {e}") from e
    except ValueError as e:
        raise LlmUnavailable(f"Neplatná odpoveď Ollamy: {e}") from e
    raise LlmUnavailable("Odpoveď modelu sa nečakane skončila.")


def chat(cfg, messages, max_tokens=400, temperature=0.0, think=False, fmt=None):
    """Celá odpoveď naraz -> (text, stats). Predvolene bez uvažovania (krátke pomocné volania)."""
    t0 = time.time()
    payload = _payload(cfg, messages, False, max_tokens, temperature, think=think)
    if fmt is not None:
        payload["format"] = fmt
    try:
        r = requests.post(f"{cfg.ollama_url}/api/chat", json=payload, timeout=(10, cfg.request_timeout))
    except requests.RequestException as e:
        raise LlmUnavailable(f"Ollama nie je dostupná: {e}") from e
    if r.status_code != 200:
        raise LlmUnavailable(_error_text(r))
    data = r.json()
    return (data.get("message") or {}).get("content", "").strip(), _stats(data, t0, None)


def embed(cfg, texts, timeout=600, keep_alive=None):
    """keep_alive: pri otázkach predvolene AI_EMBED_KEEP_ALIVE (0 = hneď uvoľniť VRAM pre jazykový
    model, rovnako ako ask.py v rag_asistent); pri indexovaní dlhšie, aby sa nenačítaval pri každej dávke."""
    try:
        r = requests.post(f"{cfg.ollama_url}/api/embed",
                          json={"model": cfg.embed_model, "input": list(texts),
                                "keep_alive": cfg.embed_keep_alive if keep_alive is None else keep_alive},
                          timeout=(10, timeout))
    except requests.RequestException as e:
        raise LlmUnavailable(f"Ollama nie je dostupná: {e}") from e
    if r.status_code != 200:
        raise LlmUnavailable(_error_text(r))
    return r.json()["embeddings"]


def health(cfg):
    """Stav pre admina: beží Ollama? sú stiahnuté oba modely?"""
    out = {"ok": False, "chat_model": cfg.chat_model, "embed_model": cfg.embed_model,
           "chat_model_present": False, "embed_model_present": False, "models": [], "error": None}
    try:
        r = requests.get(f"{cfg.ollama_url}/api/tags", timeout=5)
        r.raise_for_status()
        names = [m.get("name", "") for m in r.json().get("models", [])]
    except (requests.RequestException, ValueError) as e:
        out["error"] = f"Ollama nie je dostupná na {cfg.ollama_url}: {e}"
        return out

    def present(model):
        return any(n == model or n == f"{model}:latest" or n.split(":")[0] == model for n in names)

    out.update(ok=True, models=names, chat_model_present=present(cfg.chat_model),
               embed_model_present=present(cfg.embed_model))
    return out


def _error_text(r):
    try:
        return f"Ollama {r.status_code}: {r.json().get('error', r.text[:300])}"
    except ValueError:
        return f"Ollama {r.status_code}: {r.text[:300]}"


def _stats(chunk, t0, first):
    gen_s = (chunk.get("eval_duration") or 0) / 1e9
    return {
        "latency_ms": int((time.time() - t0) * 1000),
        "first_token_ms": int(first * 1000) if first is not None else None,
        "load_ms": int((chunk.get("load_duration") or 0) / 1e6),
        "tokens_in": chunk.get("prompt_eval_count"),
        "tokens_out": chunk.get("eval_count"),
        "tok_s": round(chunk.get("eval_count", 0) / gen_s, 1) if gen_s else None,
        "done_reason": chunk.get("done_reason"),
    }
