/* ============================================================
   AdaptPy - pracovná plocha jedného cvičenia.

   - Markdown bunky sa vykreslia (marked), code bunky sú editovateľné
     (CodeMirror) a dajú sa spustiť cez /api/exercises/<id>/run.
   - Bunka je "hotová", keď dobehne bez chyby -> rastie % vypracovania.
   - Pri 100 % sa aktivuje tlačidlo "Dokončil som".
   - Obrázky/odkazy v texte (src="sources/...") sa prepíšu na backend
     asset endpoint, aby sa načítali.
   - Vpravo je pripravený chat panel (napojí ho /js/pages/chat.js,
     lebo skeleton s panelom vkladáme SYNCHRÓNNE ešte pred jeho behom).
   ============================================================ */
(function () {
  const root = document.getElementById("ex-content");
  if (!root) return;

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
  function pick(o, base) { return lang() === "en" ? (o[base + "_en"] || o[base + "_sk"]) : (o[base + "_sk"] || o[base + "_en"]); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, m => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]
    ));
  }

  const exId = new URLSearchParams(location.search).get("id");

  // ---- 1) SYNCHRÓNNY skeleton (aby chat.js našiel panel) ----
  const RUN_ICON = '<svg viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" fill="none"><polygon points="6 4 20 12 6 20 6 4"/></svg>';
  root.innerHTML = `
    <div class="ex-workspace">
      <div class="ex-nb-col">
        <div id="ex-head"><div class="ex-empty" data-i18n="ex.loading">Načítavam cvičenie…</div></div>
        <div id="ex-cells"></div>
      </div>
      <aside class="side-panel">
        <div class="chat-panel">
          <div class="chat-panel__header">
            <span class="chat-panel__dot"></span>
            <span data-i18n="chat.title">AdaptPy asistent</span>
          </div>
          <div class="chat-panel__messages" id="chat-messages">
            <div class="chat-msg chat-msg--bot">
              <span data-i18n="ex.chatGreeting">Ahoj! Pomôžem ti s týmto cvičením. (asistent čoskoro pribudne)</span>
            </div>
          </div>
          <form class="chat-panel__input" id="chat-form">
            <input type="text" id="chat-input" autocomplete="off" data-i18n-placeholder="chat.placeholder" placeholder="Napíš správu…" />
            <button type="submit" class="chat-panel__send" aria-label="Odoslať">
              <svg viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8" fill="none"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/></svg>
            </button>
          </form>
        </div>
      </aside>
    </div>`;

  if (!exId) {
    root.innerHTML = lockedCard(tr("ex.badId", "Chýba identifikátor cvičenia."));
    return;
  }

  const headEl = document.getElementById("ex-head");
  const cellsEl = document.getElementById("ex-cells");

  let editors = [];
  let doneSet = new Set();
  let totalCode = 0;
  let percent = 0;
  let currentEx = null;

  // Po prepnutí jazyka: prekresli hlavičku (názov/popis/tlačidlo) a preloží
  // popisky buniek. Kód v editoroch ani výstupy sa NErušia.
  function retranslateCells() {
    editors.forEach(rec => {
      const btnSpan = rec.wrap.querySelector(".nb-code__run span");
      if (btnSpan) btnSpan.textContent = tr("ex.run", "Spustiť");
      const st = rec.statusEl;
      if (st.classList.contains("nb-code__status--ok")) st.textContent = "✓ " + tr("ex.cellDone", "hotová");
      else if (st.classList.contains("nb-code__status--err")) st.textContent = tr("ex.cellErr", "chyba");
      else st.textContent = tr("ex.cellIdle", "nespustená");
    });
  }

  function hookLangChange() {
    if (typeof I18N === "undefined" || typeof I18N.setLang !== "function") return;
    if (I18N.__exWorkHooked) return;
    const orig = I18N.setLang.bind(I18N);
    I18N.setLang = function (l) {
      orig(l);
      if (currentEx) { renderHead(currentEx); updateHeadBar(); }
      retranslateCells();
      if (typeof I18N !== "undefined") I18N.apply();
    };
    I18N.__exWorkHooked = true;
  }

  function lockedCard(msg) {
    return `
      <div class="card ex-locked-card">
        <div class="ex-locked-ic">
          <svg viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>
        </div>
        <h2>${esc(msg)}</h2>
        <p><a href="/cvicenia">${tr("ex.backToList", "← Späť na zoznam cvičení")}</a></p>
      </div>`;
  }

  // prepíše relatívne src/href (sources/...) na backend asset endpoint
  function rewriteAssets(container) {
    const isAbs = s => /^(https?:|data:|mailto:|#|\/)/i.test(s || "");
    container.querySelectorAll("img[src]").forEach(img => {
      const s = img.getAttribute("src");
      if (s && !isAbs(s)) img.setAttribute("src", `/api/exercises/${exId}/asset/${s}`);
    });
    container.querySelectorAll("a[href]").forEach(a => {
      const h = a.getAttribute("href");
      if (h && !isAbs(h)) {
        a.setAttribute("href", `/api/exercises/${exId}/asset/${h}`);
        a.setAttribute("target", "_blank");
        a.setAttribute("rel", "noopener");
      }
    });
  }

  function updateHeadBar() {
    const fill = headEl.querySelector(".ex-progress__fill");
    const pct = headEl.querySelector(".ex-progress__pct");
    const btn = headEl.querySelector(".ex-head__done-btn");
    if (fill) fill.style.width = percent + "%";
    if (pct) pct.textContent = percent + "%";
    if (btn) btn.disabled = !(totalCode === 0 || percent >= 100);
  }

  function renderHead(ex) {
    const title = esc(pick(ex, "title") || ex.slug);
    const desc = esc(pick(ex, "description") || "");
    const completed = ex.progress && ex.progress.status === "completed";
    headEl.innerHTML = `
      <div class="ex-head">
        <h2 class="ex-head__title">${title}</h2>
        ${desc ? `<p class="ex-head__desc">${desc}</p>` : ""}
        <div class="ex-head__bar-row">
          <div class="ex-progress">
            <div class="ex-progress__top">
              <span class="ex-progress__pct">${percent}%</span>
              <span class="ex-progress__label">${tr("ex.progressLabel", "vypracované")}</span>
            </div>
            <div class="ex-progress__track">
              <div class="ex-progress__fill" style="width:${percent}%"></div>
            </div>
          </div>
          <button class="btn ex-head__done-btn" id="ex-done-btn" ${(totalCode === 0 || percent >= 100) ? "" : "disabled"}>
            ${completed ? "✓ " + tr("ex.done", "Dokončené") : tr("ex.markDone", "Dokončil som")}
          </button>
        </div>
      </div>`;
    headEl.querySelector("#ex-done-btn").addEventListener("click", onComplete);
  }

  function renderCells(cells) {
    cellsEl.innerHTML = "";
    editors = [];
    cells.forEach(cell => {
      if (cell.type === "markdown") {
        const div = document.createElement("div");
        div.className = "nb-md";
        try {
          div.innerHTML = (window.marked ? marked.parse(cell.source || "") : esc(cell.source || ""));
        } catch (e) { div.textContent = cell.source || ""; }
        rewriteAssets(div);
        cellsEl.appendChild(div);
      } else if (cell.type === "code") {
        cellsEl.appendChild(buildCodeCell(cell));
      }
    });
    // CodeMirror si zmeria rozmery až keď je v DOM -> po vložení prekresli,
    // inak je kód viditeľný až po kliknutí do bunky.
    refreshEditors();
  }

  function refreshEditors() {
    const doRefresh = () => editors.forEach(e => { try { e.cm.refresh(); } catch (err) {} });
    requestAnimationFrame(doRefresh);
    // poistka, ak sa layout ustáli o chvíľu neskôr (fonty, obrázky)
    setTimeout(doRefresh, 120);
  }

  function buildCodeCell(cell) {
    const wrap = document.createElement("div");
    wrap.className = "nb-code" + (cell.done ? " nb-code--done" : "");
    wrap.innerHTML = `
      <div class="nb-code__toolbar">
        <button class="btn nb-code__run">${RUN_ICON}<span>${tr("ex.run", "Spustiť")}</span></button>
        <span class="nb-code__status ${cell.done ? "nb-code__status--ok" : "nb-code__status--idle"}">
          ${cell.done ? "✓ " + tr("ex.cellDone", "hotová") : tr("ex.cellIdle", "nespustená")}
        </span>
      </div>
      <div class="nb-code__editor"></div>
      <div class="nb-code__output"></div>`;

    const editorHost = wrap.querySelector(".nb-code__editor");
    const cm = CodeMirror(editorHost, {
      value: cell.source || "",
      mode: "python",
      lineNumbers: true,
      indentUnit: 4,
      viewportMargin: Infinity,
    });

    const statusEl = wrap.querySelector(".nb-code__status");
    const outEl = wrap.querySelector(".nb-code__output");
    const runBtn = wrap.querySelector(".nb-code__run");

    const rec = { code_index: cell.code_index, cm, statusEl, outEl, wrap };
    editors.push(rec);
    runBtn.addEventListener("click", () => runCell(rec, runBtn));
    return wrap;
  }

  async function runCell(rec, runBtn) {
    runBtn.disabled = true;
    rec.statusEl.className = "nb-code__status nb-code__status--idle";
    rec.statusEl.textContent = tr("ex.running", "spúšťam…");
    try {
      const r = await fetch(`/api/exercises/${exId}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ code_index: rec.code_index, code: rec.cm.getValue() }),
      });
      const data = await r.json();
      if (!r.ok) {
        rec.outEl.className = "nb-code__output nb-code__output--err";
        rec.outEl.textContent = data.error || tr("ex.runError", "Bunku sa nepodarilo spustiť.");
        rec.statusEl.className = "nb-code__status nb-code__status--err";
        rec.statusEl.textContent = tr("ex.cellErr", "chyba");
        return;
      }
      rec.outEl.className = "nb-code__output" + (data.ok ? "" : " nb-code__output--err");
      rec.outEl.textContent = (data.output || "") + (data.error || "");
      if (data.ok) {
        rec.wrap.classList.add("nb-code--done");
        rec.statusEl.className = "nb-code__status nb-code__status--ok";
        rec.statusEl.textContent = "✓ " + tr("ex.cellDone", "hotová");
      } else {
        rec.statusEl.className = "nb-code__status nb-code__status--err";
        rec.statusEl.textContent = tr("ex.cellErr", "chyba");
      }
      percent = data.percent;
      updateHeadBar();
    } catch (e) {
      rec.outEl.className = "nb-code__output nb-code__output--err";
      rec.outEl.textContent = tr("ex.runError", "Bunku sa nepodarilo spustiť.");
    } finally {
      runBtn.disabled = false;
    }
  }

  async function onComplete() {
    const btn = headEl.querySelector(".ex-head__done-btn");
    if (btn) btn.disabled = true;
    try {
      const r = await fetch(`/api/exercises/${exId}/complete`, {
        method: "POST", credentials: "include",
      });
      const data = await r.json();
      if (!r.ok) {
        if (btn) { btn.disabled = false; btn.textContent = tr("ex.notYet", "Ešte nie — spusti všetky bunky"); }
        return;
      }
      percent = 100;
      updateHeadBar();
      if (btn) { btn.textContent = "✓ " + tr("ex.done", "Dokončené"); btn.disabled = true; }
      setTimeout(() => { window.location.href = "/cvicenia"; }, 900);
    } catch (e) {
      if (btn) btn.disabled = false;
    }
  }

  async function load() {
    try {
      const r = await fetch(`/api/exercises/${exId}`, { credentials: "include" });
      if (r.status === 401) { window.location.href = "/login"; return; }
      if (r.status === 403) {
        const d = await r.json();
        root.innerHTML = lockedCard(d.error || tr("ex.locked", "Cvičenie je zamknuté."));
        return;
      }
      if (!r.ok) { root.innerHTML = lockedCard(tr("ex.loadError", "Cvičenie sa nepodarilo načítať.")); return; }

      const ex = await r.json();
      currentEx = ex;
      totalCode = ex.code_cells || 0;
      doneSet = new Set((ex.progress && ex.progress.done_cells) || []);
      percent = (ex.progress && ex.progress.percent) || 0;

      renderHead(ex);
      renderCells(ex.cells || []);
      updateHeadBar();
      hookLangChange();
      if (typeof I18N !== "undefined") I18N.apply();
    } catch (e) {
      root.innerHTML = lockedCard(tr("ex.loadError", "Cvičenie sa nepodarilo načítať."));
    }
  }

  load();
})();
