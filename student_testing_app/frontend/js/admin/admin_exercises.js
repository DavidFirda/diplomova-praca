/* ============================================================
   AdaptPy - admin: správa cvičení.
   - responzívne karty
   - prepínače Publikované / Sprístupnené, poradie, mazanie, rescan
   - EDITOR NOTEBOOKU (markdown + code bunky)
   - úprava metadát vrátane ČASOVÉHO LIMITU na bunku (run_timeout)
   ============================================================ */
(function () {
  const listEl = document.getElementById("ex-admin-list");
  if (!listEl) return;

  function tr(key, fallback) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fallback;
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, m => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]
    ));
  }

  let items = [];

  // ---------- zoznam ----------
  function itemRow(ex) {
    const stats = ex.stats || { completed: 0, in_progress: 0 };
    const limit = ex.run_timeout ? ` · ${ex.run_timeout}s` : "";
    return `
      <div class="exadmin-item" data-id="${ex.id}">
        <div class="exadmin-item__ord">${ex.order_index}</div>
        <div class="exadmin-item__main">
          <div class="exadmin-item__title">${esc(ex.title_sk || ex.slug)}</div>
          <div class="exadmin-item__meta">
            ${esc(ex.filename)} · ${ex.code_cells} ${tr("exadmin.cells", "buniek")}${limit}
            · ✓ ${stats.completed} ${tr("exadmin.completedBy", "dokončili")}
          </div>
          <div class="exadmin-item__controls">
            <label class="ex-toggle">
              <input type="checkbox" class="ex-pub" ${ex.published ? "checked" : ""}>
              <span class="ex-toggle__track"></span>
              <span>${tr("exadmin.published", "Publikované")}</span>
            </label>
            <label class="ex-toggle">
              <input type="checkbox" class="ex-acc" ${ex.accessible ? "checked" : ""}>
              <span class="ex-toggle__track"></span>
              <span>${tr("exadmin.accessible", "Sprístupnené")}</span>
            </label>
            <div class="exadmin-item__actions">
              <button class="btn btn--secondary ex-notebook">${tr("exadmin.notebook", "Upraviť notebook")}</button>
              <button class="btn btn--secondary ex-edit">${tr("exadmin.edit", "Metadáta")}</button>
              <button class="btn btn--secondary ex-del">${tr("exadmin.delete", "Vymazať")}</button>
            </div>
          </div>
        </div>
      </div>`;
  }

  function render() {
    if (!items.length) {
      listEl.innerHTML = `<div class="ex-empty">${tr("exadmin.empty", "Zatiaľ žiadne cvičenia. Nahraj prvý notebook vyššie.")}</div>`;
      return;
    }
    listEl.innerHTML = items.map(itemRow).join("");
    listEl.querySelectorAll(".exadmin-item").forEach(el => {
      const id = +el.getAttribute("data-id");
      el.querySelector(".ex-pub").addEventListener("change", e => patch(id, { published: e.target.checked }));
      el.querySelector(".ex-acc").addEventListener("change", e => patch(id, { accessible: e.target.checked }));
      el.querySelector(".ex-notebook").addEventListener("click", () => openNotebook(id));
      el.querySelector(".ex-edit").addEventListener("click", () => openEdit(id));
      el.querySelector(".ex-del").addEventListener("click", () => del(id));
    });
    if (typeof I18N !== "undefined") I18N.apply();
  }

  async function load() {
    try {
      const r = await fetch("/api/admin/exercises", { credentials: "include" });
      if (r.status === 401 || r.status === 403) {
        listEl.innerHTML = `<div class="ex-empty">${tr("exadmin.noAccess", "Prístup len pre administrátora.")}</div>`;
        return;
      }
      const d = await r.json();
      items = d.exercises || [];
      render();
    } catch (e) {
      listEl.innerHTML = `<div class="ex-empty">${tr("exadmin.loadError", "Načítanie zlyhalo.")}</div>`;
    }
  }

  async function patch(id, body) {
    try {
      const r = await fetch(`/api/admin/exercises/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });
      const d = await r.json();
      if (r.ok && d.exercise) { items = items.map(x => x.id === id ? d.exercise : x); render(); }
    } catch (e) {}
  }

  async function del(id) {
    if (!confirm(tr("exadmin.confirmDel", "Vymazať toto cvičenie? Progres študentov k nemu sa tiež odstráni."))) return;
    const alsoFile = confirm(tr("exadmin.delFile", "Vymazať aj samotný .ipynb súbor z priečinka? (OK = áno)"));
    try {
      const r = await fetch(`/api/admin/exercises/${id}?file=${alsoFile ? "1" : "0"}`, {
        method: "DELETE", credentials: "include",
      });
      if (r.ok) { items = items.filter(x => x.id !== id); render(); }
    } catch (e) {}
  }

  // ---------- upload ----------
  const uploadBtn = document.getElementById("ex-upload-btn");
  const uploadMsg = document.getElementById("ex-upload-msg");
  function showMsg(text, isErr) {
    uploadMsg.style.display = "block";
    uploadMsg.className = isErr ? "error-message" : "info-message";
    uploadMsg.textContent = text;
  }
  // pole „Časový limit“ vo formulári nahrávania (ak ho HTML ešte nemá, vloží sa samo)
  if (uploadBtn && !document.getElementById("ex-timeout")) {
    const grp = document.createElement("div");
    grp.className = "form-group ex-upload-timeout";
    grp.innerHTML = `<label for="ex-timeout" data-i18n="exadmin.timeout">${tr("exadmin.timeout", "Časový limit na bunku (s) – prázdne = predvolené")}</label>
      <input type="number" id="ex-timeout" min="1" max="60" placeholder="napr. 10" />`;
    uploadBtn.parentNode.insertBefore(grp, uploadBtn);
  }
  if (uploadBtn) uploadBtn.addEventListener("click", async () => {
    const fileInput = document.getElementById("ex-file");
    if (!fileInput.files.length) { showMsg(tr("exadmin.pickFile", "Vyber súbor .ipynb."), true); return; }
    const fd = new FormData();
    fd.append("file", fileInput.files[0]);
    fd.append("title_sk", document.getElementById("ex-title-sk").value);
    fd.append("title_en", document.getElementById("ex-title-en").value);
    fd.append("description_sk", document.getElementById("ex-desc-sk").value);
    fd.append("order_index", document.getElementById("ex-order").value);
    const toEl = document.getElementById("ex-timeout");
    if (toEl) fd.append("run_timeout", toEl.value);
    uploadBtn.disabled = true;
    try {
      const r = await fetch("/api/admin/exercises", { method: "POST", credentials: "include", body: fd });
      const d = await r.json();
      if (!r.ok) { showMsg(d.error || tr("exadmin.uploadErr", "Nahratie zlyhalo."), true); return; }
      showMsg(tr("exadmin.uploaded", "Cvičenie nahraté. Nezabudni ho publikovať a sprístupniť."), false);
      ["ex-file", "ex-title-sk", "ex-title-en", "ex-desc-sk", "ex-order", "ex-timeout"].forEach(i => { const el = document.getElementById(i); if (el) el.value = ""; });
      load();
    } catch (e) {
      showMsg(tr("exadmin.uploadErr", "Nahratie zlyhalo."), true);
    } finally { uploadBtn.disabled = false; }
  });

  // ---------- rescan ----------
  const rescanBtn = document.getElementById("ex-rescan");
  if (rescanBtn) rescanBtn.addEventListener("click", async () => {
    rescanBtn.disabled = true;
    try {
      const r = await fetch("/api/admin/exercises/rescan", { method: "POST", credentials: "include" });
      const d = await r.json();
      if (r.ok) { items = d.exercises || []; render(); }
    } catch (e) {} finally { rescanBtn.disabled = false; }
  });

  // ---------- edit metadát ----------
  const modal = document.getElementById("ex-edit-modal");
  const modalBody = document.getElementById("ex-edit-body");
  window.exadminCloseEdit = () => { modal.style.display = "none"; };

  function openEdit(id) {
    const ex = items.find(x => x.id === id);
    if (!ex) return;
    modalBody.innerHTML = `
      <label>${tr("exadmin.titleSk", "Názov (SK)")}</label>
      <input type="text" id="edit-title-sk" value="${esc(ex.title_sk)}" />
      <label>${tr("exadmin.titleEn", "Názov (EN)")}</label>
      <input type="text" id="edit-title-en" value="${esc(ex.title_en)}" />
      <label>${tr("exadmin.descSk", "Popis (SK)")}</label>
      <textarea id="edit-desc-sk">${esc(ex.description_sk)}</textarea>
      <label>${tr("exadmin.descEn", "Popis (EN)")}</label>
      <textarea id="edit-desc-en">${esc(ex.description_en)}</textarea>
      <label>${tr("exadmin.order", "Poradie")}</label>
      <input type="number" id="edit-order" value="${ex.order_index}" />
      <label>${tr("exadmin.timeout", "Časový limit na bunku (s) – prázdne = predvolené")}</label>
      <input type="number" id="edit-timeout" min="1" max="60" value="${ex.run_timeout != null ? ex.run_timeout : ""}" />
      <label>${tr("exadmin.topics", "Témy / časti (každá na nový riadok)")}</label>
      <textarea id="edit-topics">${esc((ex.topics || []).join("\n"))}</textarea>
      <button class="btn" id="edit-save">${tr("exadmin.save", "Uložiť")}</button>
    `;
    modal.style.display = "flex";
    document.getElementById("edit-save").addEventListener("click", async () => {
      await patch(id, {
        title_sk: document.getElementById("edit-title-sk").value,
        title_en: document.getElementById("edit-title-en").value,
        description_sk: document.getElementById("edit-desc-sk").value,
        description_en: document.getElementById("edit-desc-en").value,
        order_index: document.getElementById("edit-order").value,
        run_timeout: document.getElementById("edit-timeout").value,
        topics: document.getElementById("edit-topics").value.split("\n").map(s => s.trim()).filter(Boolean),
      });
      modal.style.display = "none";
    });
  }

  // ============================================================
  //  EDITOR NOTEBOOKU (markdown + code bunky)
  // ============================================================
  let nbObj = null;
  let nbExId = null;

  function ensureNbModal() {
    if (document.getElementById("nbedit-modal")) return;
    const el = document.createElement("div");
    el.className = "nbedit-modal";
    el.id = "nbedit-modal";
    el.style.display = "none";
    el.innerHTML = `
      <div class="nbedit-backdrop"></div>
      <div class="nbedit-panel">
        <div class="nbedit-header">
          <h2 class="nbedit-title">${tr("exadmin.nbTitle", "Úprava notebooku")}: <span id="nbedit-name"></span></h2>
          <div class="nbedit-header__actions">
            <button class="btn btn--secondary btn--sm" id="nbedit-add-md">+ ${tr("exadmin.textCell", "Text")}</button>
            <button class="btn btn--secondary btn--sm" id="nbedit-add-code">+ ${tr("exadmin.codeCell", "Kód")}</button>
            <button class="btn btn--sm" id="nbedit-save">${tr("exadmin.save", "Uložiť")}</button>
            <button class="icon-btn" id="nbedit-close" aria-label="Zavrieť">✕</button>
          </div>
        </div>
        <div class="nbedit-hint" id="nbedit-hint"></div>
        <div class="nbedit-body" id="nbedit-cells"></div>
      </div>`;
    document.body.appendChild(el);
    el.querySelector(".nbedit-backdrop").addEventListener("click", closeNotebook);
    el.querySelector("#nbedit-close").addEventListener("click", closeNotebook);
    el.querySelector("#nbedit-add-md").addEventListener("click", () => addCell("markdown"));
    el.querySelector("#nbedit-add-code").addEventListener("click", () => addCell("code"));
    el.querySelector("#nbedit-save").addEventListener("click", saveNotebook);
  }

  function closeNotebook() {
    const m = document.getElementById("nbedit-modal");
    if (m) m.style.display = "none";
    nbObj = null; nbExId = null;
  }

  function cellSourceToText(cell) {
    const s = cell.source;
    return Array.isArray(s) ? s.join("") : (s || "");
  }

  function autoGrow(ta) {
    ta.style.height = "auto";
    ta.style.height = Math.min(600, Math.max(70, ta.scrollHeight + 2)) + "px";
  }

  function cellBlock(type, text, timeout) {
    const block = document.createElement("div");
    block.className = "nbedit-cell";
    block.dataset.type = type;
    block.innerHTML = `
      <div class="nbedit-cell__bar">
        <span class="nbedit-cell__tag nbedit-cell__tag--${type}">${type === "code" ? tr("exadmin.codeCell", "Kód") : tr("exadmin.textCell", "Text")}</span>
        ${type === "code" ? `<label class="nbedit-limit">${tr("exadmin.cellLimit", "limit (s)")}
          <input type="number" class="nbedit-limit__input" min="1" max="60" placeholder="—" value="${timeout ? Number(timeout) : ""}" />
        </label>` : ""}
        <div class="nbedit-cell__ops">
          <button class="nbedit-op" data-op="up" title="Hore">↑</button>
          <button class="nbedit-op" data-op="down" title="Dole">↓</button>
          <button class="nbedit-op" data-op="type" title="Prepnúť typ">⇄ ${type === "code" ? tr("exadmin.textCell", "Text") : tr("exadmin.codeCell", "Kód")}</button>
          <button class="nbedit-op nbedit-op--del" data-op="del" title="Zmazať">✕</button>
        </div>
      </div>
      <textarea class="nbedit-cell__src" spellcheck="false"></textarea>`;
    const ta = block.querySelector("textarea");
    ta.value = text;
    ta.classList.toggle("nbedit-cell__src--code", type === "code");
    ta.addEventListener("input", () => autoGrow(ta));

    block.querySelectorAll(".nbedit-op").forEach(btn => {
      btn.addEventListener("click", () => {
        const op = btn.dataset.op;
        if (op === "del") { if (confirm(tr("exadmin.delCell", "Zmazať túto bunku?"))) block.remove(); }
        else if (op === "up") { const prev = block.previousElementSibling; if (prev) block.parentNode.insertBefore(block, prev); }
        else if (op === "down") { const next = block.nextElementSibling; if (next) block.parentNode.insertBefore(next, block); }
        else if (op === "type") {
          const newType = block.dataset.type === "code" ? "markdown" : "code";
          const limEl = block.querySelector(".nbedit-limit__input");
          const replacement = cellBlock(newType, ta.value, limEl ? limEl.value : "");
          block.replaceWith(replacement);
          requestAnimationFrame(() => autoGrow(replacement.querySelector("textarea")));
        }
      });
    });
    return block;
  }

  function addCell(type) {
    const host = document.getElementById("nbedit-cells");
    const block = cellBlock(type, "");
    host.appendChild(block);
    const ta = block.querySelector("textarea");
    autoGrow(ta); ta.focus();
    block.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function openNotebook(id) {
    ensureNbModal();
    nbExId = id;
    const ex = items.find(x => x.id === id);
    document.getElementById("nbedit-name").textContent = ex ? (ex.filename || ex.slug) : "";
    const host = document.getElementById("nbedit-cells");
    const hint = document.getElementById("nbedit-hint");
    host.innerHTML = `<div class="ex-empty">${tr("exadmin.loading", "Načítavam…")}</div>`;
    hint.textContent = "";
    document.getElementById("nbedit-modal").style.display = "flex";

    try {
      const r = await fetch(`/api/admin/exercises/${id}/raw`, { credentials: "include" });
      const d = await r.json();
      if (!r.ok) { host.innerHTML = `<div class="ex-empty">${esc(d.error || tr("exadmin.loadError", "Načítanie zlyhalo."))}</div>`; return; }
      nbObj = JSON.parse(d.content);
      if (!nbObj.cells) nbObj.cells = [];
      host.innerHTML = "";
      nbObj.cells.forEach(c => {
        const type = c.cell_type === "code" ? "code" : "markdown";
        const to = type === "code" && c.metadata && c.metadata.adaptpy ? c.metadata.adaptpy.timeout : "";
        host.appendChild(cellBlock(type, cellSourceToText(c), to));
      });
      requestAnimationFrame(() => host.querySelectorAll("textarea").forEach(autoGrow));
    } catch (e) {
      host.innerHTML = `<div class="ex-empty">${tr("exadmin.parseErr", "Notebook sa nepodarilo prečítať (neplatný JSON).")}</div>`;
    }
  }

  async function saveNotebook() {
    if (!nbObj || nbExId == null) return;
    const hint = document.getElementById("nbedit-hint");
    const blocks = [...document.querySelectorAll("#nbedit-cells .nbedit-cell")];
    const cells = blocks.map(b => {
      const type = b.dataset.type;
      const text = b.querySelector("textarea").value;
      if (type === "code") {
        const limEl = b.querySelector(".nbedit-limit__input");
        const lim = limEl ? parseInt(limEl.value, 10) : NaN;
        const meta = (lim > 0) ? { adaptpy: { timeout: Math.min(lim, 60) } } : {};
        return { cell_type: "code", metadata: meta, execution_count: null, outputs: [], source: text };
      }
      return { cell_type: "markdown", metadata: {}, source: text };
    });
    nbObj.cells = cells;
    if (!nbObj.nbformat) nbObj.nbformat = 4;
    if (!nbObj.nbformat_minor) nbObj.nbformat_minor = 5;
    if (!nbObj.metadata) nbObj.metadata = {};

    const saveBtn = document.getElementById("nbedit-save");
    saveBtn.disabled = true;
    hint.className = "nbedit-hint";
    hint.textContent = tr("exadmin.saving", "Ukladám…");
    try {
      const r = await fetch(`/api/admin/exercises/${nbExId}/raw`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ content: JSON.stringify(nbObj, null, 1) }),
      });
      const d = await r.json();
      if (!r.ok) {
        hint.className = "nbedit-hint nbedit-hint--err";
        hint.textContent = d.error || tr("exadmin.saveErr", "Uloženie zlyhalo.");
        return;
      }
      if (d.exercise) { items = items.map(x => x.id === nbExId ? d.exercise : x); render(); }
      hint.className = "nbedit-hint nbedit-hint--ok";
      hint.textContent = tr("exadmin.saved2", "Uložené ✓");
    } catch (e) {
      hint.className = "nbedit-hint nbedit-hint--err";
      hint.textContent = tr("exadmin.saveErr", "Uloženie zlyhalo.");
    } finally { saveBtn.disabled = false; }
  }

  function hookLangChange() {
    if (typeof I18N === "undefined" || typeof I18N.setLang !== "function") return;
    if (I18N.__exAdminHooked) return;
    const orig = I18N.setLang.bind(I18N);
    I18N.setLang = function (l) { orig(l); render(); };
    I18N.__exAdminHooked = true;
  }

  hookLangChange();
  load();
})();
