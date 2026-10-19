/* AdaptPy - Admin: dostupnosť sekcií pre študentov (zatiaľ Testy).
   Vypnutá sekcia zmizne študentom z dashboardu, menu aj API; admin ju vidí stále. */
(function () {
  const btn = document.getElementById("sec-tests-btn");
  const status = document.getElementById("sec-tests-status");
  const hint = document.getElementById("sec-tests-hint");
  if (!btn) return;

  let enabled = true;

  function tr(key, fb) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  }

  // Texty riadi data-i18n (I18N.apply() ich prepisuje pri zmene jazyka), preto sa mení kľúč.
  function render() {
    status.setAttribute("data-i18n", enabled ? "adminS.statusOn" : "adminS.statusOff");
    btn.setAttribute("data-i18n", enabled ? "adminS.disable" : "adminS.enable");
    btn.className = enabled ? "btn btn--secondary" : "btn";
    btn.disabled = false;
    if (typeof I18N !== "undefined") I18N.apply();
  }

  async function load() {
    try {
      const r = await fetch("/api/admin/sections", { credentials: "include" });
      if (r.ok) { enabled = !!(await r.json()).tests; render(); }
    } catch (e) {}
  }

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    hint.textContent = "";
    try {
      const r = await fetch("/api/admin/sections", {
        method: "PUT", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tests: !enabled }),
      });
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        enabled = !!d.tests;
        hint.textContent = enabled ? tr("adminS.nowOn", "Testy sú zapnuté.") : tr("adminS.nowOff", "Testy sú vypnuté pre študentov.");
        hint.className = "admin-hint admin-hint--ok";
      } else {
        hint.textContent = d.error || tr("adminS.error", "Chyba.");
        hint.className = "admin-hint admin-hint--err";
      }
    } catch (e) {
      hint.textContent = tr("adminS.error", "Chyba.");
      hint.className = "admin-hint admin-hint--err";
    }
    render();
  });

  // len admin; ostatných presmeruj na dashboard (API je chránené aj na serveri)
  fetch("/api/admin/me", { credentials: "include" })
    .then(r => r.json())
    .then(d => { if (!d.is_admin) window.location.href = "/dashboard"; else load(); })
    .catch(() => { window.location.href = "/dashboard"; });
})();
