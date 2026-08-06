/* ============================================================
   AdaptPy - horný navbar (pre úvod, login, register).
   - Klik na "AdaptPy" vždy vedie na / (úvod).
   - Auth tlačidlo (meno + Odhlásiť sa) sa zobrazí LEN keď je
     používateľ prihlásený. Neprihlásený nevidí žiadne auth tlačidlo.
   ============================================================ */
(function () {
  async function getAuthState() {
    try {
      const r = await fetch("/api/auth/me", { credentials: "include" });
      if (r.ok) {
        const data = await r.json();
        return data.student || null;
      }
    } catch (e) {}
    return null;
  }

  async function logout() {
    try { await fetch("/api/auth/logout", { method: "POST", credentials: "include" }); } catch (e) {}
    localStorage.removeItem("student_id");
    window.location.href = "/";
  }
  window.adaptpyLogout = logout;

  async function render() {
    const mount = document.getElementById("navbar");
    if (!mount) return;

    const student = await getAuthState();

    // Auth časť: prihlásený vidí meno + Odhlásiť sa,
    // neprihlásený vidí decentné "Prihlásiť sa" (rovnaký minimalistický štýl).
    let authHtml;
    if (student) {
      const displayName = student.name ? student.name : student.login;
      authHtml = `
        <a href="/dashboard" class="navbar__user" title="${displayName}">
          <span class="navbar__user-avatar">${(displayName[0] || "?").toUpperCase()}</span>
          <span class="navbar__user-name">${displayName}</span>
        </a>
        <button class="icon-btn" type="button" onclick="adaptpyLogout()" data-i18n="nav.logout">Odhlásiť sa</button>
      `;
    } else {
      authHtml = `<a href="/login" class="icon-btn" data-i18n="nav.login">Prihlásiť sa</a>`;
    }

    mount.innerHTML = `
      <nav class="navbar">
        <a class="navbar__brand" href="/">
          <img src="/assets/logo.svg" alt="" class="navbar__brand-logo" width="34" height="34" />
          <span>Adapt<span class="navbar__brand-accent">Py</span></span>
        </a>
        <div class="navbar__actions">
          <div class="lang-switch" role="group" aria-label="Language">
            <button data-lang="sk" type="button">SK</button>
            <button data-lang="en" type="button">EN</button>
          </div>
          <button id="theme-toggle" class="theme-slider" type="button" aria-label="Toggle theme">
            <span class="theme-slider__knob">
              <svg class="theme-slider__sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19"/></svg>
              <svg class="theme-slider__moon" viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/></svg>
            </span>
          </button>
          ${authHtml}
        </div>
      </nav>
    `;

    // Expose stav pre stránky (napr. index tlačidlo "Začať")
    window.adaptpyStudent = student;
    document.dispatchEvent(new CustomEvent("adaptpy:auth", { detail: { student } }));

    if (typeof I18N !== "undefined") I18N.apply();
    if (typeof THEME !== "undefined") THEME.apply();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }
})();
