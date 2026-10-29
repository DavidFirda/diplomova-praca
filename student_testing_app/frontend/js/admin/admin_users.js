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
    const dash = '<span class="admin-muted">–</span>';
    const rows = users.map(u => {
      const flags = (u.flags_ulohy || 0) + (u.flags_tests || 0) + (u.flags_exercises || 0);
      return `
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
        <td class="admin-hide-sm admin-center" title="${u.pretest_answers}/${u.pretest_total}">${u.pretest_done ? "✓" : (u.pretest_answers > 0 ? `${u.pretest_answers}/${u.pretest_total}` : "–")}</td>
        <td class="admin-hide-sm admin-center" title="${tr("adminU.exercisesTitle", "dokončené / publikované")}">${u.exercises_total ? `${u.exercises_done || 0}/${u.exercises_total}` : "–"}</td>
        <td class="admin-hide-sm admin-center" title="${tr("adminU.ulohyTitle", "vyriešené / dokončené")}">${u.ulohy_solved || 0}/${u.ulohy_total || 0}</td>
        <td class="admin-hide-sm admin-center">${u.main_tests}</td>
        <td class="admin-center" title="${tr("orig.flagsTitle", "Aktívne red flagy (cvičenia / úlohy / testy)")}">${
          flags ? `<span class="orig-chip">${u.flags_exercises || 0} / ${u.flags_ulohy || 0} / ${u.flags_tests || 0}</span>` : dash}</td>
        <td>
          <div class="admin-actions">
            <a class="btn btn--secondary btn--sm" href="/admin-user-exercises?uid=${u.id}" data-i18n="adminU.exercises">${tr("adminU.exercises","Cvičenia")}</a>
            <a class="btn btn--secondary btn--sm" href="/admin-user-ulohy?uid=${u.id}" data-i18n="adminU.ulohy">${tr("adminU.ulohy","Úlohy")}</a>
            <a class="btn btn--secondary btn--sm" href="/admin-user-tests?uid=${u.id}" data-i18n="adminU.tests" title="${tr("adminU.testsHint", "Predtest a hlavné testy")}">${tr("adminU.tests","Testy")}</a>
            <button class="btn btn--danger-outline btn--sm" data-i18n="adminU.delete" data-del="${u.id}" data-name="${u.name} ${u.surname}">${tr("adminU.delete","Vymazať")}</button>
          </div>
        </td>
      </tr>`;
    }).join("");

    card.innerHTML = `
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>ID</th>
              <th data-i18n="adminU.user">Používateľ</th>
              <th class="admin-hide-sm" data-i18n="adminU.email">Email</th>
              <th data-i18n="adminU.role">Rola</th>
              <th class="admin-hide-sm admin-center" data-i18n="adminU.pretest">Predtest</th>
              <th class="admin-hide-sm admin-center" data-i18n="adminU.exercises">Cvičenia</th>
              <th class="admin-hide-sm admin-center" data-i18n="adminU.ulohyCol">Úlohy</th>
              <th class="admin-hide-sm admin-center" data-i18n="adminU.mainTests">Testy</th>
              <th class="admin-center" data-i18n="orig.flagsCol">Red flagy</th>
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

  (async function init() {
    if (!(await guardAdmin())) return;
    loadUsers();
  })();
})();
