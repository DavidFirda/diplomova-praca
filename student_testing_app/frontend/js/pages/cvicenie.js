/* ============================================================
   AdaptPy - pracovná plocha jedného cvičenia.

   - Markdown bunky (marked) + editovateľné code bunky (CodeMirror).
   - Spúšťanie v sandboxe cez /api/exercises/<id>/run.
   - Perzistencia premenných: posiela sa `prelude` = kód buniek nad aktuálnou
     (v poradí na obrazovke, vrátane vlastných/scratch).
   - Grafy (matplotlib) sa zobrazia pod výstupom.
   - Časový limit cvičenia: počas behu beží ODPOČET; pri timeoute pekná hláška.
   - Vlastné bunky sa dajú vložiť kdekoľvek cez "＋".
   - Vpravo AI asistent cvičenia (RAG nad prednáškami, js/core/ai_chat.js): vidí zadanie
     aktuálnej bunky a kód študenta; kód z odpovede vloží do bunky LEN po potvrdení
     študentom (výber bunky + nahradiť/pridať). Vloženie sa zaloguje.
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

  // ---- SYNCHRÓNNY skeleton (notebook + panel asistenta) ----
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
        <!-- AI asistent cvičenia: rovnaký vzhľad ako na dashboarde a v Úlohách, ale stále viditeľný.
             Na desktope je pripnutý vpravo, na tablete/mobile dole (dá sa rozbaliť, správanie v chat.js).
             Odpovede, zdroje a vloženie kódu do bunky rieši js/core/ai_chat.js + initAssistant() nižšie. -->
        <section class="chat-panel ai-panel" id="chat-panel" aria-labelledby="chat-title">
          <header class="chat-panel__header">
            <div class="ul-avatar ul-avatar--lg" aria-hidden="true">
              <svg class="ul-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.2v3"/><circle cx="12" cy="2.9" r="1" fill="currentColor" stroke="none"/><rect x="4.5" y="6.5" width="15" height="12.5" rx="4.2"/><path d="M2.4 11.6v3.2M21.6 11.6v3.2"/><circle cx="9.1" cy="12" r="1.25" fill="currentColor" stroke="none"/><circle cx="14.9" cy="12" r="1.25" fill="currentColor" stroke="none"/><path d="M9.4 15.6c.75.6 1.6.9 2.6.9s1.85-.3 2.6-.9"/></svg>
            </div>
            <div class="chat-panel__title">
              <strong id="chat-title" data-i18n="ex.aiTitle">AI asistent cvičenia</strong>
              <span class="chat-panel__status"><i class="ul-online" aria-hidden="true"></i><span data-i18n="chat.online">Online · pomôžem ti s cvičením</span></span>
              <span class="chat-panel__preview" id="chat-preview" aria-hidden="true"></span>
            </div>
            <span class="ai-panel__cell" id="ai-active-cell" data-i18n-title="ex.aiActiveCell" title="Bunka, ku ktorej sa pýtaš"></span>
            <button type="button" class="chat-panel__toggle" id="chat-toggle" aria-expanded="false" aria-controls="chat-messages" data-i18n-aria-label="chat.expand" aria-label="Rozbaliť chat">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 15l6-6 6 6"/></svg>
            </button>
          </header>
          <div class="chat-panel__messages" id="chat-messages" aria-live="polite"></div>
          <div class="chat-panel__quick">
            <button type="button" class="ul-chip" data-ai-prompt="ex.aiExplainTaskMsg" data-i18n="chat.chipExplain">Vysvetli mi zadanie</button>
            <button type="button" class="ul-chip" data-ai-prompt="ex.aiHintMsg" data-i18n="chat.chipHint">Daj mi nápovedu</button>
            <button type="button" class="ul-chip" data-ai-prompt="ex.aiSkeletonMsg" data-i18n="ex.aiSkeleton">Daj mi kostru riešenia</button>
          </div>
          <form class="chat-panel__input" id="chat-form" autocomplete="off">
            <input type="text" id="chat-input" maxlength="1500" autocomplete="off" data-i18n-placeholder="ex.aiPlaceholder" placeholder="Opýtaj sa na látku alebo svoj kód…" />
            <button type="submit" class="ul-send chat-panel__send" data-i18n-aria-label="chat.send" aria-label="Odoslať">
              <svg class="ul-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 3 10.5 13.5"/><path d="M21 3l-6.5 18-4-7.5L3 9.5 21 3z"/></svg>
            </button>
          </form>
        </section>
      </aside>
    </div>`;

  if (!exId) {
    root.innerHTML = lockedCard(tr("ex.badId", "Chýba identifikátor cvičenia."));
    return;
  }

  const headEl = document.getElementById("ex-head");
  const cellsEl = document.getElementById("ex-cells");

  let editors = [];
  let activeRec = null;   // bunka, v ktorej študent naposledy písal (kontext pre asistenta)
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
        <span class="nb-code__num">${custom ? "✎" : (cell.code_index + 1)}</span>
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

    // kontrola originality: zákaz vkladania zvonku + sledovanie písania (js/core/originality.js)
    const guard = (typeof Originality !== "undefined") ? Originality.attach(cm) : null;
    const rec = { code_index: cell.code_index, cm, guard, statusEl, outEl, imagesEl, wrap, custom, timeout: (!custom && cell.timeout) ? cell.timeout : 0, lastOutput: "" };
    wrap.__rec = rec;
    editors.push(rec);
    cm.on("focus", () => setActive(rec));
    runBtn.addEventListener("click", () => runCell(rec, runBtn));

    if (custom) {
      const rmBtn = wrap.querySelector(".nb-code__remove");
      if (rmBtn) rmBtn.addEventListener("click", () => {
        editors = editors.filter(e => e !== rec);
        if (activeRec === rec) setActive(null);
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
    const prevStatus = { cls: rec.statusEl.className, text: rec.statusEl.textContent };
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
      const code = rec.cm.getValue();
      const prelude = buildPrelude(rec.wrap);
      const send = async (integrity) => {
        const r = await fetch(`/api/exercises/${exId}/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ code_index: rec.code_index, code, prelude, integrity }),
        });
        let data = {};
        try { data = await r.json(); } catch (e) { /* prázdne telo */ }
        return { r, data };
      };
      // podozrivé písanie -> server chce potvrdenie, Originality ukáže okno a spustí znova
      const sent = rec.guard
        ? await Originality.submit(rec.guard, send, (x) => x.data)
        : await send(undefined);
      stopTimer();
      if (sent.cancelled) {                     // študent sa vrátil k úprave - nič sa nespustilo
        rec.statusEl.className = prevStatus.cls;
        rec.statusEl.textContent = prevStatus.text;
        return;
      }
      const { r, data } = sent;

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
      rec.lastOutput = rec.outEl.textContent;
      setActive(rec);
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

  // =========================================================
  // AI asistent cvičenia
  // =========================================================
  const chatBox = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const activeLabel = document.getElementById("ai-active-cell");
  let chat = null;
  let chatBusy = false;

  function cellLabel(rec) {
    if (!rec) return "";
    if (rec.custom) return tr("ex.aiScratch", "vlastná bunka");
    return `${tr("ex.aiCell", "Bunka")} ${rec.code_index + 1}`;
  }
  function firstLine(code) {
    const line = (code || "").split("\n").find(l => l.trim() && !l.trim().startsWith("#")) || "";
    return line.trim().slice(0, 40);
  }
  function setActive(rec) {
    activeRec = rec;
    editors.forEach(e => e.wrap.classList.toggle("nb-code--active", e === rec));
    if (activeLabel) activeLabel.textContent = rec ? cellLabel(rec) : "";
  }
  function recByValue(value) {
    return editors.find(e => (e.custom ? "cx:" : "nb:") + e.code_index === value);
  }

  // ciele vloženia: všetky bunky v poradí na obrazovke, predvolená je aktívna
  function insertTargets() {
    const wraps = [...cellsEl.querySelectorAll(".nb-code")];
    return wraps.map(w => w.__rec).filter(Boolean).map(rec => ({
      value: (rec.custom ? "cx:" : "nb:") + rec.code_index,
      short: cellLabel(rec),
      label: `${cellLabel(rec)}${firstLine(rec.cm.getValue()) ? " – " + firstLine(rec.cm.getValue()) : ""}`,
      selected: rec === activeRec,
    }));
  }

  // vloženie kódu do bunky (študent potvrdil v okne asistenta)
  function applyInsert(code, target, how) {
    const rec = recByValue(target);
    if (!rec) return false;
    const cm = rec.cm;
    const last = cm.lastLine();
    const end = { line: last, ch: cm.getLine(last).length };
    if (how === "replace") cm.replaceRange(code, { line: 0, ch: 0 }, end, "assistant");
    else cm.replaceRange((cm.getValue().trim() ? "\n\n" : "") + code, end, end, "assistant");
    setActive(rec);
    if (window.adaptpyChatPanel && window.adaptpyChatPanel.isDock()) window.adaptpyChatPanel.setExpanded(false);
    rec.wrap.scrollIntoView({ behavior: "smooth", block: "center" });
    rec.wrap.classList.add("nb-code--inserted");
    setTimeout(() => rec.wrap.classList.remove("nb-code--inserted"), 1600);
    try { cm.focus(); } catch (e) {}
    return true;
  }

  function setChatBusy(on) {
    chatBusy = on;
    if (chatInput) chatInput.disabled = on;
    document.querySelectorAll("#chat-panel [data-ai-prompt]").forEach(b => { b.disabled = on; });
  }

  async function askAssistant(text) {
    if (!chat || chatBusy || !text) return;
    setChatBusy(true);
    const rec = activeRec;
    const body = {
      mode: "exercise", exercise_id: Number(exId), message: text,
      cell_index: rec && !rec.custom ? rec.code_index : null,
      cell_code: rec ? rec.cm.getValue() : null,
      cell_output: rec ? (rec.lastOutput || "") : "",
    };
    const shown = rec ? `${text}\n(${cellLabel(rec)})` : text;
    await AiChat.ask(chat, body, { userText: shown });
    setChatBusy(false);
    if (chatInput) chatInput.focus({ preventScroll: true });
  }

  async function initAssistant() {
    if (chat || typeof AiChat === "undefined" || !chatBox) return;
    chat = AiChat.view(chatBox, { insert: { targets: insertTargets, apply: applyInsert } });
    chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = chatInput.value.trim();
      if (!text) return;
      chatInput.value = "";
      askAssistant(text);
    });
    // rýchle otázky: na tlačidle je krátky popis, odošle sa celá otázka (data-ai-prompt = kľúč prekladu)
    document.querySelectorAll("#chat-panel [data-ai-prompt]").forEach(b => {
      b.addEventListener("click", () => askAssistant(tr(b.dataset.aiPrompt, b.textContent.trim())));
    });

    const messages = await AiChat.history({ mode: "exercise", exercise_id: exId });
    if (messages.length) chat.restore(messages);
    else chat.plain(tr("ex.aiGreeting", "Ahoj! Som AI asistent tohto cvičenia. Klikni do bunky, s ktorou potrebuješ pomôcť, a opýtaj sa. Vysvetlím ti látku z prednášok a navediem ťa – celé riešenie ti nenapíšem, ale dám ti kostru. Kód do bunky vložím len keď to potvrdíš."), false);
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
      initAssistant();

      if (typeof I18N !== "undefined") I18N.apply();
    } catch (e) {
      root.innerHTML = lockedCard(tr("ex.loadError", "Cvičenie sa nepodarilo načítať."));
    }
  }

  load();
})();
