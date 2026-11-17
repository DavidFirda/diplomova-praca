# ============================================================
# AdaptPy - nastavenia AI asistenta.
#
# Predvolené hodnoty sú v .env (pozri .env.example). Model, uvažovanie (think)
# a teplotu vie admin zmeniť za behu v admin rozhraní "AI asistent" -> uložia sa
# do app_settings a prebijú .env (bez reštartu, platí pre všetkých workerov).
# ============================================================
import os
from dataclasses import dataclass

from services.settings import get_setting, set_setting

KEY_MODEL = "ai_chat_model"
KEY_THINK = "ai_think"
KEY_TEMPERATURE = "ai_temperature"
KEY_ENABLED = "ai_enabled"


def _env_bool(name, default):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def parse_think(value):
    """'true'/'false' -> bool (qwen, gemma), 'low'/'medium'/'high' -> str (gpt-oss), '' -> None."""
    v = str(value if value is not None else "").strip().lower()
    if v in ("", "none", "default"):
        return None
    if v in ("true", "1", "yes", "on"):
        return True
    if v in ("false", "0", "no", "off"):
        return False
    return v if v in ("low", "medium", "high") else None


def think_label(think):
    return "" if think is None else str(think).lower()


@dataclass
class AiConfig:
    ollama_url: str
    chat_model: str
    think: object
    temperature: float
    embed_model: str
    embed_keep_alive: str
    num_ctx: int
    max_tokens: int
    max_tokens_think: int
    enabled: bool
    translate_query: bool
    rag_k: int
    request_timeout: int
    max_concurrent: int
    rate_limit: int
    rate_window: int
    materials_dir: str
    index_dir: str
    max_upload_mb: int


def load():
    """Aktuálna konfigurácia (.env + prepísané hodnoty z admin rozhrania)."""
    temperature = get_setting(KEY_TEMPERATURE, "") or os.getenv("AI_TEMPERATURE", "0.3")
    try:
        temperature = max(0.0, min(float(temperature), 1.5))
    except ValueError:
        temperature = 0.3
    enabled_setting = get_setting(KEY_ENABLED, "")
    return AiConfig(
        ollama_url=os.getenv("OLLAMA_URL", "http://host.docker.internal:11434").rstrip("/"),
        chat_model=get_setting(KEY_MODEL, "") or os.getenv("AI_CHAT_MODEL", "qwen3.8:27b"),
        think=parse_think(get_setting(KEY_THINK, "") or os.getenv("AI_THINK", "false")),
        temperature=temperature,
        embed_model=os.getenv("AI_EMBED_MODEL", "bge-m3"),
        # 0 = embedding model sa po vyhľadaní uvoľní z VRAM (qwen3.8:27b sa na 16 GB GPU inak nezmestí celý)
        embed_keep_alive=os.getenv("AI_EMBED_KEEP_ALIVE", "0"),
        num_ctx=int(os.getenv("AI_NUM_CTX", "16384")),
        max_tokens=int(os.getenv("AI_MAX_TOKENS", "1200")),
        max_tokens_think=int(os.getenv("AI_MAX_TOKENS_THINK", "6000")),
        enabled=(enabled_setting == "true") if enabled_setting else _env_bool("AI_ENABLED", True),
        translate_query=_env_bool("AI_TRANSLATE_QUERY", True),
        rag_k=int(os.getenv("AI_RAG_K", "5")),
        request_timeout=int(os.getenv("AI_REQUEST_TIMEOUT", "300")),
        max_concurrent=int(os.getenv("AI_MAX_CONCURRENT", "2")),
        rate_limit=int(os.getenv("AI_RATE_LIMIT", "30")),
        rate_window=int(os.getenv("AI_RATE_WINDOW", "600")),
        materials_dir=os.getenv("MATERIALS_DIR", os.path.join("data", "materials")),
        index_dir=os.getenv("RAG_INDEX_DIR", os.path.join("data", "rag_index")),
        max_upload_mb=int(os.getenv("MATERIALS_MAX_MB", "200")),
    )


def save_runtime(model=None, think=None, temperature=None, enabled=None):
    """Zmena z admin rozhrania (None = nemeniť, '' = vrátiť na hodnotu z .env)."""
    if model is not None:
        set_setting(KEY_MODEL, model.strip())
    if think is not None:
        set_setting(KEY_THINK, str(think).strip().lower())
    if temperature is not None:
        set_setting(KEY_TEMPERATURE, str(temperature).strip())
    if enabled is not None:
        set_setting(KEY_ENABLED, "true" if enabled else "false")


def public_view(cfg):
    return {
        "ollama_url": cfg.ollama_url, "chat_model": cfg.chat_model, "think": think_label(cfg.think),
        "temperature": cfg.temperature, "embed_model": cfg.embed_model, "num_ctx": cfg.num_ctx,
        "enabled": cfg.enabled, "translate_query": cfg.translate_query, "rag_k": cfg.rag_k,
        "max_concurrent": cfg.max_concurrent, "rate_limit": cfg.rate_limit, "rate_window": cfg.rate_window,
        "env_model": os.getenv("AI_CHAT_MODEL", "qwen3.8:27b"), "env_think": os.getenv("AI_THINK", "false"),
    }
