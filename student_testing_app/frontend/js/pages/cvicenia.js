/* ============================================================
   AdaptPy - zoznam cvičení.
   Konzistentné veľkosti: badge aj akčná oblasť majú vyhradené
   miesto v každom stave (odomknuté/zamknuté) aj jazyku.
   ============================================================ */
(function () {
  const listEl = document.getElementById("ex-list");
  if (!listEl) return;

  function tr(key, fallback) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fallback;
  }
  function lang() {
    try {
      if (typeof I18N !== "undefined" && I18N.lang) return I18N.lang;
      return localStorage.getItem("adeptpy_lang") || "sk";
    } catch (e) { return "sk"; }
  }
  function pick(ex, base) {
    return lang() === "en" ? (ex[base + "_en"] || ex[base + "_sk"]) : (ex[base + "_sk"] || ex[base + "_en"]);
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, m => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]
    ));
  }

  function badge(ex) {
    if (ex.status === "completed")
      return `<span class="ex-badge ex-badge--done">✓ ${tr("ex.done", "Dokončené")}</span>`;
    if (ex.locked)
      return `<span class="ex-badge ex-badge--locked">🔒 ${tr("ex.locked", "Zamknuté")}</span>`;
    if (ex.status === "in_progress")
      return `<span class="ex-badge ex-badge--progress">${tr("ex.inProgress", "Rozpracované")}</span>`;
    return "";
  }

  function lockNote(ex) {
    if (!ex.locked) return "";
    const msg = ex.lock_reason === "not_accessible"
      ? tr("ex.lockAccess", "Zatiaľ nesprístupnené vyučujúcim.")
      : tr("ex.lockPrev", "Najprv dokonči predchádzajúce cvičenie.");
    return `<div class="ex-progress__label ex-progress__label--note">${esc(msg)}</div>`;
  }

  function row(ex, idx) {
    const title = esc(pick(ex, "title") || ex.slug);
    const desc = esc(pick(ex, "description") || "");
    const topics = (ex.topics || []).slice(0, 5)
      .map(t => `<span class="ex-topic">${esc(t)}</span>`).join("");

    const actions = ex.locked ? "" : `
        <a class="btn" href="/cvicenie?id=${ex.id}">${
          ex.status === "not_started" ? tr("ex.start", "Otvoriť") : tr("ex.continue", "Pokračovať")
        }</a>
        <a class="btn btn--secondary" href="/api/exercises/${ex.id}/download">${tr("ex.download", "Stiahnuť")}</a>`;

    return `
      <div class="ex-row ${ex.locked ? "ex-row--locked" : ""} ${ex.status === "completed" ? "ex-row--done" : ""}">
        <div class="ex-row__num">${idx + 1}</div>
        <div class="ex-row__body">
          <div class="ex-row__title">${title}</div>
          ${desc ? `<div class="ex-row__desc">${desc}</div>` : ""}
          ${topics ? `<div class="ex-topics">${topics}</div>` : ""}
        </div>
        <div class="ex-row__side">
          <div class="ex-row__badge-slot">${badge(ex)}</div>
          <div class="ex-progress">
            <div class="ex-progress__top">
              <span class="ex-progress__pct">${ex.percent}%</span>
              <span class="ex-progress__label">${tr("ex.progressLabel", "vypracované")}</span>
            </div>
            <div class="ex-progress__track">
              <div class="ex-progress__fill" style="width:${ex.percent}%"></div>
            </div>
            ${lockNote(ex)}
          </div>
          <div class="ex-row__actions">${actions}</div>
        </div>
      </div>`;
  }

  let lastData = null;

  function render(list) {
    if (!list || !list.length) {
      listEl.innerHTML = `<div class="ex-empty">${tr("ex.none", "Zatiaľ tu nie sú žiadne cvičenia. Vyučujúci ich čoskoro sprístupní.")}</div>`;
      return;
    }
    listEl.innerHTML = list.map(row).join("");
    if (typeof I18N !== "undefined") I18N.apply();
  }

  async function load() {
    try {
      const r = await fetch("/api/exercises", { credentials: "include" });
      if (r.status === 401) { window.location.href = "/login"; return; }
      const data = await r.json();
      lastData = (data && data.exercises) || [];
      render(lastData);
    } catch (e) {
      listEl.innerHTML = `<div class="ex-empty">${tr("ex.loadError", "Cvičenia sa nepodarilo načítať.")}</div>`;
    }
  }

  function hookLangChange() {
    if (typeof I18N === "undefined" || typeof I18N.setLang !== "function") return;
    if (I18N.__exListHooked) return;
    const orig = I18N.setLang.bind(I18N);
    I18N.setLang = function (l) { orig(l); if (lastData) render(lastData); };
    I18N.__exListHooked = true;
  }

  hookLangChange();
  load();
})();
