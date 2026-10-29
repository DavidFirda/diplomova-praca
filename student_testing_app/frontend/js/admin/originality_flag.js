/* ============================================================
   AdaptPy - admin: RED FLAG kontroly originality pri odpovedi.
   Použité pri pokusoch v Úlohách (admin_user_ulohy.js) aj pri odpovediach
   v testoch (admin_users.js). Údaje prichádzajú z backend/services/integrity.py
   (admin_view): dôvody, voľba študenta v potvrdzovacom okne, metriky písania.
   Admin môže red flag zrušiť (a znova obnoviť).
   ============================================================ */
(function () {
  function tr(key, fb) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, m => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]
    ));
  }
  const REASON_FB = {
    no_corrections: "kód bol napísaný súvisle, bez jedinej opravy či zmazania",
    unexplained_insert: "v kóde je viac textu, než bolo napísané na klávesnici (vloženie cez terminál)",
    uniform_rhythm: "písanie má strojovo pravidelný rytmus",
    too_fast: "kód bol napísaný nezvyčajne rýchlo",
    no_telemetry: "chýbajú údaje o písaní z editora",
  };

  function when(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleString();
  }

  /** HTML bloku red flagu (prázdny reťazec, ak odpoveď flag nemá). `id` = id pokusu/odpovede. */
  function html(integrity, id) {
    if (!integrity || !integrity.flag) return "";
    const g = integrity;
    const reasons = (g.reasons || []).map(r =>
      `<li>${esc(tr("orig.reason." + r, REASON_FB[r] || r))}</li>`).join("");
    let confirm = "";
    if (g.confirmation === "own_work") {
      confirm = `<div class="orig-flag__confirm">✓ ${esc(tr("orig.ownWorkShort", "Študent potvrdil: vlastná práca"))}</div>`;
    } else if (g.confirmation === "outside_source") {
      confirm = `<div class="orig-flag__confirm orig-flag__confirm--outside">⚠ ${esc(tr("orig.outsideShort", "Študent priznal: prepisované z iného zdroja"))}</div>`;
    }
    const m = g.metrics;
    const metrics = m ? `<div class="orig-flag__metrics">${esc(
      tr("orig.metrics", "Napísané: {typed} zn. · opravy: {corr} · zablokované vloženia: {paste}")
        .replace("{typed}", m.typed_chars ?? "–")
        .replace("{corr}", m.corrections ?? "–")
        .replace("{paste}", m.paste_blocked ?? "–")
    )}${m.cpm ? ` · ${esc(m.cpm)} zn./min` : ""}</div>` : "";
    const dismissedNote = g.dismissed
      ? `<div class="orig-flag__metrics">${esc(tr("orig.dismissed", "Red flag zrušený adminom"))}${g.dismissed_at ? " · " + esc(when(g.dismissed_at)) : ""}</div>` : "";
    const btn = g.dismissed
      ? `<button type="button" class="btn btn--secondary btn--sm" data-orig-flag="${id}" data-orig-dismiss="false">${esc(tr("orig.restore", "Obnoviť red flag"))}</button>`
      : `<button type="button" class="btn btn--secondary btn--sm" data-orig-flag="${id}" data-orig-dismiss="true">${esc(tr("orig.dismiss", "Zrušiť red flag"))}</button>`;
    return `
      <div class="orig-flag ${g.dismissed ? "orig-flag--dismissed" : ""}">
        <div class="orig-flag__head">
          <span class="orig-flag__title">⚑ ${esc(tr("orig.flagTitle", "Podozrivé písanie – možný plagiát"))}</span>
          ${btn}
        </div>
        ${reasons ? `<ul class="orig-flag__reasons">${reasons}</ul>` : ""}
        ${confirm}${metrics}${dismissedNote}
      </div>`;
  }

  
  function chip(count) {
    if (!count) return "";
    return `<span class="orig-chip" title="${esc(tr("orig.flagTitle", "Podozrivé písanie"))}">⚑ ${count} ${esc(tr("orig.activeFlags", "red flag"))}</span>`;
  }

  /** Napojí tlačidlá zrušiť/obnoviť. patch(id, dismissed) -> Promise<boolean> (úspech). */
  function bind(root, patch, after) {
    root.querySelectorAll("[data-orig-flag]").forEach(btn => {
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        const ok = await patch(btn.getAttribute("data-orig-flag"), btn.getAttribute("data-orig-dismiss") === "true");
        if (!ok) { btn.disabled = false; btn.textContent = "✕"; return; }
        if (after) after();
      });
    });
  }

  window.OrigFlag = { html, chip, bind };
})();
