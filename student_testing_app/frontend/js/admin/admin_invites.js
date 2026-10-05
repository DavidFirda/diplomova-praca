/* ============================================================
   AdaptPy - Admin: POZVÁNKY používateľov (logika)
   HTML kostra karty a modálu je v pages/admin_users.html,
   štýly v css/parts/10-invites.css - tu je iba logika a vykreslenie
   riadkov tabuľky / výsledkov.
   ============================================================ */
(function () {
  const card = document.getElementById("admin-invites-card");
  if (!card) return;

  const $ = id => document.getElementById(id);
  const modal = $("inv-modal");

  function tr(key, fb) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  }
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = iso => { if (!iso) return "–"; const d = new Date(iso + (iso.endsWith("Z") ? "" : "Z")); return isNaN(d) ? "–" : d.toLocaleDateString(); };

  let data = { invitations: [], stats: {}, mode: "invite" };

  // ---------- načítanie + vykreslenie ----------
  async function load() {
    try {
      const r = await fetch("/api/admin/invitations", { credentials: "include" });
      if (!r.ok) { $("inv-table-wrap").innerHTML = `<p class="admin-loading">${tr("adminU.error", "Chyba načítania.")}</p>`; return; }
      data = await r.json();
      render();
    } catch (e) { $("inv-table-wrap").innerHTML = `<p class="admin-loading">${tr("adminU.error", "Chyba načítania.")}</p>`; }
  }

  function statusLabel(s) {
    return s === "registered" ? tr("inv.registered", "Zaregistrovaný")
         : s === "expired" ? tr("inv.expired", "Vypršalo")
         : tr("inv.pending", "Čaká na registráciu");
  }

  function render() {
    const s = data.stats || {};
    $("inv-stat-total").textContent = s.total || 0;
    $("inv-stat-pending").textContent = s.pending || 0;
    $("inv-stat-registered").textContent = s.registered || 0;
    $("inv-stat-expired").textContent = s.expired || 0;
    $("inv-mode").textContent = data.mode === "open"
      ? tr("inv.modeOpen", "Režim registrácie: voľná (každý sa môže zaregistrovať).")
      : tr("inv.modeInvite", "Režim registrácie: len na pozvánku.");

    const wrap = $("inv-table-wrap");
    if (!data.invitations.length) {
      wrap.innerHTML = `<p class="admin-muted">${tr("inv.empty", "Zatiaľ žiadne pozvánky.")}</p>`;
      return;
    }
    const rows = data.invitations.map(i => `
      <tr>
        <td><strong>${esc(i.email)}</strong>${(i.name || i.surname) ? `<br><span class="admin-muted">${esc((i.name + " " + i.surname).trim())}</span>` : ""}</td>
        <td class="admin-hide-sm">${esc(i.group)}</td>
        <td><span class="inv-badge inv-badge--${esc(i.status)}">${statusLabel(i.status)}</span></td>
        <td class="admin-hide-sm">${i.status === "registered" ? fmt(i.used_at) : fmt(i.expires_at)}</td>
        <td>
          <div class="admin-actions">
            ${i.status !== "registered" ? `<button class="btn btn--secondary btn--sm" data-resend="${i.id}">${tr("inv.resend", "Nový odkaz / poslať znova")}</button>` : ""}
            <button class="btn btn--danger-outline btn--sm" data-del="${i.id}" data-email="${esc(i.email)}">${tr("adminU.delete", "Vymazať")}</button>
          </div>
        </td>
      </tr>`).join("");

    wrap.innerHTML = `
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead><tr>
            <th>${tr("adminU.email", "Email")}</th>
            <th class="admin-hide-sm">${tr("inv.group", "Skupina")}</th>
            <th>${tr("inv.status", "Stav")}</th>
            <th class="admin-hide-sm">${tr("inv.until", "Platí do / registrácia")}</th>
            <th>${tr("adminU.actions", "Akcie")}</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
    wrap.querySelectorAll("[data-resend]").forEach(b => b.addEventListener("click", () => resend(b.dataset.resend)));
    wrap.querySelectorAll("[data-del]").forEach(b => b.addEventListener("click", () => del(b.dataset.del, b.dataset.email)));
  }

  function hint(msg, ok) {
    const el = $("inv-hint");
    el.textContent = msg;
    el.className = "admin-hint " + (ok ? "admin-hint--ok" : "admin-hint--err");
    setTimeout(() => { el.textContent = ""; el.className = "admin-hint"; }, 4000);
  }

  async function copy(text) {
    try { await navigator.clipboard.writeText(text); return true; }
    catch (e) {
      const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta);
      ta.select(); let ok = false; try { ok = document.execCommand("copy"); } catch (x) {}
      ta.remove(); return ok;
    }
  }
  function flash(btn) { const o = btn.textContent; btn.textContent = "✓"; setTimeout(() => { btn.textContent = o; }, 1200); }

  // ---------- akcie v tabuľke ----------
  async function resend(id) {
    const mail = confirm(tr("inv.confirmMail", "Poslať aj e-mail? (OK = poslať e-mail, Zrušiť = len vygenerovať odkaz)"));
    const r = await fetch(`/api/admin/invitations/${id}/resend`, {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ send_email: mail }),
    });
    const d = await r.json();
    if (!r.ok) { hint(d.error || tr("adminU.error", "Chyba."), false); return; }
    await copy(d.link);
    await load();
    hint(tr("inv.linkCopied", "Nový odkaz bol skopírovaný do schránky.") + (mail ? " " + tr("inv.mailSent", "E-mail bol odoslaný.") : ""), true);
  }

  async function del(id, email) {
    if (!confirm(tr("inv.confirmDel", "Zrušiť pozvánku pre") + ` ${email}?`)) return;
    const r = await fetch(`/api/admin/invitations/${id}`, { method: "DELETE", credentials: "include" });
    if (r.ok) load(); else hint(tr("adminU.error", "Chyba."), false);
  }

  // ---------- modál ----------
  function openAdd() {
    $("inv-result").innerHTML = "";
    modal.style.display = "flex";
    $("inv-emails").focus();
  }
  function closeAdd() { modal.style.display = "none"; load(); }

  const RES = {
    created: ["inv.rCreated", "Vytvorená"], renewed: ["inv.rRenewed", "Obnovená"],
    already_registered: ["inv.rExisting", "Už má účet"], invalid: ["inv.rInvalid", "Neplatný e-mail"],
  };

  async function submit() {
    const btn = $("inv-submit");
    const out = $("inv-result");
    const emails = $("inv-emails").value;
    if (!emails.trim()) { out.innerHTML = `<p class="error-message" style="display:block">${tr("inv.needEmail", "Zadaj aspoň jeden e-mail.")}</p>`; return; }
    btn.disabled = true;
    try {
      const r = await fetch("/api/admin/invitations", {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          emails,
          group: $("inv-group").value,
          expires_days: $("inv-days").value,
          send_email: $("inv-mail").checked,
        }),
      });
      const d = await r.json();
      if (!r.ok) { out.innerHTML = `<p class="error-message" style="display:block">${esc(d.error || tr("adminU.error", "Chyba."))}</p>`; return; }

      const links = d.results.filter(x => x.link).map(x => `${x.email}\t${x.link}`).join("\n");
      out.innerHTML = `
        <div class="inv-res"><table><tbody>
          ${d.results.map(x => `<tr>
            <td>${esc(x.email)}</td>
            <td>${tr(RES[x.result][0], RES[x.result][1])}${x.mailed ? " ✉" : ""}</td>
            <td>${x.link ? `<div class="inv-link" title="${esc(x.link)}">${esc(x.link)}</div>` : ""}</td>
            <td>${x.link ? `<button class="btn btn--secondary btn--sm" data-copy="${esc(x.link)}">${tr("inv.copy", "Kopírovať")}</button>` : ""}</td>
          </tr>`).join("")}
        </tbody></table></div>
        ${links ? `<button class="btn btn--secondary btn--sm inv-copyall" id="inv-copyall">${tr("inv.copyAll", "Kopírovať všetky odkazy")}</button>` : ""}
        <div class="inv-note">${tr("inv.linksOnce", "Odkazy sa zobrazia len teraz – neskôr ich dostaneš cez „Nový odkaz“.")}</div>`;
      out.querySelectorAll("[data-copy]").forEach(b => b.addEventListener("click", async () => { if (await copy(b.dataset.copy)) flash(b); }));
      const all = $("inv-copyall");
      if (all) all.addEventListener("click", async () => { if (await copy(links)) flash(all); });
      $("inv-emails").value = "";
    } catch (e) {
      out.innerHTML = `<p class="error-message" style="display:block">${tr("msg.serverError", "Chyba pripojenia k serveru.")}</p>`;
    } finally { btn.disabled = false; }
  }

  $("inv-add").addEventListener("click", openAdd);
  $("inv-close").addEventListener("click", closeAdd);
  $("inv-cancel").addEventListener("click", closeAdd);
  $("inv-backdrop").addEventListener("click", closeAdd);
  $("inv-submit").addEventListener("click", submit);

  (async function init() {
    // len pre admina (admin_users.js stránku aj tak stráži)
    try {
      const r = await fetch("/api/admin/me", { credentials: "include" });
      const d = await r.json();
      if (!d.is_admin) return;
    } catch (e) { return; }
    load();
  })();
})();
