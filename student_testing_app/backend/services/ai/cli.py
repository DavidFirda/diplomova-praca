# ============================================================
# AdaptPy - príkazy pre AI asistenta (spúšťajú sa v kontajneri backendu):
#
#   flask --app app ai import /cesta/k/priecinku --kind prednaska [--visible]
#   flask --app app ai import /cesta/knihy --kind kniha
#   flask --app app ai reindex [--all]       # chýbajúce/chybné alebo všetky materiály
#   flask --app app ai search "čo je dedenie" [--k 5]
#
# Import skopíruje súbory do MATERIALS_DIR a zaindexuje ich (synchrónne, s výpisom).
# Rovnako ako nahratie v admin rozhraní - hodí sa na prvé naplnenie z rag_asistent/data.
# ============================================================
import os
import shutil
import uuid

import click
from flask.cli import AppGroup

from models import db
from models_ai import CourseMaterial
from services.ai import config as ai_config
from services.ai.rag import indexer, readers, store

ai_cli = AppGroup("ai", help="AI asistent: materiály a index RAG.")

SKIP_DIRS = {".ipynb_checkpoints", "__pycache__", ".git", ".venv", "__MACOSX"}


@ai_cli.command("import")
@click.argument("folder", type=click.Path(exists=True, file_okay=True))
@click.option("--kind", type=click.Choice(["prednaska", "kniha"]), default="prednaska")
@click.option("--visible", is_flag=True, help="Sprístupniť materiály aj študentom na stiahnutie.")
@click.option("--zip", "with_zip", is_flag=True,
              help="Pri priečinku nahrať aj .zip (predvolene sa preskočia - býva v nich to isté ako v rozbalených súboroch).")
def import_folder(folder, kind, visible, with_zip):
    """Nahrá všetky podporované súbory z priečinka (rekurzívne) a zaindexuje ich."""
    cfg = ai_config.load()
    os.makedirs(cfg.materials_dir, exist_ok=True)
    paths = [folder] if os.path.isfile(folder) else sorted(
        os.path.join(root, f) for root, dirs, files in os.walk(folder)
        if not (SKIP_DIRS & set(root.replace("\\", "/").split("/"))) for f in files)
    created = []
    for path in paths:
        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lower()
        if ext not in readers.UPLOAD_EXTS or (ext == ".zip" and os.path.isdir(folder) and not with_zip):
            continue
        with open(path, "rb") as fh:
            digest = readers.sha256_of(fh)
        if CourseMaterial.query.filter_by(sha256=digest).first():
            click.echo(f"[--] {name}: už existuje, preskakujem")
            continue
        stored = f"{uuid.uuid4().hex}{ext}"
        shutil.copyfile(path, os.path.join(cfg.materials_dir, stored))
        title = readers.first_slide_title(path, name) or os.path.splitext(name)[0]
        m = CourseMaterial(kind=kind, title=title[:255], original_name=name[:255], stored_name=stored,
                           size_bytes=os.path.getsize(path), sha256=digest,
                           lecture_no=readers.lecture_no(name) or readers.lecture_no(os.path.dirname(path))
                           if kind == "prednaska" else None,
                           visible_to_students=visible, status="pending")
        db.session.add(m)
        db.session.commit()
        created.append(m.id)
        click.echo(f"[+] {name} -> materiál #{m.id}")
    for mid in created:
        indexer.index_material(mid)
        m = db.session.get(CourseMaterial, mid)
        click.echo(f"[{'ok' if m.status == 'ready' else '!!'}] #{mid} {m.original_name}: "
                   f"{m.chunks} kúskov {m.error or ''}")
    click.echo(f"Hotovo: {len(created)} nových materiálov.")


@ai_cli.command("reindex")
@click.option("--all", "all_", is_flag=True, help="Prepočítať všetky materiály (napr. po zmene embedding modelu).")
def reindex(all_):
    cfg = ai_config.load()
    q = CourseMaterial.query.order_by(CourseMaterial.id)
    rows = q.all() if all_ else [m for m in q.all()
                                 if m.status != "ready" or m.embed_model != cfg.embed_model]
    for m in rows:
        indexer.index_material(m.id)
        m = db.session.get(CourseMaterial, m.id)
        click.echo(f"[{'ok' if m.status == 'ready' else '!!'}] #{m.id} {m.original_name}: "
                   f"{m.chunks} kúskov {m.error or ''}")
    store.bump_version(cfg.index_dir)
    click.echo(f"Hotovo: {len(rows)} materiálov.")


@ai_cli.command("search")
@click.argument("question")
@click.option("--k", default=5)
def search(question, k):
    cfg = ai_config.load()
    results, info = indexer.retrieve(cfg, question, k=k)
    click.echo(f"(kúskov v indexe: {info['chunks_total']}, vektory: {info['vectors']}, chyba: {info['error']})")
    for i, c in enumerate(results, start=1):
        signals = ", ".join(f"{a} #{b}" for a, b in c["poradie"].items())
        click.echo(f"\n[{i}] {store.source_label(c)}   (skóre {c['skore']}; {signals})\n    "
                   + " ".join(c["text"].split())[:220])


def register_ai_cli(app):
    app.cli.add_command(ai_cli)
