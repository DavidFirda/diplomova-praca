"""Spolocne nastavenia."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
INDEX = HERE / "index"
OLLAMA = "http://127.0.0.1:11434"

# priecinok v data/ -> typ zdroja a vaha pri hladani
SOURCES = {
    "prednasky": {"typ": "prednaska", "vaha": 1.0},  # pptx + kody z prednasok
    "knihy": {"typ": "kniha", "vaha": 0.6},  # pdf knihy, su po anglicky
}

# domace ulohy nejdu do indexu, su len na vyhodnotenie
HOMEWORKS = DATA / "domace_ulohy"
HW_YEARS = (2024, 2025)  # len tieto roky su ohodnotene

EMBED_MODEL = "bge-m3"
CHUNK_CHARS = 1500
OVERLAP_CHARS = 200
