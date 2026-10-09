/* ============================================================
   AdaptPy - dashboard logika (sidebar layout)
   ============================================================ */
(async function () {
  let data;
  try {
    // Zdieľané volanie (deduplikované so sidebar/guard) - nevolá sa druhýkrát.
    data = window.adaptpyGetDashboard
      ? await window.adaptpyGetDashboard()
      : await (await fetch("/api/auth/dashboard", { credentials: "include" })).json();
    if (!data || data._unauth) { window.location.href = "/login"; return; }
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

  // Dotazník - zobrazí sa len ak ho admin zverejnil (feedback formulár je vždy)
  const rowQ = document.getElementById("row-questionnaire");
  if (rowQ) rowQ.style.display = data.questionnaire_published ? "" : "none";
  if (data.questionnaire_published && data.feedback_done) {
    const fb = document.getElementById("feedback-badge");
    if (fb) fb.style.display = "inline-flex";
    const fbBtn = document.getElementById("feedback-btn");
    if (fbBtn) fbBtn.textContent = (typeof I18N !== "undefined") ? I18N.t("dash.feedback.edit") : "Upraviť odpovede";
  }

  if (typeof I18N !== "undefined") I18N.apply();
})();
