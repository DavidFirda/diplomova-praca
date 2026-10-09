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

  // ---------- Zverejnenie dotazníka ----------
  const pubBtn = document.getElementById("publish-btn");
  const pubStatus = document.getElementById("publish-status");
  const pubHint = document.getElementById("publish-hint");
  let published = false;

  // Texty riadi data-i18n (I18N.apply() ich prepisuje pri zmene jazyka aj po načítaní sidebaru),
  // preto sa mení samotný kľúč, nie text.
  function renderPublish() {
    pubStatus.setAttribute("data-i18n", published ? "adminF.statusPublished" : "adminF.statusHidden");
    pubBtn.setAttribute("data-i18n", published ? "adminF.unpublish" : "adminF.publish");
    pubBtn.className = published ? "btn btn--secondary" : "btn";
    pubBtn.disabled = false;
    if (typeof I18N !== "undefined") I18N.apply();
  }

  async function loadPublish() {
    try {
      const r = await fetch("/api/admin/questionnaire", { credentials: "include" });
      if (r.ok) { published = !!(await r.json()).published; renderPublish(); }
    } catch (e) {}
  }

  pubBtn.addEventListener("click", async () => {
    pubBtn.disabled = true;
    pubHint.textContent = "";
    try {
      const r = await fetch("/api/admin/questionnaire", {
        method: "PUT", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ published: !published }),
      });
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        published = !!d.published;
        pubHint.textContent = published
          ? tr("adminF.nowPublished", "Dotazník je zverejnený.")
          : tr("adminF.nowHidden", "Dotazník je skrytý.");
        pubHint.className = "admin-hint admin-hint--ok";
      } else {
        pubHint.textContent = d.error || tr("adminF.error", "Chyba.");
        pubHint.className = "admin-hint admin-hint--err";
      }
    } catch (e) {
      pubHint.textContent = tr("adminF.error", "Chyba.");
      pubHint.className = "admin-hint admin-hint--err";
    }
    renderPublish();
  });

  // ---------- Správy z feedback formulára ----------
  const msgCard = document.getElementById("admin-msg-card");
  const CAT_LABEL = {
    bug: () => tr("ff.catBug", "Nahlásiť chybu"),
    idea: () => tr("ff.catIdea", "Nápad na zlepšenie"),
    praise: () => tr("ff.catPraise", "Pochvala"),
    other: () => tr("ff.catOther", "Iné"),
  };

  // Správy píšu používatelia -> NIKDY nevkladať ako HTML (XSS), len cez textContent.
  function renderMessages(messages) {
    msgCard.textContent = "";
    if (!messages.length) {
      const p = document.createElement("p");
      p.className = "admin-muted";
      p.textContent = tr("adminF.noMessages", "Zatiaľ žiadne správy.");
      msgCard.appendChild(p);
      return;
    }
    messages.forEach((m) => {
      const row = document.createElement("div");
      row.className = "admin-q";

      const main = document.createElement("div");
      main.className = "admin-q__main";
      const label = document.createElement("div");
      label.className = "admin-q__label";
      label.style.whiteSpace = "pre-wrap";
      label.textContent = m.message;
      const meta = document.createElement("div");
      meta.className = "admin-q__meta";
      const badge = document.createElement("span");
      badge.className = "admin-q__badge";
      badge.textContent = (CAT_LABEL[m.category] || CAT_LABEL.other)();
      const who = document.createElement("span");
      who.className = "admin-muted";
      const when = m.created_at ? new Date(m.created_at + (m.created_at.endsWith("Z") ? "" : "Z")).toLocaleString() : "";
      who.textContent = `${m.student.name || ""} (${m.student.login}) · ${when}`;
      meta.append(badge);
      if (m.rating) {
        const rt = document.createElement("span");
        rt.className = "admin-q__badge";
        rt.textContent = "★".repeat(m.rating) + "☆".repeat(5 - m.rating);
        rt.title = `${m.rating}/5`;
        meta.append(rt);
      }
      meta.append(who);
      main.append(label, meta);

      const actions = document.createElement("div");
      actions.className = "admin-q__actions";
      const del = document.createElement("button");
      del.className = "btn btn--danger-outline btn--sm";
      del.textContent = tr("adminF.delete", "Vymazať");
      del.addEventListener("click", async () => {
        if (!confirm(tr("adminF.confirmDelMsg", "Vymazať túto správu?"))) return;
        const r = await fetch(`/api/admin/feedback/messages/${m.id}`, { method: "DELETE", credentials: "include" });
        if (r.ok) loadMessages();
      });
      actions.appendChild(del);

      row.append(main, actions);
      msgCard.appendChild(row);
    });
  }

  async function loadMessages() {
    try {
      const r = await fetch("/api/admin/feedback/messages", { credentials: "include" });
      if (r.ok) renderMessages((await r.json()).messages || []);
    } catch (e) {}
  }

  (async function init() {
    if (!(await guardAdmin())) return;
    loadPublish();
    loadQuestions();
    loadMessages();
  })();
})();
