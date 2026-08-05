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
        <button id="theme-toggle" class="icon-btn" type="button" aria-label="Toggle theme">
          <span id="theme-icon">🌙</span>
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
