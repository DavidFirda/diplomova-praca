/* ============================================================
   AdaptPy - pracovná plocha jedného cvičenia.

   - Markdown bunky (marked) + editovateľné code bunky (CodeMirror).
   - Spúšťanie v sandboxe cez /api/exercises/<id>/run.
   - Perzistencia premenných: posiela sa `prelude` = kód buniek nad aktuálnou
     (v poradí na obrazovke, vrátane vlastných/scratch).
   - Grafy (matplotlib) sa zobrazia pod výstupom.
   - Časový limit cvičenia: počas behu beží ODPOČET; pri timeoute pekná hláška.
   - Vlastné bunky sa dajú vložiť kdekoľvek cez "＋".
   - Vpravo pripravený chat panel (napojí ho /js/pages/chat.js).
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

  // ---- SYNCHRÓNNY skeleton (aby chat.js našiel panel) ----
  const RUN_ICON = '<svg viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" fill="none"><polygon points="6 4 20 12 6 20 6 4"/></svg>';
  root.innerHTML = `
    <div class="ex-workspace">
      <div class="ex-nb-col">
        <div id="ex-head"><div class="ex-empty" data-i18n="ex.loading">Načítavam cvičenie…</div></div>
        <div id="ex-cells"></div>
        <div class="ex-addcell-note-bar" id="ex-addcell-bar" style="display:none;">
          <span class="ex-addcell-note" data-i18n="ex.scratchHint">Vlastné bunky na experimentovanie – nezapočítavajú sa do progresu. Pridať ich môžeš kdekoľvek cez „＋“.</span>
        </div>
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
  let runTimeout = 0;   // limit cvičenia (s); 0 = nevieme presne (default runnera)

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

  // --- i18n hook (prekreslenie pri zmene jazyka) ---
  function retranslateCells() {
    editors.forEach(rec => {
      const btnSpan = rec.wrap.querySelector(".nb-code__run span");
      if (btnSpan) btnSpan.textContent = tr("ex.run", "Spustiť");
      const st = rec.statusEl;
      if (!st) return;
      if (st.classList.contains("nb-code__status--ok")) st.textContent = "✓ " + tr("ex.cellDone", "hotová");
      else if (st.classList.contains("nb-code__status--err")) st.textContent = tr("ex.cellErr", "chyba");
      else if (st.classList.contains("nb-code__status--custom")) st.textContent = tr("ex.scratchCell", "vlastná bunka");
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
    const limitNote = runTimeout > 0
      ? `<span class="ex-head__limit">${tr("ex.limit", "Limit na bunku")}: ${runTimeout}s</span>` : "";
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
        ${limitNote}
      </div>`;
    headEl.querySelector("#ex-done-btn").addEventListener("click", onComplete);
  }

  function renderCells(cells) {
    cellsEl.innerHTML = "";
    editors = [];
    cellsEl.appendChild(insertBar());
    cells.forEach(cell => {
      if (cell.type === "markdown") {
        const div = document.createElement("div");
        div.className = "nb-md";
        try { div.innerHTML = (window.marked ? marked.parse(cell.source || "") : esc(cell.source || "")); }
        catch (e) { div.textContent = cell.source || ""; }
        rewriteAssets(div);
        cellsEl.appendChild(div);
      } else if (cell.type === "code") {
        cellsEl.appendChild(buildCodeCell(cell));
      }
      cellsEl.appendChild(insertBar());
    });
    refreshEditors();
  }

  function refreshEditors() {
    const doRefresh = () => editors.forEach(e => { try { e.cm.refresh(); } catch (err) {} });
    requestAnimationFrame(doRefresh);
    setTimeout(doRefresh, 120);
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

  // tenká vsuvka "＋" - vloží vlastnú bunku presne na toto miesto
  function insertBar() {
    const bar = document.createElement("div");
    bar.className = "ex-insert";
    bar.innerHTML = `<button class="ex-insert__btn" title="${tr("ex.insertHere", "Pridať bunku sem")}">
        <span class="ex-insert__plus">＋</span>
        <span class="ex-insert__label">${tr("ex.insertHere", "Pridať bunku sem")}</span>
      </button>`;
    bar.querySelector(".ex-insert__btn").addEventListener("click", () => addScratchCellAt(bar));
    return bar;
  }

  function buildCodeCell(cell) {
    const custom = !!cell.custom;
    const wrap = document.createElement("div");
    wrap.className = "nb-code" + (cell.done ? " nb-code--done" : "") + (custom ? " nb-code--custom" : "");
    wrap.innerHTML = `
      <div class="nb-code__toolbar">
        <button class="btn nb-code__run">${RUN_ICON}<span>${tr("ex.run", "Spustiť")}</span></button>
        ${(!custom && cell.timeout) ? `<span class="nb-code__limit" title="${tr("ex.limit", "Limit na bunku")}">⏱ ${cell.timeout}s</span>` : ""}
        ${custom ? `<button class="nb-code__remove" title="${tr("ex.removeCell", "Odstrániť bunku")}">✕</button>` : ""}
        <span class="nb-code__status ${custom ? "nb-code__status--custom" : (cell.done ? "nb-code__status--ok" : "nb-code__status--idle")}">
          ${custom ? tr("ex.scratchCell", "vlastná bunka") : (cell.done ? "✓ " + tr("ex.cellDone", "hotová") : tr("ex.cellIdle", "nespustená"))}
        </span>
      </div>
      <div class="nb-code__editor"></div>
      <div class="nb-code__output"></div>
      <div class="nb-code__images"></div>`;

    const editorHost = wrap.querySelector(".nb-code__editor");
    const initialCode = (cell.saved != null) ? cell.saved : (cell.source || "");
    const cm = CodeMirror(editorHost, {
      value: initialCode, mode: "python", lineNumbers: true,
      indentUnit: 4, viewportMargin: Infinity,
    });

    const statusEl = wrap.querySelector(".nb-code__status");
    const outEl = wrap.querySelector(".nb-code__output");
    const imagesEl = wrap.querySelector(".nb-code__images");
    const runBtn = wrap.querySelector(".nb-code__run");

    const rec = { code_index: cell.code_index, cm, statusEl, outEl, imagesEl, wrap, custom, timeout: (!custom && cell.timeout) ? cell.timeout : 0 };
    wrap.__rec = rec;
    editors.push(rec);
    runBtn.addEventListener("click", () => runCell(rec, runBtn));

    if (custom) {
      const rmBtn = wrap.querySelector(".nb-code__remove");
      if (rmBtn) rmBtn.addEventListener("click", () => {
        editors = editors.filter(e => e !== rec);
        const next = wrap.nextElementSibling;
        if (next && next.classList.contains("ex-insert")) next.remove();
        wrap.remove();
      });
    }
    return wrap;
  }

  let scratchCounter = 1000;
  function addScratchCellAt(afterBar) {
    const parent = afterBar.parentNode;
    if (!parent) return;
    const wrap = buildCodeCell({ type: "code", code_index: scratchCounter++, source: "", done: false, custom: true });
    const newBar = insertBar();
    parent.insertBefore(wrap, afterBar.nextSibling);
    parent.insertBefore(newBar, wrap.nextSibling);
    const rec = editors[editors.length - 1];
    requestAnimationFrame(() => { try { rec.cm.refresh(); rec.cm.focus(); } catch (e) {} });
    wrap.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  // poskladá kód všetkých code-buniek NAD danou (v poradí na obrazovke)
  function buildPrelude(currentWrap) {
    const wraps = [...cellsEl.querySelectorAll(".nb-code")];
    const codes = [];
    for (const w of wraps) {
      if (w === currentWrap) break;
      if (w.__rec && w.__rec.cm) codes.push(w.__rec.cm.getValue());
    }
    return codes.join("\n\n");
  }

  function renderImages(rec, images) {
    if (!rec.imagesEl) return;
    if (!images || !images.length) { rec.imagesEl.innerHTML = ""; return; }
    rec.imagesEl.innerHTML = images.map(src => `<img class="nb-img" src="${src}" alt="graf">`).join("");
  }

  async function runCell(rec, runBtn) {
    runBtn.disabled = true;
    rec.statusEl.className = "nb-code__status nb-code__status--idle";

    // --- odpočet (orientačný; reálny strop drží runner) ---
    const cellLimit = rec.timeout || runTimeout;
    let left = cellLimit;
    const tick = () => {
      rec.statusEl.textContent = left > 0
        ? `${tr("ex.running", "spúšťam…")} (${left}s)`
        : tr("ex.running", "spúšťam…");
      left -= 1;
    };
    tick();
    const timer = cellLimit > 0 ? setInterval(tick, 1000) : null;
    const stopTimer = () => { if (timer) clearInterval(timer); };

    try {
      const r = await fetch(`/api/exercises/${exId}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          code_index: rec.code_index,
          code: rec.cm.getValue(),
          prelude: buildPrelude(rec.wrap),
        }),
      });
      const data = await r.json();
      stopTimer();

      if (!r.ok) {
        rec.outEl.className = "nb-code__output nb-code__output--err";
        rec.outEl.textContent = data.error || tr("ex.runError", "Bunku sa nepodarilo spustiť.");
        rec.statusEl.className = "nb-code__status nb-code__status--err";
        rec.statusEl.textContent = tr("ex.cellErr", "chyba");
        renderImages(rec, []);
        return;
      }

      // --- timeout (zastavené limitom) ---
      if (data.timed_out) {
        rec.outEl.className = "nb-code__output nb-code__output--timeout";
        rec.outEl.textContent = data.error || tr("ex.timeout", "Kód bol zastavený, lebo prekročil časový limit.");
        rec.statusEl.className = "nb-code__status nb-code__status--err";
        rec.statusEl.textContent = tr("ex.timedOut", "zastavené (limit)");
        renderImages(rec, []);
        return;
      }

      rec.outEl.className = "nb-code__output" + (data.ok ? "" : " nb-code__output--err");
      rec.outEl.textContent = (data.output || "") + (data.error || "");
      renderImages(rec, data.images);

      if (rec.custom) {
        rec.statusEl.className = "nb-code__status " + (data.ok ? "nb-code__status--custom" : "nb-code__status--err");
        rec.statusEl.textContent = data.ok ? tr("ex.scratchCell", "vlastná bunka") : tr("ex.cellErr", "chyba");
        return;
      }
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
      stopTimer();
      rec.outEl.className = "nb-code__output nb-code__output--err";
      rec.outEl.textContent = tr("ex.runError", "Bunku sa nepodarilo spustiť.");
    } finally {
      stopTimer();
      runBtn.disabled = false;
    }
  }

  async function onComplete() {
    const btn = headEl.querySelector(".ex-head__done-btn");
    if (btn) btn.disabled = true;
    try {
      const r = await fetch(`/api/exercises/${exId}/complete`, { method: "POST", credentials: "include" });
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
      runTimeout = ex.run_timeout || 0;

      renderHead(ex);
      renderCells(ex.cells || []);
      updateHeadBar();
      hookLangChange();

      const bar = document.getElementById("ex-addcell-bar");
      if (bar) bar.style.display = "flex";

      if (typeof I18N !== "undefined") I18N.apply();
    } catch (e) {
      root.innerHTML = lockedCard(tr("ex.loadError", "Cvičenie sa nepodarilo načítať."));
    }
  }

  load();
})();
