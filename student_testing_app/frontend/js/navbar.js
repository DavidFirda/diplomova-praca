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
          <button id="theme-toggle" class="icon-btn" type="button" aria-label="Toggle theme">
            <span id="theme-icon">🌙</span>
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
