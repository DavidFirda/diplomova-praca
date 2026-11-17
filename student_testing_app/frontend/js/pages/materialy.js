/* ============================================================
   AdaptPy - Materiály kurzu pre študentov (len tie, ktoré sprístupnil vyučujúci).
   Asistent na ne odkazuje cez /materialy#m-<id> (riadok sa zvýrazní).
   ============================================================ */
(function () {
  const root = document.getElementById("mat-content");
  const tr = (key, fb) => {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (m) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
  const size = (b) => b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} kB`;

  function row(m) {
    const head = m.kind === "prednaska"
      ? (m.lecture_no != null ? `${tr("mat.lecture", "Prednáška")} ${m.lecture_no}` : tr("mat.lecture", "Prednáška"))
      : tr("mat.book", "Kniha");
    return `
      <div class="mat-row" id="m-${m.id}">
        <div class="mat-row__ic">${esc((m.ext || "").toUpperCase().slice(0, 4))}</div>
        <div class="mat-row__body">
          <div class="mat-row__title">${esc(m.title)}</div>
          <div class="mat-row__sub">${esc(head)} · ${esc(m.original_name)} · ${size(m.size_bytes)}</div>
        </div>
        <a class="btn btn--secondary" href="/api/materials/${m.id}/download">${tr("mat.download", "Stiahnuť")}</a>
      </div>`;
  }

  async function load() {
    try {
      const r = await fetch("/api/materials", { credentials: "include" });
      if (r.status === 401) { location.href = "/login"; return; }
      const d = await r.json();
      const list = d.materials || [];
      if (!list.length) {
        root.innerHTML = `<div class="ex-empty">${tr("mat.none", "Vyučujúci zatiaľ nesprístupnil žiadne materiály.")}</div>`;
        return;
      }
      const lectures = list.filter((m) => m.kind === "prednaska");
      const books = list.filter((m) => m.kind !== "prednaska");
      root.innerHTML =
        (lectures.length ? `<h2 class="mat-group-title">${tr("mat.lectures", "Prednášky")}</h2><div class="mat-list">${lectures.map(row).join("")}</div>` : "") +
        (books.length ? `<h2 class="mat-group-title">${tr("mat.books", "Knihy")}</h2><div class="mat-list">${books.map(row).join("")}</div>` : "");
      if (location.hash) {
        const el = document.querySelector(location.hash);
        if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    } catch (e) {
      root.innerHTML = `<div class="ex-empty">${tr("mat.error", "Materiály sa nepodarilo načítať.")}</div>`;
    }
  }

  document.addEventListener("langchange", load);
  load();
})();
