/* AdaptPy - Dotazník: načíta existujúce odpovede z DB, umožní ich upraviť,
   po odoslaní zobrazí poďakovanie (nepresmeruje). */
document.addEventListener("DOMContentLoaded", async () => {
  const studentId = localStorage.getItem("student_id");
  const form = document.getElementById("feedback-form");

  function tr(key, fallback) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fallback;
  }

  if (!studentId) {
    alert("Chýbajú informácie o študentovi.");
    window.location.href = "/login";
    return;
  }

  let alreadySubmitted = false;

  // Načítaj existujúce odpovede a predvypln formulár
  try {
    const res = await fetch("/api/feedback/get", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: studentId }),
    });
    const data = await res.json();
    if (data.submitted && data.feedback) {
      alreadySubmitted = true;
      for (const [key, val] of Object.entries(data.feedback)) {
        if (val === null || val === undefined) continue;
        const field = form.elements[key];
        if (field) field.value = val;
      }
      // Zmeň nadpis tlačidla a doplň info, že ide o úpravu
      const btn = form.querySelector('button[type="submit"]');
      if (btn) btn.textContent = tr("fb.update", "Uložiť zmeny");
      showInfo(tr("fb.editing", "Tvoje odpovede sú načítané. Môžeš ich upraviť a znova uložiť."), "info");
    }
  } catch (e) { /* ticho */ }

  function showInfo(msg, type) {
    let box = document.getElementById("fb-message");
    if (!box) {
      box = document.createElement("div");
      box.id = "fb-message";
      box.className = "fb-message";
      form.parentNode.insertBefore(box, form);
    }
    box.textContent = msg;
    box.className = "fb-message fb-message--" + (type || "info");
  }

  // Odoslanie / uloženie
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    data.student_id = studentId;

    try {
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const result = await res.json();

      // Nahraď formulár poďakovaním (nepresmeruje nikam)
      const card = form.closest(".card") || form.parentNode;
      card.innerHTML = `
        <div class="fb-thanks">
          <div class="fb-thanks__icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6 9 17l-5-5"/></svg>
          </div>
          <div class="fb-thanks__title">${tr("fb.thanksTitle", "Dotazník vyplnený 🎉")}</div>
          <div class="fb-thanks__text">${tr("fb.thanksText", "Ďakujeme za tvoje postrehy! Každá odpoveď nám pomáha spraviť AdaptPy o kúsok lepším. Tvoj hlas formuje budúcnosť učenia.")}</div>
          <a class="btn" href="/dashboard" data-i18n="fb.backHome">Späť na prehľad</a>
        </div>
      `;
      if (typeof I18N !== "undefined") I18N.apply();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      showInfo(tr("fb.error", "Nepodarilo sa odoslať. Skús to znova."), "error");
    }
  });
});
