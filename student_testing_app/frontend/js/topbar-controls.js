/* AdaptPy - topbar ovládanie: hamburger (mobil) + prepínače jazyka/témy.
   Hamburger je prvý, prepínače za ním. Na mobile je hamburger vľavo,
   prepínače vpravo (rieši CSS). Vloží sa do <div id="topbar-controls"></div>. */
(function () {
  function render() {
    const mount = document.getElementById("topbar-controls");
    if (!mount) return;
    mount.innerHTML = `
      <button class="topbar-hamburger" type="button" onclick="adaptpyToggleSidebar && adaptpyToggleSidebar()" aria-label="Menu">
        <svg viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" fill="none" width="22" height="22"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
      </button>
      <div class="topbar-switches">
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
      </div>
    `;
    if (typeof I18N !== "undefined") I18N.apply();
    if (typeof THEME !== "undefined") THEME.apply();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }
})();
