/* AdaptPy - Feedback formulár (voľná správa). Je dostupný vždy,
   nezávisle od toho, či admin zverejnil dotazník. */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("feedback-form");
  const msg = document.getElementById("ff-message");
  const count = document.getElementById("ff-count");
  const hint = document.getElementById("ff-hint");
  const btn = document.getElementById("ff-submit");

  function tr(key, fb) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  }
  function showHint(text, isError) {
    hint.textContent = text;
    hint.className = "admin-hint" + (isError ? " admin-hint--err" : "");
  }

  msg.addEventListener("input", () => { count.textContent = msg.value.length; });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showHint("");
    btn.disabled = true;
    try {
      const r = await fetch("/api/feedback/message", {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: document.getElementById("ff-category").value,
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
          <div class="fb-thanks__title">${tr("ff.thanksTitle", "Ďakujeme za spätnú väzbu 🎉")}</div>
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
