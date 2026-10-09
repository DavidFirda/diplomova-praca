/* AdaptPy - Feedback formulár (hviezdičky + typ správy + text).
   Je dostupný vždy, nezávisle od toho, či admin zverejnil dotazník. */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("feedback-form");
  const msg = document.getElementById("ff-message");
  const count = document.getElementById("ff-count");
  const hint = document.getElementById("ff-hint");
  const btn = document.getElementById("ff-submit");
  const ratingText = document.getElementById("ff-rating-text");
  const stars = Array.from(form.querySelectorAll("#ff-stars label"));

  function tr(key, fb) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  }
  const RATE_FALLBACK = { 1: "Zlé", 2: "Slabé", 3: "Priemerné", 4: "Dobré", 5: "Skvelé" };
  const rateLabel = (n) => tr("ff.rate" + n, RATE_FALLBACK[n]);
  const selectedRating = () => {
    const el = form.querySelector('input[name="rating"]:checked');
    return el ? parseInt(el.value, 10) : null;
  };

  function showHint(text, isError) {
    hint.textContent = text;
    hint.className = "admin-hint" + (isError ? " admin-hint--err" : "");
  }

  // Popis hodnotenia pod hviezdičkami (hover = náhľad, inak vybraná hodnota).
  // Texty sa čítajú pri každom volaní, takže sledujú zmenu jazyka SK/EN.
  function renderRatingText(preview) {
    const n = preview || selectedRating();
    ratingText.textContent = n ? `${rateLabel(n)} (${n}/5)` : "";
    stars.forEach((l) => l.setAttribute("aria-label", `${rateLabel(l.dataset.rate)} (${l.dataset.rate}/5)`));
  }
  stars.forEach((l) => {
    l.addEventListener("mouseenter", () => renderRatingText(parseInt(l.dataset.rate, 10)));
    l.addEventListener("mouseleave", () => renderRatingText());
  });
  form.addEventListener("change", (e) => { if (e.target.name === "rating") renderRatingText(); });
  document.querySelectorAll(".lang-switch").forEach((el) => el.addEventListener("click", () => setTimeout(renderRatingText, 0)));
  renderRatingText();

  msg.addEventListener("input", () => { count.textContent = msg.value.length; });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showHint("");
    if (msg.value.trim().length < 3) {
      showHint(tr("ff.tooShort", "Napíš aspoň pár slov."), true);
      msg.focus();
      return;
    }
    btn.disabled = true;
    try {
      const r = await fetch("/api/feedback/message", {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: form.querySelector('input[name="category"]:checked').value,
          rating: selectedRating(),
          message: msg.value,
        }),
      });
      if (r.status === 401) { window.location.href = "/login"; return; }
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        showHint(tr(d.error_key, d.error || tr("ff.error", "Nepodarilo sa odoslať. Skús to znova.")), true);
        btn.disabled = false;
        return;
      }
      const card = form.closest(".card") || form.parentNode;
      card.innerHTML = `
        <div class="fb-thanks">
          <div class="fb-thanks__icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6 9 17l-5-5"/></svg></div>
          <div class="fb-thanks__title">${tr("ff.thanksTitle", "Ďakujeme za spätnú väzbu ")}</div>
          <div class="fb-thanks__text">${tr("ff.thanksText", "Tvoja správa nám pomôže spraviť AdaptPy lepším.")}</div>
          <a class="btn" href="/dashboard">${tr("fb.backHome", "Späť na prehľad")}</a>
        </div>`;
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      showHint(tr("ff.error", "Nepodarilo sa odoslať. Skús to znova."), true);
      btn.disabled = false;
    }
  });
});
