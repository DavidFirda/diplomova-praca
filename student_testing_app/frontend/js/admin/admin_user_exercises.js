/* ============================================================
   AdaptPy - admin: cvičenia konkrétneho používateľa.
   Pri každom cvičení % + stav; po rozbalení odpovede študenta
   (kód) po bunkách + či bunka bežala bez chyby.
   ============================================================ */
(function () {
  const root = document.getElementById("ux-content");
  if (!root) return;

  function tr(key, fb) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  }
  function lang() {
    try { if (typeof I18N !== "undefined" && I18N.lang) return I18N.lang; return localStorage.getItem("adeptpy_lang") || "sk"; } catch (e) { return "sk"; }
  }
  function pick(o, base) { return lang() === "en" ? (o[base + "_en"] || o[base + "_sk"]) : (o[base + "_sk"] || o[base + "_en"]); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, m => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]
    ));
  }

  const uid = new URLSearchParams(location.search).get("uid");
  let data = null;

  function statusBadge(status) {
    if (status === "completed") return `<span class="ex-badge ex-badge--done">✓ ${tr("ex.done", "Dokončené")}</span>`;
    if (status === "in_progress") return `<span class="ex-badge ex-badge--progress">${tr("ex.inProgress", "Rozpracované")}</span>`;
    return `<span class="ex-badge ex-badge--locked">${tr("adminUX.notStarted", "Nezačaté")}</span>`;
  }

  function cellBlock(c) {
    const stateCls = c.ran_ok ? "ux-cell--ok" : (c.answered ? "ux-cell--err" : "ux-cell--none");
    const stateLbl = c.ran_ok
      ? "✓ " + tr("adminUX.ranOk", "bez chyby")
      : (c.answered ? tr("adminUX.notOk", "nespustené / s chybou") : tr("adminUX.noAnswer", "bez odpovede"));
    const answer = c.answered ? esc(c.answer) : `<span class="ux-muted">${tr("adminUX.noAnswer", "bez odpovede")}</span>`;
    return `
      <div class="ux-cell ${stateCls}">
        <div class="ux-cell__head">
          <span class="ux-cell__idx">${tr("adminUX.cell", "Bunka")} ${c.code_index + 1}</span>
          <span class="ux-cell__state">${stateLbl}</span>
        </div>
        <details class="ux-cell__prompt">
          <summary>${tr("adminUX.prompt", "Predpis")}</summary>
          <pre class="ux-code ux-code--muted">${esc(c.prompt)}</pre>
        </details>
        <div class="ux-cell__answer-label">${tr("adminUX.studentCode", "Odpoveď študenta")}</div>
        <pre class="ux-code">${answer}</pre>
      </div>`;
  }

  function exerciseCard(ex, idx) {
    const title = esc(pick(ex, "title") || ("#" + ex.id));
    const answeredCount = (ex.cells || []).filter(c => c.answered).length;
    const cells = (ex.cells || []).map(cellBlock).join("") ||
      `<div class="ux-muted" style="padding:8px 0;">${tr("adminUX.noCells", "Cvičenie nemá code-bunky.")}</div>`;

    return `
      <div class="ux-ex">
        <div class="ux-ex__top">
          <div class="ux-ex__num">${idx + 1}</div>
          <div class="ux-ex__main">
            <div class="ux-ex__title">${title}</div>
            <div class="ex-progress">
              <div class="ex-progress__top">
                <span class="ex-progress__pct">${ex.percent}%</span>
                <span class="ex-progress__label">${tr("ex.progressLabel", "vypracované")} · ${answeredCount}/${ex.code_cells} ${tr("adminUX.answered", "odpovedí")}</span>
              </div>
              <div class="ex-progress__track"><div class="ex-progress__fill" style="width:${ex.percent}%"></div></div>
            </div>
          </div>
          <div class="ux-ex__badge">${statusBadge(ex.status)}</div>
        </div>
        <details class="ux-ex__answers">
          <summary>${tr("adminUX.showAnswers", "Zobraziť odpovede")}</summary>
          <div class="ux-cells">${cells}</div>
        </details>
      </div>`;
  }

  function render() {
    if (!data) return;
    const s = data.student || {};
    const name = `${s.name || ""} ${s.surname || ""}`.trim() || s.login || ("#" + s.id);
    const list = data.exercises || [];

    const head = `
      <div class="card ux-student">
        <div class="ux-student__avatar">${esc((name[0] || "?").toUpperCase())}</div>
        <div>
          <div class="ux-student__name">${esc(name)}</div>
          <div class="ux-student__sub">${esc(s.login || "")}${s.email ? " · " + esc(s.email) : ""}</div>
        </div>
      </div>`;

    const body = list.length
      ? `<div class="ux-list">${list.map(exerciseCard).join("")}</div>`
      : `<div class="ex-empty">${tr("adminUX.noExercises", "Zatiaľ nie sú žiadne publikované cvičenia.")}</div>`;

    root.innerHTML = head + body;
    if (typeof I18N !== "undefined") I18N.apply();
  }

  async function load() {
    if (!uid) { root.innerHTML = `<div class="ex-empty">${tr("adminUX.noUser", "Chýba používateľ.")}</div>`; return; }
    try {
      const r = await fetch(`/api/admin/exercises/user/${uid}`, { credentials: "include" });
      if (r.status === 401 || r.status === 403) { window.location.href = "/dashboard"; return; }
      if (!r.ok) { root.innerHTML = `<div class="ex-empty">${tr("adminUX.error", "Načítanie zlyhalo.")}</div>`; return; }
      data = await r.json();
      render();
    } catch (e) {
      root.innerHTML = `<div class="ex-empty">${tr("adminUX.error", "Načítanie zlyhalo.")}</div>`;
    }
  }

  function hookLangChange() {
    if (typeof I18N === "undefined" || typeof I18N.setLang !== "function") return;
    if (I18N.__uxHooked) return;
    const orig = I18N.setLang.bind(I18N);
    I18N.setLang = function (l) { orig(l); render(); };
    I18N.__uxHooked = true;
  }

  hookLangChange();
  load();
})();
