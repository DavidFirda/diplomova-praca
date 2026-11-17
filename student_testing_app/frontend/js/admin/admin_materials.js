/* ============================================================
   AdaptPy - Admin: materiály kurzu (prednášky, knihy) pre RAG asistenta.
   - nahratie súborov (pptx, pdf, ipynb, py, md, txt, zip) -> indexovanie na pozadí
   - úprava názvu, čísla prednášky, váhy; zapnutie v asistentovi; sprístupnenie študentom
   - reindexovanie, zmazanie, stiahnutie
   - test vyhľadávania: čo by RAG k otázke našiel (rovnako ako ask.py v rag_asistent)
   ============================================================ */
(function () {
  const root = document.getElementById("mat-admin");
  const tr = (key, fb) => {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (m) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
  const size = (b) => b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} kB`;
  const STATUS = {
    pending: ["ai-badge--info", "čaká"], indexing: ["ai-badge--warn", "indexujem…"],
    ready: ["ai-badge--ok", "pripravené"], error: ["ai-badge--err", "chyba"],
  };
  let pollTimer = null;

  async function api(path, opts) {
    const r = await fetch(`/api/admin/materials${path}`, { credentials: "include", ...(opts || {}) });
    if (r.status === 401) { location.href = "/login"; throw new Error("401"); }
    if (r.status === 403) { location.href = "/dashboard"; throw new Error("403"); }
    let d = {};
    try { d = await r.json(); } catch (e) { /* prázdne */ }
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
    return d;
  }

  function layout() {
    root.innerHTML = `
      <div class="ai-admin-card">
        <h3>${tr("aiM.upload", "Nahrať materiály")}</h3>
        <form class="mat-upload" id="mat-form">
          <input type="file" id="mat-files" multiple>
          <select id="mat-kind">
            <option value="prednaska">${tr("mat.lecture", "Prednáška")}</option>
            <option value="kniha">${tr("mat.book", "Kniha")}</option>
          </select>
          <label class="inline"><input type="checkbox" id="mat-visible"> ${tr("aiM.visibleNew", "sprístupniť študentom")}</label>
          <button type="submit" class="btn-sm">${tr("aiM.uploadBtn", "Nahrať a zaindexovať")}</button>
          <span class="ai-muted" id="mat-upload-msg"></span>
        </form>
        <p class="ai-muted" id="mat-upload-note"></p>
      </div>
      <div class="ai-admin-card">
        <h3>${tr("aiM.list", "Materiály")} <span class="ai-muted" id="mat-index-info"></span></h3>
        <div class="ai-filters">
          <button type="button" class="btn--secondary" id="mat-reindex-all">${tr("aiM.reindexAll", "Reindexovať všetko")}</button>
          <span class="ai-muted">${tr("aiM.weightNote", "Váha: prednášky 1,0 a knihy 0,6 (knihy majú veľa kúskov a sú po anglicky, bez nižšej váhy by vytlačili slajdy).")}</span>
        </div>
        <div class="ai-table-wrap" id="mat-table"></div>
      </div>
      <div class="ai-admin-card">
        <h3>${tr("aiM.searchTest", "Test vyhľadávania (RAG)")}</h3>
        <div class="ai-filters">
          <input type="search" id="mat-q" style="flex:1;min-width:240px" placeholder="${esc(tr("aiM.searchPh", "napr. ako funguje dedenie"))}">
          <select id="mat-k">${[3, 5, 8].map((k) => `<option value="${k}" ${k === 5 ? "selected" : ""}>k = ${k}</option>`).join("")}</select>
          <button type="button" id="mat-search">${tr("aiM.searchBtn", "Hľadať")}</button>
        </div>
        <div id="mat-search-out"></div>
      </div>`;

    document.getElementById("mat-form").addEventListener("submit", upload);
    document.getElementById("mat-reindex-all").addEventListener("click", async () => {
      if (!confirm(tr("aiM.reindexConfirm", "Prepočítať index všetkých materiálov? Pri knihách to môže trvať niekoľko minút."))) return;
      try { await api("/reindex-all", { method: "POST" }); load(); } catch (e) { alert(e.message); }
    });
    document.getElementById("mat-search").addEventListener("click", searchTest);
    document.getElementById("mat-q").addEventListener("keydown", (e) => { if (e.key === "Enter") searchTest(); });
  }

  async function upload(e) {
    e.preventDefault();
    const files = document.getElementById("mat-files").files;
    const msg = document.getElementById("mat-upload-msg");
    if (!files.length) { msg.textContent = tr("aiM.noFile", "Vyber súbory."); return; }
    const fd = new FormData();
    [...files].forEach((f) => fd.append("files", f));
    fd.append("kind", document.getElementById("mat-kind").value);
    fd.append("visible_to_students", document.getElementById("mat-visible").checked ? "true" : "false");
    msg.textContent = tr("aiM.uploading", "Nahrávam…");
    try {
      const d = await api("", { method: "POST", body: fd });
      const skipped = d.skipped.map((s) => `${s.name} (${{ duplicate: tr("aiM.dup", "už existuje"), unsupported: tr("aiM.unsupported", "nepodporovaný typ"), too_large: tr("aiM.tooLarge", "príliš veľký") }[s.reason] || s.reason})`);
      msg.textContent = `✓ ${d.created.length} ${tr("aiM.uploaded", "nahraných")}` + (skipped.length ? ` · ${tr("aiM.skipped", "preskočené")}: ${skipped.join(", ")}` : "");
      document.getElementById("mat-files").value = "";
      load();
    } catch (err) { msg.textContent = err.message; }
  }

  async function load() {
    let d;
    try { d = await api(""); } catch (e) { document.getElementById("mat-table").innerHTML = `<p>${esc(e.message)}</p>`; return; }
    document.getElementById("mat-upload-note").textContent =
      `${tr("aiM.formats", "Podporované")}: ${d.upload_exts.join(", ")} · max ${d.max_upload_mb} MB · ${tr("aiM.zipNote", "zip = napr. kódy z prednášky")}`;
    const i = d.index;
    document.getElementById("mat-index-info").textContent =
      `· ${i.materials_in_assistant} ${tr("aiM.inAssistant", "v asistentovi")}, ${i.chunks_in_assistant} ${tr("aiM.chunks", "kúskov")}, embedding ${i.embed_model}` +
      (i.outdated_embeddings ? ` · ⚠ ${i.outdated_embeddings} ${tr("aiM.outdated", "s iným embedding modelom – reindexuj")}` : "");
    render(d.materials);
    const busy = d.materials.some((m) => m.status === "pending" || m.status === "indexing");
    clearTimeout(pollTimer);
    if (busy) pollTimer = setTimeout(load, 3000);
  }

  function render(list) {
    const el = document.getElementById("mat-table");
    if (!list.length) { el.innerHTML = `<p class="ai-muted">${tr("aiM.empty", "Zatiaľ žiadne materiály. Nahraj prednášky (pptx) a knihy (pdf).")}</p>`; return; }
    el.innerHTML = `<table class="ai-table">
      <thead><tr>
        <th>${tr("aiM.colTitle", "Názov")}</th><th>${tr("aiM.colType", "Typ")}</th><th>${tr("aiM.colNo", "Č. prednášky")}</th>
        <th>${tr("aiM.colWeight", "Váha")}</th><th>${tr("aiM.colStatus", "Stav")}</th>
        <th>${tr("aiM.colAssistant", "Asistent")}</th><th>${tr("aiM.colStudents", "Študenti")}</th><th></th>
      </tr></thead>
      <tbody>${list.map((m) => {
        const [cls, label] = STATUS[m.status] || ["", m.status];
        return `<tr data-id="${m.id}">
          <td><input class="mat-admin-title" data-f="title" value="${esc(m.title)}">
            <div class="ai-muted">${esc(m.original_name)} · ${size(m.size_bytes)}</div></td>
          <td><select data-f="kind" class="mat-admin-num" style="width:auto">
            <option value="prednaska" ${m.kind === "prednaska" ? "selected" : ""}>${tr("mat.lecture", "Prednáška")}</option>
            <option value="kniha" ${m.kind === "kniha" ? "selected" : ""}>${tr("mat.book", "Kniha")}</option></select></td>
          <td><input class="mat-admin-num" data-f="lecture_no" type="number" min="0" value="${m.lecture_no ?? ""}" ${m.kind === "kniha" ? "disabled" : ""}></td>
          <td><input class="mat-admin-num" data-f="weight" type="number" step="0.1" min="0" max="3" placeholder="${m.default_weight}" value="${m.weight ?? ""}"></td>
          <td><span class="ai-badge ${cls}">${tr("aiM.status." + m.status, label)}</span>
            ${m.status === "ready" ? `<div class="ai-muted">${m.chunks} ${tr("aiM.chunks", "kúskov")}</div>` : ""}
            ${m.error ? `<div class="ai-muted" style="color:var(--danger)" title="${esc(m.error)}">${esc(m.error.slice(0, 80))}</div>` : ""}</td>
          <td><input type="checkbox" class="ai-toggle" data-f="use_in_assistant" ${m.use_in_assistant ? "checked" : ""}></td>
          <td><input type="checkbox" class="ai-toggle" data-f="visible_to_students" ${m.visible_to_students ? "checked" : ""}></td>
          <td><div class="ai-actions">
            <a class="btn btn--secondary btn--sm" href="/api/admin/materials/${m.id}/download">${tr("aiM.download", "Stiahnuť")}</a>
            <button type="button" data-act="reindex" class="btn--secondary">${tr("aiM.reindex", "Reindex")}</button>
            <button type="button" data-act="delete" class="danger">${tr("aiM.delete", "Zmazať")}</button>
          </div></td>
        </tr>`;
      }).join("")}</tbody></table>`;

    el.querySelectorAll("tr[data-id]").forEach((row) => {
      const id = row.dataset.id;
      row.querySelectorAll("[data-f]").forEach((inp) => {
        inp.addEventListener("change", async () => {
          const f = inp.dataset.f;
          const value = inp.type === "checkbox" ? inp.checked : inp.value;
          try {
            await api(`/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify({ [f]: value }) });
            if (f === "kind" || f === "title") load();
          } catch (e) { alert(e.message); load(); }
        });
      });
      row.querySelector('[data-act="reindex"]').addEventListener("click", async () => {
        try { await api(`/${id}/reindex`, { method: "POST" }); load(); } catch (e) { alert(e.message); }
      });
      row.querySelector('[data-act="delete"]').addEventListener("click", async () => {
        if (!confirm(tr("aiM.deleteConfirm", "Zmazať materiál aj jeho index? Súbor sa natrvalo odstráni zo servera."))) return;
        try { await api(`/${id}`, { method: "DELETE" }); load(); } catch (e) { alert(e.message); }
      });
    });
  }

  async function searchTest() {
    const q = document.getElementById("mat-q").value.trim();
    const out = document.getElementById("mat-search-out");
    if (!q) return;
    out.innerHTML = `<p class="ai-muted">${tr("aiA.loading", "Načítavam…")}</p>`;
    try {
      const d = await api("/search-test", { method: "POST", headers: { "Content-Type": "application/json" },
                                            body: JSON.stringify({ question: q, k: Number(document.getElementById("mat-k").value) }) });
      const info = d.info;
      out.innerHTML = `<p class="ai-muted">${tr("aiM.indexSize", "Kúskov v indexe")}: ${info.chunks_total} · ${info.vectors ? tr("aiA.vectorsBm25", "vektory + BM25") : "BM25"}${info.error ? ` · ⚠ ${esc(info.error)}` : ""}</p>
        <div class="ai-search-results">${d.results.map((r) => `
          <div class="item"><strong>[${r.rank}] ${esc(r.label)}</strong>
            <span class="ai-muted">· ${tr("aiA.score", "skóre")} ${r.score} · ${esc(Object.entries(r.signals || {}).map(([k, v]) => `${k} #${v}`).join(", "))}</span>
            <pre>${esc(r.text)}</pre></div>`).join("") || `<p class="ai-muted">${tr("aiM.noResults", "Nič sa nenašlo.")}</p>`}</div>`;
    } catch (e) { out.innerHTML = `<p>${esc(e.message)}</p>`; }
  }

  layout();
  load();
})();
