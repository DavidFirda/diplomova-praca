import json
import os
import tempfile


def save_json(path, data, **dump_kwargs):
    """
    Atomický zápis JSON (dočasný súbor + os.replace): čitateľ nikdy neuvidí
    nedopísaný súbor, ani keď proces zomrie počas zápisu.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, **dump_kwargs)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
