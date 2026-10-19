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

  // Testy vypnuté adminom: študent kolónku (kartu aj metriku) nevidí, admin áno s tagom
  const testsOff = !!(data.sections && data.sections.tests === false);
  if (testsOff) {
    const metricMain = document.getElementById("main-count");
    const metricBox = metricMain && metricMain.closest(".metric");
    if (!data.is_admin) {
      if (rowMain) rowMain.style.display = "none";
      if (metricBox) metricBox.style.display = "none";
    } else if (rowMain) {
      // tag ide do tela karty ako samostatný prvok (titulok má data-i18n a I18N.apply() by ho prepísal)
      const body = rowMain.querySelector(".task-row__body");
      if (body && !body.querySelector(".task-row__tag")) {
        body.insertAdjacentHTML("beforeend", '<span class="task-row__tag" data-i18n="dash.hiddenTag">skryté pre študentov</span>');
      }
    }
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

  // ---------------------------------------------------------
  // Karty Úlohy a Cvičenia. Načítajú sa nezávisle od zvyšku dashboardu:
  // chyba jednej karty neskryje ostatné. Pri zmene jazyka sa len prekreslia.
  // ---------------------------------------------------------
  const tr = (key, fb) => {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  };
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (m) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
  const lang = () => ((typeof I18N !== "undefined" && I18N.lang) || "sk");
  const catName = (c) => (typeof I18N !== "undefined" ? I18N.category(c) : c);

  let ulohy = null;      // odpoveď /api/ulohy/summary
  let exercises = null;  // zoznam cvičení

  // ----- Úlohy -----
  function masteryRows(mastery) {
    const known = mastery.filter((m) => m.percent != null);
    const lowest = known.length ? Math.min(...known.map((m) => m.percent)) : null;
    const focusCat = lowest != null && lowest < 80 ? known.find((m) => m.percent === lowest).category : null;
    return mastery.map((m) => {
      const pct = m.percent;
      const level = pct == null ? "" : pct < 50 ? "dash-bar--low" : pct < 75 ? "dash-bar--mid" : "dash-bar--high";
      const pill = m.category === focusCat
        ? `<span class="dash-pill dash-pill--warn">${esc(tr("dash.ulohy.focus", "hlavný cieľ"))}</span>` : "";
      return `<div class="dash-mastery__row">
        <div class="dash-mastery__top">
          <span class="dash-mastery__name">${esc(catName(m.category))}${pill}</span>
          <span class="dash-mastery__pct">${pct == null ? "–" : pct + " %"}</span>
        </div>
        <div class="dash-bar ${level}"><div class="dash-bar__fill" style="width:${pct == null ? 0 : pct}%"></div></div>
      </div>`;
    }).join("");
  }

  function nextPanel(summary) {
    const c = summary.current;
    if (!c) {
      return `<div class="dash-label">${esc(tr("dash.ulohy.how", "Ako to funguje"))}</div>
        <ul class="dash-how">
          <li>${esc(tr("dash.ulohy.how1", "Máš 5 pokusov, prvý robíš bez pomoci."))}</li>
          <li>${esc(tr("dash.ulohy.how2", "Po nesprávnej odpovedi uvidíš, čo je zle, a kód opravíš sám."))}</li>
          <li>${esc(tr("dash.ulohy.how3", "Po 2. chybe ti pomôže asistent, po 5. sa ukáže riešenie."))}</li>
        </ul>`;
    }
    const dots = [];
    for (let i = 1; i <= c.max_attempts; i++) {
      const cls = i <= c.attempts_used ? "dash-dot--bad" : (i === c.attempts_used + 1 ? "dash-dot--now" : "");
      dots.push(`<i class="dash-dot ${cls}"></i>`);
    }
    return `<div class="dash-next__head">
        <span class="dash-label">${esc(tr("dash.ulohy.current", "Rozpracovaná úloha"))}</span>
        <span class="dash-pill dash-pill--warn">${esc(catName(c.category))}</span>
      </div>
      <div class="dash-next__text">${esc(I18N.questionText(c.question))}</div>
      <div class="dash-next__input"><b>${esc(tr("dash.ulohy.input", "Vstup"))}:</b> <code>${esc(c.question.input_data)}</code></div>
      <div class="dash-next__foot">
        <span>${esc(tr("dash.ulohy.attempt", "Pokus"))} ${Math.min(c.attempts_used + 1, c.max_attempts)}/${c.max_attempts}</span>
        <span class="dash-dots" aria-hidden="true">${dots.join("")}</span>
      </div>`;
  }

  function renderUlohy() {
    const row = document.getElementById("row-ulohy");
    if (!row || !ulohy) return;
    const btn = document.getElementById("ulohy-btn");
    const body = document.getElementById("ulohy-body");
    const statsEl = document.getElementById("ulohy-stats");
    const metric = document.getElementById("stat-ulohy");

    if (!ulohy.pretest_done) {            // úlohy sa odomknú až po predteste
      row.classList.add("dash-hero--locked");
      body.style.display = "none";
      statsEl.textContent = "";
      if (metric) metric.textContent = "–";
      btn.removeAttribute("href");
      btn.classList.remove("btn", "btn--secondary");
      btn.classList.add("task-row__locked-label");
      btn.textContent = tr("dash.pretest.locked", "Najprv dokonči predtest");
      return;
    }

    const st = ulohy.stats || { total: 0, solved: 0, solved_first_try: 0 };
    row.classList.remove("dash-hero--locked");
    body.style.display = "";
    document.getElementById("ulohy-mastery").innerHTML = masteryRows(ulohy.mastery || []);
    document.getElementById("ulohy-next").innerHTML = nextPanel(ulohy);
    if (metric) metric.textContent = st.total > 0 ? `${st.solved} / ${st.total}` : "–";
    statsEl.innerHTML = st.total > 0
      ? `${esc(tr("dash.ulohy.statSolved", "Vyriešené"))}: <b>${st.solved}</b> ${esc(tr("dash.ulohy.statOf", "z"))} <b>${st.total}</b>`
        + ` · ${esc(tr("dash.ulohy.statFirst", "na 1. pokus"))}: <b>${st.solved_first_try}</b>`
      : "";
    btn.classList.add("btn", "btn--secondary");
    btn.classList.remove("task-row__locked-label");
    btn.setAttribute("href", "/ulohy");
    btn.textContent = ulohy.current ? tr("dash.ulohy.resume", "Pokračovať v úlohe")
      : st.total > 0 ? tr("dash.ulohy.continue", "Pokračovať v úlohách")
      : tr("dash.ulohy.start", "Začať úlohy");
  }

  // ----- Cvičenia -----
  function exTitle(ex) {
    return lang() === "en" ? (ex.title_en || ex.title_sk) : (ex.title_sk || ex.title_en);
  }
  function exItem(ex) {
    let badge, cls = "";
    if (ex.locked) { badge = tr("ex.locked", "Zamknuté"); cls = "dash-ex--locked"; }
    else if (ex.status === "completed") { badge = tr("ex.done", "Dokončené"); cls = "dash-ex--done"; }
    else if (ex.status === "in_progress") { badge = tr("ex.inProgress", "Rozpracované"); cls = "dash-ex--progress"; }
    else { badge = tr("dash.cv.notStarted", "Nezačaté"); }
    const pct = Math.max(0, Math.min(100, ex.percent || 0));
    const inner = `<div class="dash-ex__top">
        <span class="dash-ex__title">${esc(exTitle(ex) || ex.slug)}</span>
        <span class="dash-ex__badge">${esc(badge)}</span>
      </div>
      <div class="dash-bar"><div class="dash-bar__fill" style="width:${pct}%"></div></div>
      <div class="dash-ex__note">${pct} % ${esc(tr("ex.progressLabel", "vypracované"))}</div>`;
    return ex.locked
      ? `<div class="dash-ex ${cls}">${inner}</div>`
      : `<a class="dash-ex ${cls}" href="/cvicenie?id=${ex.id}">${inner}</a>`;
  }
  function renderCvicenia() {
    const list = document.getElementById("cvicenia-list");
    if (!list || !exercises) return;
    if (!exercises.length) {
      list.innerHTML = `<div class="dash-empty">${esc(tr("ex.none", "Zatiaľ tu nie sú žiadne cvičenia."))}</div>`;
      return;
    }
    // najprv rozpracované, potom odomknuté nezačaté, potom ostatné; max. 3
    const rank = (e) => e.locked ? 3 : e.status === "in_progress" ? 0 : e.status === "not_started" ? 1 : 2;
    const top = exercises.map((e, i) => ({ e, i }))
      .sort((a, b) => rank(a.e) - rank(b.e) || a.i - b.i).slice(0, 3).map((x) => x.e);
    list.innerHTML = top.map(exItem).join("");
  }

  async function getJson(url) {
    const r = await fetch(url, { credentials: "include" });
    if (!r.ok) throw new Error(url + " " + r.status);
    return r.json();
  }
  const [uRes, eRes] = await Promise.allSettled([getJson("/api/ulohy/summary"), getJson("/api/exercises")]);
  if (uRes.status === "fulfilled") { ulohy = uRes.value; renderUlohy(); }
  else { const r = document.getElementById("row-ulohy"); if (r) r.style.display = "none"; }
  if (eRes.status === "fulfilled") { exercises = eRes.value.exercises || []; renderCvicenia(); }
  else { const r = document.getElementById("row-cvicenia"); if (r) r.style.display = "none"; }

  document.addEventListener("langchange", () => { renderUlohy(); renderCvicenia(); });
})();
