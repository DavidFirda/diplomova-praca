/* ============================================================
   AdaptPy - navbar s prepínačom témy a jazyka.
   Vloží sa do <div id="navbar"></div> na začiatku stránky.
   ============================================================ */
(function () {
  function render() {
    const mount = document.getElementById("navbar");
    if (!mount) return;

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
        </div>
      </nav>
    `;

    // Po vykreslení aplikuj jazyk aj tému (ak je i18n načítané)
    if (typeof I18N !== "undefined") I18N.apply();
    if (typeof THEME !== "undefined") THEME.apply();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }
})();
