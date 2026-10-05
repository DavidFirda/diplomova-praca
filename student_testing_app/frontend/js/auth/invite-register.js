/* ============================================================
   AdaptPy - registrácia cez POZVÁNKU (stránka /register)
   - /register?invite=TOKEN : overí pozvánku, predvyplní a zamkne e-mail,
     odoslanie formulára ide na /api/invites/register
   - bez tokenu: ak je registrácia len na pozvánku, formulár sa nahradí hláškou
   Načítava sa PRED checkAccessCode(), aby pozvaný používateľ nemusel
   zadávať prístupový kód.
   ============================================================ */
(function () {
  const params = new URLSearchParams(window.location.search);
  const token = (params.get("invite") || "").trim();

  // pozvaný používateľ preskočí heslo "prístupového kódu" (platný token je vstupenka)
  if (token) { try { sessionStorage.setItem("access_granted", "true"); } catch (e) {} }

  function lang() { try { return (typeof I18N !== "undefined" && I18N.lang) || "sk"; } catch (e) { return "sk"; } }
  const FB = {
    "invite.only":    { sk: "Registrácia je možná len na pozvánku od administrátora.", en: "Registration is by invitation from an administrator only." },
    "invite.onlyHint":{ sk: "Ak si pozvánku dostal/a e-mailom, otvor odkaz z e-mailu.", en: "If you received an invitation by e-mail, open the link from it." },
    "invite.invalid": { sk: "Pozvánka je neplatná.", en: "The invitation is invalid." },
    "invite.used":    { sk: "Táto pozvánka už bola použitá.", en: "This invitation has already been used." },
    "invite.expired": { sk: "Platnosť pozvánky vypršala. Požiadaj administrátora o novú.", en: "The invitation has expired. Ask an administrator for a new one." },
    "invite.welcome": { sk: "Pozvánka je platná – dokonči registráciu.", en: "Invitation is valid – complete your registration." },
    "invite.done":    { sk: "Registrácia úspešná! Teraz sa môžeš prihlásiť.", en: "Registration successful! You can now log in." },
    "invite.err":     { sk: "Chyba pripojenia k serveru.", en: "Server connection error." },
  };
  function t(key) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return (FB[key] || {})[lang()] || (FB[key] || {}).sk || key;
  }

  function ready(fn) {
    if (document.readyState !== "loading") fn(); else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(async function () {
    const form = document.getElementById("register-form");
    const errEl = document.getElementById("error-message");
    if (!form) return;

    // banner nad formulárom
    const banner = document.createElement("p");
    banner.id = "invite-banner";
    banner.style.cssText = "display:none;margin:0 0 14px;padding:10px 14px;border-radius:10px;font-weight:600;font-size:.9rem;";
    form.parentNode.insertBefore(banner, form);
    function showBanner(msg, ok) {
      banner.textContent = msg;
      banner.style.display = "block";
      banner.style.background = ok ? "var(--success-soft, #e6f7ee)" : "var(--danger-soft, #fdecec)";
      banner.style.color = ok ? "var(--success, #1a7f4b)" : "var(--danger, #c62828)";
    }
    function lockForm(hint) {
      form.style.display = "none";
      if (hint) {
        const p = document.createElement("p");
        p.style.cssText = "color:var(--text-muted);font-size:.9rem;margin-top:8px;";
        p.textContent = hint;
        banner.parentNode.insertBefore(p, form);
      }
    }

    // ---- bez tokenu ----
    if (!token) {
      let mode = "invite";
      try { mode = (await (await fetch("/api/invites/mode")).json()).mode; } catch (e) {}
      if (mode !== "open") {
        showBanner(t("invite.only"), false);
        lockForm(t("invite.onlyHint"));
      }
      return;                      // režim "open": pôvodný formulár ostáva
    }

    // ---- s tokenom ----
    let info;
    try {
      info = await (await fetch("/api/invites/check?token=" + encodeURIComponent(token))).json();
    } catch (e) { showBanner(t("invite.err"), false); lockForm(); return; }

    if (!info.valid) {
      showBanner(t("invite." + (info.reason || "invalid")), false);
      lockForm();
      return;
    }

    showBanner(t("invite.welcome"), true);
    const $ = id => document.getElementById(id);
    $("email").value = info.email;
    $("email").readOnly = true;
    $("email").style.opacity = ".75";
    if (info.name) $("name").value = info.name;
    if (info.surname) $("surname").value = info.surname;

    // Prebije pôvodný submit handler (capture na dokumente beží skôr ako handler formulára).
    document.addEventListener("submit", async function (e) {
      if (e.target !== form) return;
      e.preventDefault();
      e.stopImmediatePropagation();

      const btn = form.querySelector("button[type=submit]");
      if (btn) btn.disabled = true;
      errEl.style.display = "none";
      try {
        const r = await fetch("/api/invites/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            token,
            name: $("name").value, surname: $("surname").value,
            login: $("login").value, password: $("password").value,
          }),
        });
        const d = await r.json();
        if (r.ok && d.student) {
          alert(t("invite.done"));
          window.location.href = "/login";
          return;
        }
        let msg = d.error || t("invite.err");
        try {
          if (d.error_key && typeof I18N !== "undefined") { const v = I18N.t(d.error_key); if (v && v !== d.error_key) msg = v; }
        } catch (x) {}
        errEl.innerText = msg;
        errEl.style.display = "block";
      } catch (x) {
        errEl.innerText = t("invite.err");
        errEl.style.display = "block";
      } finally { if (btn) btn.disabled = false; }
    }, true);
  });
})();
