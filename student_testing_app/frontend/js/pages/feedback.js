/* AdaptPy - Dotazník (dynamický z DB).
   - Dostupný len ak ho admin zverejnil (inak server vráti 403 a zobrazí sa info).
   - Otázky sa načítajú z /api/feedback/questions (spravuje admin).
   - Admin NEMÔŽE vyplniť dotazník (len ho spravuje).
   - Existujúce odpovede sa predvyplnia, dajú sa upraviť.
   - Po odoslaní poďakovanie (bez presmerovania). */
document.addEventListener("DOMContentLoaded", async () => {
  const studentId = localStorage.getItem("student_id");
  const form = document.getElementById("feedback-form");

  function tr(key, fb) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  }
  const lang = () => (localStorage.getItem("adeptpy_lang") || "sk");

  if (!studentId) { window.location.href = "/login"; return; }

  // Admin nemôže vyplniť dotazník
  try {
    const ar = await fetch("/api/admin/me", { credentials: "include" });
    const ad = await ar.json();
    if (ad.is_admin) {
      const card = form.closest(".card") || form.parentNode;
      card.innerHTML = `
        <div class="fb-thanks">
          <div class="fb-thanks__title">${tr("fb.adminTitle","Si prihlásený ako administrátor")}</div>
          <div class="fb-thanks__text">${tr("fb.adminText","Administrátor dotazník nevypĺňa. Otázky môžeš spravovať v sekcii Dotazník (správa).")}</div>
          <a class="btn" href="/admin-feedback" data-i18n="fb.manageQuestions">Spravovať otázky</a>
        </div>`;
      if (typeof I18N !== "undefined") I18N.apply();
      return;
    }
  } catch (e) { /* ak zlyhá, pokračuj ako bežný user */ }

  // Načítaj otázky z DB
  let questions = [];
  try {
    const r = await fetch("/api/feedback/questions", { credentials: "include" });
    if (r.status === 401) { window.location.href = "/login"; return; }
    if (r.status === 403) {
      // Admin dotazník ešte nezverejnil (alebo ho skryl)
      const card = form.closest(".card") || form.parentNode;
      card.innerHTML = `
        <div class="fb-thanks">
          <div class="fb-thanks__title">${tr("fb.notPublishedTitle","Dotazník zatiaľ nie je dostupný")}</div>
          <div class="fb-thanks__text">${tr("fb.notPublishedText","Dotazník sa sprístupní, keď ho administrátor zverejní. Medzitým nám môžeš napísať cez formulár spätnej väzby.")}</div>
          <a class="btn" href="/feedback-form">${tr("fb.toFeedbackForm","Napísať spätnú väzbu")}</a>
        </div>`;
      return;
    }
    const d = await r.json();
    questions = d.questions || [];
  } catch (e) {}

  if (!questions.length) {
    form.innerHTML = `<p class="admin-muted">${tr("fb.noQuestions","Dotazník momentálne nemá žiadne otázky.")}</p>`;
    return;
  }

  // Načítaj existujúce odpovede
  let existing = {};
  let alreadySubmitted = false;
  try {
    const r = await fetch("/api/feedback/get", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const d = await r.json();
    if (d.submitted) { existing = d.feedback || {}; alreadySubmitted = true; }
  } catch (e) {}

  // Vygeneruj formulár
  const fieldsHtml = questions.map(q => {
    const label = lang() === "en" ? q.label_en : q.label_sk;
    const val = existing[q.qkey] != null ? existing[q.qkey] : "";
    const req = q.required ? "required" : "";
    let input = "";
    if (q.qtype === "select") {
      const opts = [`<option value="">${tr("fb.choose","-- Vyber --")}</option>`]
        .concat((q.options || []).map(o => `<option value="${o}" ${String(val) === o ? "selected" : ""}>${o}</option>`));
      input = `<select name="${q.qkey}" ${req}>${opts.join("")}</select>`;
    } else if (q.qtype === "number") {
      input = `<input type="number" name="${q.qkey}" value="${val}" ${req}>`;
    } else if (q.qtype === "textarea") {
      input = `<textarea name="${q.qkey}" rows="4" ${req}>${val}</textarea>`;
    } else {
      input = `<input type="text" name="${q.qkey}" value="${val}" ${req}>`;
    }
    return `<div class="form-field"><label>${label}</label>${input}</div>`;
  }).join("");

  const btnLabel = alreadySubmitted ? tr("fb.update", "Uložiť zmeny") : tr("fb.submit", "Odoslať");
  form.innerHTML = fieldsHtml + `<button type="submit">${btnLabel}</button>`;

  if (alreadySubmitted) {
    const info = document.createElement("div");
    info.className = "fb-message fb-message--info";
    info.textContent = tr("fb.editing", "Tvoje odpovede sú načítané. Môžeš ich upraviť a znova uložiť.");
    form.parentNode.insertBefore(info, form);
  }

  // Odoslanie
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const answers = {};
    for (const [k, v] of fd.entries()) answers[k] = v;

    try {
      const r = await fetch("/api/feedback", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers }),
      });
      await r.json();
      const card = form.closest(".card") || form.parentNode;
      card.innerHTML = `
        <div class="fb-thanks">
          <div class="fb-thanks__icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6 9 17l-5-5"/></svg></div>
          <div class="fb-thanks__title">${tr("fb.thanksTitle","Dotazník vyplnený")}</div>
          <div class="fb-thanks__text">${tr("fb.thanksText","Ďakujeme za tvoje postrehy! Každá odpoveď nám pomáha spraviť AdaptPy o kúsok lepším. Tvoj hlas formuje budúcnosť učenia.")}</div>
          <a class="btn" href="/dashboard">${tr("fb.backHome","Späť na prehľad")}</a>
        </div>`;
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      const info = document.createElement("div");
      info.className = "fb-message fb-message--error";
      info.textContent = tr("fb.error", "Nepodarilo sa odoslať. Skús to znova.");
      form.parentNode.insertBefore(info, form);
    }
  });
});
