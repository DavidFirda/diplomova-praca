/* AdaptPy - Admin: správa používateľov (role, testy, predtesty). */
(function () {
  const card = document.getElementById("admin-users-card");

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

  async function loadUsers() {
    const r = await fetch("/api/admin/users", { credentials: "include" });
    if (!r.ok) { card.innerHTML = `<p class="admin-loading">${tr("adminU.error","Chyba načítania.")}</p>`; return; }
    const { users } = await r.json();
    renderUsers(users);
  }

  function renderUsers(users) {
    const rows = users.map(u => `
      <tr>
        <td>${u.id}</td>
        <td><strong>${u.name} ${u.surname}</strong><br><span class="admin-muted">${u.login}</span></td>
        <td class="admin-hide-sm">${u.email}</td>
        <td>
          <select class="admin-role-select" data-user="${u.id}">
            <option value="user" ${u.role === "user" ? "selected" : ""}>${tr("role.user","Používateľ")}</option>
            <option value="admin" ${u.role === "admin" ? "selected" : ""}>${tr("role.admin","Administrátor")}</option>
          </select>
        </td>
        <td class="admin-hide-sm">${u.pretest_answers > 0 ? "✓" : "–"}</td>
        <td class="admin-hide-sm">${u.main_tests}</td>
        <td>
          <div class="admin-actions">
            <a class="btn btn--secondary btn--sm" href="/admin-user-exercises?uid=${u.id}" data-i18n="adminU.exercises">${tr("adminU.exercises","Cvičenia")}</a>
            <button class="btn btn--secondary btn--sm" data-i18n="adminU.tests" data-tests="${u.id}" data-name="${u.name} ${u.surname}">${tr("adminU.tests","Testy")}</button>
            <button class="btn btn--danger-outline btn--sm" data-i18n="adminU.delete" data-del="${u.id}" data-name="${u.name} ${u.surname}">${tr("adminU.delete","Vymazať")}</button>
          </div>
        </td>
      </tr>
    `).join("");

    card.innerHTML = `
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>ID</th>
              <th data-i18n="adminU.user">Používateľ</th>
              <th class="admin-hide-sm" data-i18n="adminU.email">Email</th>
              <th data-i18n="adminU.role">Rola</th>
              <th class="admin-hide-sm" data-i18n="adminU.pretest">Predtest</th>
              <th class="admin-hide-sm" data-i18n="adminU.mainTests">Testy</th>
              <th data-i18n="adminU.actions">Akcie</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <p class="admin-hint" id="admin-hint"></p>
    `;
    if (typeof I18N !== "undefined") I18N.apply();
    attachHandlers();
  }

  function hint(msg, ok) {
    const el = document.getElementById("admin-hint");
    if (!el) return;
    el.textContent = msg;
    el.className = "admin-hint " + (ok ? "admin-hint--ok" : "admin-hint--err");
    setTimeout(() => { el.textContent = ""; el.className = "admin-hint"; }, 3000);
  }

  function attachHandlers() {
    // zmena roly
    card.querySelectorAll(".admin-role-select").forEach(sel => {
      sel.addEventListener("change", async () => {
        const uid = sel.getAttribute("data-user");
        const r = await fetch(`/api/admin/users/${uid}/role`, {
          method: "PATCH", credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ role: sel.value }),
        });
        hint(r.ok ? tr("adminU.roleSaved","Rola uložená.") : tr("adminU.error","Chyba."), r.ok);
      });
    });
    // detail testov
    card.querySelectorAll("[data-tests]").forEach(btn => {
      btn.addEventListener("click", () => openTests(btn.getAttribute("data-tests"), btn.getAttribute("data-name")));
    });
    // vymazať usera
    card.querySelectorAll("[data-del]").forEach(btn => {
      btn.addEventListener("click", async () => {
        const uid = btn.getAttribute("data-del");
        const name = btn.getAttribute("data-name");
        if (!confirm(tr("adminU.confirmDelUser", "Naozaj vymazať používateľa") + ` "${name}"? ` + tr("adminU.irreversible","Táto akcia je nezvratná."))) return;
        const r = await fetch(`/api/admin/users/${uid}`, { method: "DELETE", credentials: "include" });
        if (r.ok) loadUsers(); else hint(tr("adminU.error","Chyba."), false);
      });
    });
  }

  // ---------- Modál s testami ----------
  const modal = document.getElementById("tests-modal");
  const modalBody = document.getElementById("tests-modal-body");
  window.adminCloseTests = () => { modal.style.display = "none"; };

  async function openTests(uid, name) {
    document.getElementById("tests-modal-title").textContent =
      tr("adminU.testsOf", "Testy používateľa") + ": " + name;
    modalBody.innerHTML = `<p class="admin-loading">${tr("adminU.loading","Načítavam…")}</p>`;
    modal.style.display = "flex";
    const r = await fetch(`/api/admin/users/${uid}/tests`, { credentials: "include" });
    if (!r.ok) { modalBody.innerHTML = `<p>${tr("adminU.error","Chyba.")}</p>`; return; }
    const data = await r.json();
    renderTests(uid, data);
  }

  function answerRow(a) {
    return `
      <div class="admin-answer" data-answer="${a.id}">
        <div class="admin-answer__head">
          <span class="admin-muted">Q#${a.question_id} · ${a.category}</span>
          <label class="admin-check">
            <input type="checkbox" ${a.is_correct ? "checked" : ""} data-correct="${a.id}">
            <span data-i18n="adminU.correct">Správne</span>
          </label>
        </div>
        <textarea class="admin-answer__code" data-code="${a.id}" rows="3">${(a.answer_code || "").replace(/</g,"&lt;")}</textarea>
        <div class="admin-answer__actions">
          <button class="btn btn--secondary btn--sm" data-save-answer="${a.id}" data-i18n="adminU.saveAnswer">Uložiť</button>
          <button class="btn btn--danger-outline btn--sm" data-del-answer="${a.id}" data-i18n="adminU.delAnswer">Vymazať odpoveď</button>
        </div>
      </div>
    `;
  }

  function renderTests(uid, data) {
    let html = "";

    // Predtest
    html += `<div class="admin-test-section">
      <div class="admin-test-section__head">
        <h3 data-i18n="adminU.pretestSection">Predtest</h3>
        ${data.pretest.length ? `<button class="btn btn--danger-outline btn--sm" id="del-pretest" data-i18n="adminU.delPretest">Vymazať celý predtest</button>` : ""}
      </div>`;
    html += data.pretest.length ? data.pretest.map(answerRow).join("") : `<p class="admin-muted" data-i18n="adminU.noPretest">Žiadny predtest.</p>`;
    html += `</div>`;

    // Hlavné testy
    html += `<div class="admin-test-section"><h3 data-i18n="adminU.mainSection">Hlavné testy</h3>`;
    if (data.main_tests.length) {
      data.main_tests.forEach(t => {
        html += `<div class="admin-session">
          <div class="admin-session__head">
            <span class="admin-muted">Session: ${t.test_session}</span>
            <button class="btn btn--danger-outline btn--sm" data-del-session="${t.test_session}" data-i18n="adminU.delTest">Vymazať test</button>
          </div>
          ${t.answers.map(answerRow).join("")}
        </div>`;
      });
    } else {
      html += `<p class="admin-muted" data-i18n="adminU.noMain">Žiadne hlavné testy.</p>`;
    }
    html += `</div>`;

    modalBody.innerHTML = html;
    if (typeof I18N !== "undefined") I18N.apply();
    attachTestHandlers(uid);
  }

  function attachTestHandlers(uid) {
    // uložiť odpoveď
    modalBody.querySelectorAll("[data-save-answer]").forEach(btn => {
      btn.addEventListener("click", async () => {
        const aid = btn.getAttribute("data-save-answer");
        const code = modalBody.querySelector(`[data-code="${aid}"]`).value;
        const correct = modalBody.querySelector(`[data-correct="${aid}"]`).checked;
        const r = await fetch(`/api/admin/answers/${aid}`, {
          method: "PATCH", credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answer_code: code, is_correct: correct }),
        });
        btn.textContent = r.ok ? "✓" : "✕";
        setTimeout(() => { btn.textContent = tr("adminU.saveAnswer","Uložiť"); }, 1500);
      });
    });
    // vymazať odpoveď
    modalBody.querySelectorAll("[data-del-answer]").forEach(btn => {
      btn.addEventListener("click", async () => {
        const aid = btn.getAttribute("data-del-answer");
        if (!confirm(tr("adminU.confirmDelAnswer","Vymazať túto odpoveď?"))) return;
        const r = await fetch(`/api/admin/answers/${aid}`, { method: "DELETE", credentials: "include" });
        if (r.ok) { const el = modalBody.querySelector(`[data-answer="${aid}"]`); if (el) el.remove(); }
      });
    });
    // vymazať predtest
    const delPre = document.getElementById("del-pretest");
    if (delPre) delPre.addEventListener("click", async () => {
      if (!confirm(tr("adminU.confirmDelPretest","Vymazať celý predtest tohto používateľa?"))) return;
      const r = await fetch(`/api/admin/users/${uid}/pretest`, { method: "DELETE", credentials: "include" });
      if (r.ok) openTests(uid, document.getElementById("tests-modal-title").textContent.split(": ")[1] || "");
    });
    // vymazať test (session)
    modalBody.querySelectorAll("[data-del-session]").forEach(btn => {
      btn.addEventListener("click", async () => {
        const sess = btn.getAttribute("data-del-session");
        if (!confirm(tr("adminU.confirmDelTest","Vymazať tento test?"))) return;
        const r = await fetch(`/api/admin/users/${uid}/tests/${encodeURIComponent(sess)}`, { method: "DELETE", credentials: "include" });
        if (r.ok) openTests(uid, document.getElementById("tests-modal-title").textContent.split(": ")[1] || "");
      });
    });
  }

  (async function init() {
    if (!(await guardAdmin())) return;
    loadUsers();
  })();
})();
