/* AdaptPy - Admin: správa otázok dotazníka (CRUD). */
(function () {
  const card = document.getElementById("admin-fb-card");
  const modal = document.getElementById("q-modal");
  let editingId = null;

  function tr(key, fb) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  }

  async function guardAdmin() {
    try {
      const r = await fetch("/api/admin/me", { credentials: "include" });
      const d = await r.json();
      if (!d.is_admin) { window.location.href = "/dashboard"; return false; }
      return true;
    } catch (e) { window.location.href = "/dashboard"; return false; }
  }

  async function loadQuestions() {
    const r = await fetch("/api/admin/feedback/questions", { credentials: "include" });
    if (!r.ok) { card.innerHTML = `<p class="admin-loading">${tr("adminF.error","Chyba.")}</p>`; return; }
    const { questions } = await r.json();
    renderQuestions(questions);
  }

  function renderQuestions(questions) {
    if (!questions.length) {
      card.innerHTML = `<p class="admin-muted" data-i18n="adminF.empty">Žiadne otázky. Pridaj prvú.</p>`;
      if (typeof I18N !== "undefined") I18N.apply();
      return;
    }
    const lang = (localStorage.getItem("adeptpy_lang") || "sk");
    const rows = questions.map((q, idx) => {
      const label = lang === "en" ? q.label_en : q.label_sk;
      const opts = (q.options && q.options.length) ? q.options.join(", ") : "—";
      return `
        <div class="admin-q" data-id="${q.id}">
          <div class="admin-q__main">
            <div class="admin-q__label">${idx + 1}. ${label}</div>
            <div class="admin-q__meta">
              <span class="admin-q__badge">${q.qtype}</span>
              <span class="admin-muted">${q.qkey}</span>
              ${q.required ? `<span class="admin-q__req" data-i18n="adminF.reqBadge">povinná</span>` : ""}
              ${!q.active ? `<span class="admin-q__inactive" data-i18n="adminF.inactive">skrytá</span>` : ""}
            </div>
            ${opts !== "—" ? `<div class="admin-q__opts">${opts}</div>` : ""}
          </div>
          <div class="admin-q__actions">
            <button class="admin-order-btn" data-up="${q.id}" ${idx === 0 ? "disabled" : ""} title="Hore">▲</button>
            <button class="admin-order-btn" data-down="${q.id}" ${idx === questions.length - 1 ? "disabled" : ""} title="Dole">▼</button>
            <button class="btn btn--secondary btn--sm" data-edit="${q.id}" data-i18n="adminF.edit">Upraviť</button>
            <button class="btn btn--danger-outline btn--sm" data-del="${q.id}" data-i18n="adminF.delete">Vymazať</button>
          </div>
        </div>
      `;
    }).join("");
    card.innerHTML = rows + `<p class="admin-hint" id="fb-hint"></p>`;
    if (typeof I18N !== "undefined") I18N.apply();
    window._adminQuestions = questions;
    attachHandlers(questions);
  }

  function attachHandlers(questions) {
    card.querySelectorAll("[data-edit]").forEach(b => b.addEventListener("click", () => openEdit(questions.find(q => q.id == b.getAttribute("data-edit")))));
    card.querySelectorAll("[data-del]").forEach(b => b.addEventListener("click", () => delQuestion(b.getAttribute("data-del"))));
    card.querySelectorAll("[data-up]").forEach(b => b.addEventListener("click", () => reorder(b.getAttribute("data-up"), -1, questions)));
    card.querySelectorAll("[data-down]").forEach(b => b.addEventListener("click", () => reorder(b.getAttribute("data-down"), 1, questions)));
  }

  async function reorder(qid, dir, questions) {
    const idx = questions.findIndex(q => q.id == qid);
    const swap = questions[idx + dir];
    if (!swap) return;
    const cur = questions[idx];
    // vymeň pozície
    await fetch(`/api/admin/feedback/questions/${cur.id}`, { method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ position: swap.position }) });
    await fetch(`/api/admin/feedback/questions/${swap.id}`, { method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ position: cur.position }) });
    loadQuestions();
  }

  async function delQuestion(qid) {
    if (!confirm(tr("adminF.confirmDel", "Vymazať túto otázku? Vymažú sa aj odpovede na ňu."))) return;
    const r = await fetch(`/api/admin/feedback/questions/${qid}`, { method: "DELETE", credentials: "include" });
    if (r.ok) loadQuestions();
  }

  // ---------- Modál ----------
  window.adminCloseQ = () => { modal.style.display = "none"; };
  const typeSelect = document.getElementById("q-type");
  const optionsField = document.getElementById("q-options-field");
  function toggleOptions() {
    optionsField.style.display = (typeSelect.value === "select") ? "flex" : "none";
  }
  typeSelect.addEventListener("change", toggleOptions);

  function openAdd() {
    editingId = null;
    document.getElementById("q-modal-title").textContent = tr("adminF.newQuestion", "Nová otázka");
    document.getElementById("q-key").value = "";
    document.getElementById("q-key").disabled = false;
    document.getElementById("q-label-sk").value = "";
    document.getElementById("q-label-en").value = "";
    document.getElementById("q-type").value = "select";
    document.getElementById("q-options").value = "";
    document.getElementById("q-required").checked = true;
    toggleOptions();
    modal.style.display = "flex";
  }

  function openEdit(q) {
    editingId = q.id;
    document.getElementById("q-modal-title").textContent = tr("adminF.editQuestion", "Upraviť otázku");
    document.getElementById("q-key").value = q.qkey;
    document.getElementById("q-key").disabled = true; // kľúč sa nemení
    document.getElementById("q-label-sk").value = q.label_sk;
    document.getElementById("q-label-en").value = q.label_en;
    document.getElementById("q-type").value = q.qtype;
    document.getElementById("q-options").value = (q.options || []).join("\n");
    document.getElementById("q-required").checked = q.required;
    toggleOptions();
    modal.style.display = "flex";
  }

  document.getElementById("add-question-btn").addEventListener("click", openAdd);

  document.getElementById("q-save-btn").addEventListener("click", async () => {
    const qkey = document.getElementById("q-key").value.trim();
    const label_sk = document.getElementById("q-label-sk").value.trim();
    const label_en = document.getElementById("q-label-en").value.trim();
    const qtype = document.getElementById("q-type").value;
    const required = document.getElementById("q-required").checked;
    const options = document.getElementById("q-options").value.split("\n").map(s => s.trim()).filter(Boolean);
    const hintEl = document.getElementById("q-hint");

    if (!label_sk || !label_en || (!editingId && !qkey)) {
      hintEl.textContent = tr("adminF.fillAll", "Vyplň kľúč a text (SK aj EN).");
      hintEl.className = "admin-hint admin-hint--err";
      return;
    }

    let r;
    if (editingId) {
      r = await fetch(`/api/admin/feedback/questions/${editingId}`, {
        method: "PATCH", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label_sk, label_en, qtype, options, required }),
      });
    } else {
      r = await fetch(`/api/admin/feedback/questions`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ qkey, label_sk, label_en, qtype, options, required }),
      });
    }
    if (r.ok) { modal.style.display = "none"; loadQuestions(); }
    else {
      const d = await r.json();
      hintEl.textContent = d.error || tr("adminF.error", "Chyba.");
      hintEl.className = "admin-hint admin-hint--err";
    }
  });

  (async function init() {
    if (!(await guardAdmin())) return;
    loadQuestions();
  })();
})();
