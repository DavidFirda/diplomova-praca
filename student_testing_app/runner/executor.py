"""
Beží ako VEDĽAJŠÍ PROCES spustený z runner/app.py.
1) prelude (kód buniek nad aktuálnou) - potichu, kvôli premenným
2) aktuálnu bunku - so zachytením výstupu
Na konci zachytí matplotlib grafy ako PNG (base64).
"""
import base64
import contextlib
import io
import os
import resource
import sys
import traceback


def set_limits():
    cpu = int(os.environ.get("CPU_SECONDS", "8"))
    limits = [
        (resource.RLIMIT_CPU, (cpu, cpu + 1)),
        (resource.RLIMIT_NPROC, (96, 96)),
        (resource.RLIMIT_FSIZE, (12 * 1024 * 1024, 12 * 1024 * 1024)),
    ]
    for res_id, val in limits:
        try:
            resource.setrlimit(res_id, val)
        except Exception:
            pass
    as_mb = os.environ.get("AS_LIMIT_MB")
    if as_mb:
        try:
            b = int(as_mb) * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (b, b))
        except Exception:
            pass


def _read(path):
    import json
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(path, obj):
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)


def _mpl_loaded():
    return "matplotlib" in sys.modules


def close_all_figures():
    if not _mpl_loaded():
        return
    try:
        import matplotlib.pyplot as plt
        plt.close("all")
    except Exception:
        pass


def capture_images():
    if not _mpl_loaded():
        return []
    imgs = []
    try:
        import matplotlib.pyplot as plt
        for num in plt.get_fignums():
            try:
                fig = plt.figure(num)
                buf = io.BytesIO()
                fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
                buf.seek(0)
                imgs.append("data:image/png;base64," + base64.b64encode(buf.read()).decode("ascii"))
            except Exception:
                continue
        plt.close("all")
    except Exception:
        return imgs
    return imgs


def main():
    in_path, out_path = sys.argv[1], sys.argv[2]
    payload = _read(in_path)
    prelude = payload.get("prelude") or ""
    code = payload.get("code") or ""
    workdir = payload.get("workdir")

    if workdir and os.path.isdir(workdir):
        try:
            os.chdir(workdir)
        except Exception:
            pass

    set_limits()
    ns = {"__name__": "__main__"}

    if prelude.strip():
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                exec(compile(prelude, "<predchadzajuce_bunky>", "exec"), ns)
        except SystemExit:
            pass
        except BaseException:
            _write(out_path, {
                "ok": False, "output": "", "images": [],
                "error": "Chyba v niektorej z predchádzajúcich buniek:\n"
                         + traceback.format_exc(limit=2),
            })
            return
        close_all_figures()

    buf = io.StringIO()
    ok = True
    err = None
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            exec(compile(code, "<bunka>", "exec"), ns)
    except SystemExit:
        ok = True
    except BaseException:
        ok = False
        err = traceback.format_exc(limit=3)

    images = capture_images()
    _write(out_path, {"ok": ok, "output": buf.getvalue(), "error": err, "images": images})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            _write(sys.argv[2], {"ok": False, "output": "", "images": [],
                                 "error": "Interná chyba spúšťača."})
        except Exception:
            pass
