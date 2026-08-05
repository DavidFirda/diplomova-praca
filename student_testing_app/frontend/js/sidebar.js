/* ============================================================
   AdaptPy - bočný sidebar (app shell).
   Vloží sa do <div id="sidebar-mount"></div>.
   Ikony sú SVG line-art, dedia currentColor (čierne/biele podľa témy).
   Aktívna položka sa určí podľa data-active atribútu na mount elemente.
   ============================================================ */
(function () {
  const ICONS = {
    dashboard: '<svg viewBox="0 0 24 24" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/></svg>',
    pretest: '<svg viewBox="0 0 24 24" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/></svg>',
    tests: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 12l2 2 4-4"/></svg>',
    stats: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M3 3v18h18"/><path d="M7 15l3-4 3 2 4-6"/></svg>',
    profile: '<svg viewBox="0 0 24 24" stroke-width="1.8"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/></svg>',
    feedback: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    logout: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg>',
  };

  const NAV = [
    { key: "dashboard", href: "/dashboard", i18n: "sb.dashboard", label: "Dashboard" },
    { key: "profile", href: "/profile", i18n: "sb.profile", label: "Profil" },
    { key: "pretest", href: "/predtest", i18n: "sb.pretest", label: "Predtest" },
    { key: "tests", href: "/hlavnytest", i18n: "sb.tests", label: "Testy" },
    { key: "stats", href: "/analyza", i18n: "sb.stats", label: "Štatistika" },
    { key: "feedback", href: "/feedback", i18n: "sb.feedback", label: "Dotazník" },
  ];

  async function logout() {
    try { await fetch("/api/auth/logout", { method: "POST", credentials: "include" }); } catch (e) {}
    localStorage.removeItem("student_id");
    window.location.href = "/";
  }
  window.adaptpyLogout = logout;

  function render() {
    const mount = document.getElementById("sidebar-mount");
    if (!mount) return;
    const active = mount.getAttribute("data-active") || "dashboard";

    const links = NAV.map(item => `
      <a class="sidebar__link ${item.key === active ? "active" : ""}" href="${item.href}">
        <span class="ic">${ICONS[item.key]}</span>
        <span data-i18n="${item.i18n}">${item.label}</span>
      </a>
    `).join("");

    mount.innerHTML = `
      <div class="sidebar-backdrop" id="sidebar-backdrop"></div>
      <aside class="sidebar" id="sidebar">
        <a class="sidebar__brand" href="/">
          <img src="/assets/logo.svg" alt="" />
          <span>Adapt<span class="accent-py">Py</span></span>
        </a>
        <nav class="sidebar__nav">
          ${links}
        </nav>
        <div class="sidebar__spacer"></div>
        <a class="sidebar__link sidebar__link--danger" href="#" onclick="adaptpyLogout(); return false;">
          <span class="ic">${ICONS.logout}</span>
          <span data-i18n="sb.logout">Odhlásiť sa</span>
        </a>
      </aside>
    `;

    // mobilný toggle
    const backdrop = document.getElementById("sidebar-backdrop");
    const sidebar = document.getElementById("sidebar");
    window.adaptpyToggleSidebar = function () {
      sidebar.classList.toggle("open");
      backdrop.classList.toggle("show");
    };
    if (backdrop) backdrop.addEventListener("click", () => {
      sidebar.classList.remove("open");
      backdrop.classList.remove("show");
    });

    if (typeof I18N !== "undefined") I18N.apply();
    if (typeof THEME !== "undefined") THEME.apply();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }
})();
