/* AdaptPy - horná lišta (toolbar) stránok po prihlásení:
   hamburger (mobil) + názov stránky (ukáže sa po odscrollovaní) +
   prepínač jazyka SK/EN, prepínač témy a tlačidlo Odhlásiť sa.
   Vloží sa do <div id="topbar-controls"></div>. Lišta je vďaka CSS
   prilepená hore (sticky) a priesvitná. */
(function () {
  const MENU_IC = '<svg viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none" width="22" height="22" aria-hidden="true"><line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/></svg>';
  const LOGOUT_IC = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg>';

  function render() {
    const mount = document.getElementById("topbar-controls");
    if (!mount) return;
    mount.innerHTML = `
      <button class="topbar-hamburger" type="button" onclick="window.adaptpyToggleSidebar && adaptpyToggleSidebar()" aria-label="Menu" data-i18n-aria-label="sb.menu" aria-expanded="false" aria-controls="sidebar">
        ${MENU_IC}
      </button>
      <span class="topbar-title" aria-hidden="true"></span>
      <div class="topbar-switches">
        <div class="lang-switch" role="group" aria-label="Language">
          <button data-lang="sk" type="button">SK</button>
          <button data-lang="en" type="button">EN</button>
        </div>
        <button id="theme-toggle" class="theme-slider" type="button" aria-label="Toggle theme" data-i18n-aria-label="nav.theme">
          <span class="theme-slider__knob">
            <svg class="theme-slider__sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19"/></svg>
            <svg class="theme-slider__moon" viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/></svg>
          </span>
        </button>
        <span class="topbar-sep" aria-hidden="true"></span>
        <button class="topbar-logout" type="button" onclick="window.adaptpyLogout && adaptpyLogout()" aria-label="Odhlásiť sa" data-i18n-aria-label="sb.logout">
          ${LOGOUT_IC}<span data-i18n="sb.logout">Odhlásiť sa</span>
        </button>
      </div>
    `;
    setupTitle(mount);
    if (typeof I18N !== "undefined") I18N.apply();
    if (typeof THEME !== "undefined") THEME.apply();
  }

  // Názov stránky v lište: kópia veľkého nadpisu, viditeľná až keď nadpis
  // odscrolluje pod lištu (ako "large title" v iOS).
  function setupTitle(bar) {
    const h1 = document.querySelector(".app-topbar__greeting h1");
    const titleEl = bar.querySelector(".topbar-title");
    const sync = () => { if (h1 && titleEl) titleEl.textContent = h1.textContent.replace(/\s+/g, " ").trim(); };
    sync();
    document.addEventListener("langchange", () => setTimeout(sync, 0));
    if (h1 && "MutationObserver" in window) {
      new MutationObserver(sync).observe(h1, { childList: true, subtree: true, characterData: true });
    }
    let ticking = false;
    const update = () => {
      ticking = false;
      bar.classList.toggle("is-scrolled", window.scrollY > 2);
      const barH = bar.offsetHeight || 56;
      const past = h1 ? h1.getBoundingClientRect().bottom < barH : false;
      bar.classList.toggle("show-title", past);
    };
    window.addEventListener("scroll", () => {
      if (!ticking) { ticking = true; requestAnimationFrame(update); }
    }, { passive: true });
    window.addEventListener("resize", update, { passive: true });
    update();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }
})();
