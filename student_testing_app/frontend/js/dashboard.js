/* ============================================================
   AdaptPy - dashboard logika (sidebar layout)
   ============================================================ */
(async function () {
  let data;
  try {
    const r = await fetch("/api/auth/dashboard", { credentials: "include" });
    if (r.status === 401) { window.location.href = "/login"; return; }
    data = await r.json();
  } catch (e) {
    window.location.href = "/login";
    return;
  }

  const s = data.student || {};
  const displayName = s.name || s.login || "";

  // Privítanie
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  set("dash-name", displayName);

  // Predtest - po dokončení celá karta zmizne
  const pretestDone = data.pretest && data.pretest.done;
  if (pretestDone) {
    const rowPretest = document.getElementById("row-pretest");
    if (rowPretest) rowPretest.style.display = "none";
  }

  // Hlavné testy
  const mainCount = (data.main_tests && data.main_tests.count) || 0;
  set("main-count", mainCount);
  const rowMain = document.getElementById("row-main");
  const mainBtn = document.getElementById("main-btn");
  if (!pretestDone && rowMain && mainBtn) {
    rowMain.classList.add("task-row--locked");
    mainBtn.textContent = (typeof I18N !== "undefined") ? I18N.t("dash.pretest.locked") : "Najprv dokonči predtest";
    mainBtn.removeAttribute("href");
    mainBtn.style.pointerEvents = "none";
    mainBtn.classList.remove("btn");
    mainBtn.classList.add("task-row__locked-label");
  }

  // Štatistika
  const stats = data.stats || {};
  set("stat-accuracy", (stats.total_answers > 0) ? stats.accuracy + " %" : "–");
  set("stat-answers", stats.total_answers || 0);

  // Dotazník
  if (data.feedback_done) {
    const fb = document.getElementById("feedback-badge");
    if (fb) fb.style.display = "inline-flex";
    const fbBtn = document.getElementById("feedback-btn");
    if (fbBtn) fbBtn.textContent = (typeof I18N !== "undefined") ? I18N.t("dash.feedback.edit") : "Upraviť odpovede";
  }

  if (typeof I18N !== "undefined") I18N.apply();
})();
