/* ============================================================
   AdaptPy - admin: správa cvičení.
   Upload notebooku, úprava metadát, prepínače Publikované /
   Sprístupnené, poradie, mazanie, rescan priečinka.
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

  function itemRow(ex) {
    const stats = ex.stats || { completed: 0, in_progress: 0 };
    return `
      <div class="exadmin-item" data-id="${ex.id}">
        <div class="exadmin-item__ord">${ex.order_index}</div>
        <div class="exadmin-item__body">
          <div class="exadmin-item__title">${esc(ex.title_sk || ex.slug)}</div>
          <div class="exadmin-item__meta">
            ${esc(ex.filename)} · ${ex.code_cells} ${tr("exadmin.cells", "buniek")}
            · ✓ ${stats.completed} ${tr("exadmin.completedBy", "dokončili")}
          </div>
        </div>
        <div class="exadmin-item__flags">
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
            <button class="btn btn--secondary ex-edit">${tr("exadmin.edit", "Upraviť")}</button>
            <button class="btn btn--secondary ex-del">${tr("exadmin.delete", "Vymazať")}</button>
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
      if (r.ok && d.exercise) {
        items = items.map(x => x.id === id ? d.exercise : x);
        render();
      }
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

  // ---- upload ----
  const uploadBtn = document.getElementById("ex-upload-btn");
  const uploadMsg = document.getElementById("ex-upload-msg");
  function showMsg(text, isErr) {
    uploadMsg.style.display = "block";
    uploadMsg.className = isErr ? "error-message" : "info-message";
    uploadMsg.textContent = text;
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
    uploadBtn.disabled = true;
    try {
      const r = await fetch("/api/admin/exercises", { method: "POST", credentials: "include", body: fd });
      const d = await r.json();
      if (!r.ok) { showMsg(d.error || tr("exadmin.uploadErr", "Nahratie zlyhalo."), true); return; }
      showMsg(tr("exadmin.uploaded", "Cvičenie nahraté. Nezabudni ho publikovať a sprístupniť."), false);
      fileInput.value = "";
      document.getElementById("ex-title-sk").value = "";
      document.getElementById("ex-title-en").value = "";
      document.getElementById("ex-desc-sk").value = "";
      document.getElementById("ex-order").value = "";
      load();
    } catch (e) {
      showMsg(tr("exadmin.uploadErr", "Nahratie zlyhalo."), true);
    } finally {
      uploadBtn.disabled = false;
    }
  });

  // ---- rescan ----
  const rescanBtn = document.getElementById("ex-rescan");
  if (rescanBtn) rescanBtn.addEventListener("click", async () => {
    rescanBtn.disabled = true;
    try {
      const r = await fetch("/api/admin/exercises/rescan", { method: "POST", credentials: "include" });
      const d = await r.json();
      if (r.ok) { items = d.exercises || []; render(); }
    } catch (e) {} finally { rescanBtn.disabled = false; }
  });

  // ---- edit modal ----
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
      <label>${tr("exadmin.topics", "Témy / časti (každá na nový riadok)")}</label>
      <textarea id="edit-topics">${esc((ex.topics || []).join("\n"))}</textarea>
      <label>${tr("exadmin.replaceFile", "Nahradiť .ipynb (voliteľné)")}</label>
      <input type="file" id="edit-file" accept=".ipynb" />
      <button class="btn" id="edit-save">${tr("exadmin.save", "Uložiť")}</button>
    `;
    modal.style.display = "flex";
    document.getElementById("edit-save").addEventListener("click", async () => {
      const body = {
        title_sk: document.getElementById("edit-title-sk").value,
        title_en: document.getElementById("edit-title-en").value,
        description_sk: document.getElementById("edit-desc-sk").value,
        description_en: document.getElementById("edit-desc-en").value,
        order_index: document.getElementById("edit-order").value,
        topics: document.getElementById("edit-topics").value.split("\n").map(s => s.trim()).filter(Boolean),
      };
      await patch(id, body);
      const fileInput = document.getElementById("edit-file");
      if (fileInput.files.length) {
        const fd = new FormData();
        fd.append("file", fileInput.files[0]);
        try {
          await fetch(`/api/admin/exercises/${id}/file`, { method: "PUT", credentials: "include", body: fd });
        } catch (e) {}
        await load();
      }
      modal.style.display = "none";
    });
  }

  load();
})();
