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
    course: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
    adminUsers: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    adminFeedback: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M9 13h6M9 17h4"/></svg>',
    exercises: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M4 4h11l5 5v11a0 0 0 0 1 0 0H4z"/><path d="M14 4v5h5"/><path d="M8 13l2 2 4-4"/></svg>',
    adminExercises: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M4 4h11l5 5v11H4z"/><path d="M14 4v5h5"/><path d="M8 14h6M8 17h4"/></svg>',
  };

  const NAV = [
    { key: "dashboard", href: "/dashboard", i18n: "sb.dashboard", label: "Dashboard" },
    { key: "profile", href: "/profile", i18n: "sb.profile", label: "Profil" },
    { key: "pretest", href: "/predtest", i18n: "sb.pretest", label: "Predtest" },
    { key: "tests", href: "/hlavnytest", i18n: "sb.tests", label: "Testy" },
    { key: "exercises", href: "/cvicenia", i18n: "sb.exercises", label: "Cvičenia" },
    { key: "stats", href: "/analyza", i18n: "sb.stats", label: "Štatistika" },
    { key: "feedback", href: "/feedback", i18n: "sb.feedback", label: "Dotazník" },
  ];

  async function logout() {
    try { await fetch("/api/auth/logout", { method: "POST", credentials: "include" }); } catch (e) {}
    localStorage.removeItem("student_id");
    window.location.href = "/";
  }
  window.adaptpyLogout = logout;

  async function fetchStudent() {
    try {
      const r = await fetch("/api/auth/me", { credentials: "include" });
      if (r.ok) { const d = await r.json(); return d.student || null; }
    } catch (e) {}
    return null;
  }

  async function fetchPretestDone() {
    try {
      const r = await fetch("/api/auth/dashboard", { credentials: "include" });
      if (r.ok) { const d = await r.json(); return !!(d.pretest && d.pretest.done); }
    } catch (e) {}
    return false;
  }

  function render(student, pretestDone, isAdmin) {
    const mount = document.getElementById("sidebar-mount");
    if (!mount) return;
    const active = mount.getAttribute("data-active") || "dashboard";

    // Ak je predtest hotový, odstráň ho z navigácie (už sa nedá opakovať)
    const navItems = pretestDone ? NAV.filter(i => i.key !== "pretest") : NAV;

    const links = navItems.map(item => `
      <a class="sidebar__link ${item.key === active ? "active" : ""}" href="${item.href}">
        <span class="ic">${ICONS[item.key]}</span>
        <span data-i18n="${item.i18n}">${item.label}</span>
      </a>
    `).join("");

    // Admin sekcia - len pre admina
    let adminHtml = "";
    if (isAdmin) {
      const adminNav = [
        { key: "adminUsers", href: "/admin-users", i18n: "sb.adminUsers", label: "Používatelia", active: "admin-users" },
        { key: "adminExercises", href: "/admin-exercises", i18n: "sb.adminExercises", label: "Cvičenia (správa)", active: "admin-exercises" },
        { key: "adminFeedback", href: "/admin-feedback", i18n: "sb.adminFeedback", label: "Dotazník (správa)", active: "admin-feedback" },
      ];
      const adminLinks = adminNav.map(item => `
        <a class="sidebar__link ${item.active === active ? "active" : ""}" href="${item.href}">
          <span class="ic">${ICONS[item.key]}</span>
          <span data-i18n="${item.i18n}">${item.label}</span>
        </a>
      `).join("");
      adminHtml = `
        <div class="sidebar__section-label" data-i18n="sb.adminSection">Administrácia</div>
        ${adminLinks}
      `;
    }

    // Profilová karta hore (ako referencia): avatar + meno + login
    let profileHtml = "";
    if (student) {
      const fullName = (student.name && student.surname)
        ? `${student.name} ${student.surname}`
        : (student.name || student.login || "");
      const initial = ((student.name || student.login || "?")[0] || "?").toUpperCase();
      profileHtml = `
        <a class="sidebar__profile" href="/profile" title="Profil">
          <span class="sidebar__profile-avatar">${initial}</span>
          <span class="sidebar__profile-info">
            <span class="sidebar__profile-name">${fullName}</span>
            <span class="sidebar__profile-sub">${student.login || ""}</span>
          </span>
        </a>
        <hr class="sidebar__divider">
      `;
    }

    mount.innerHTML = `
      <div class="sidebar-backdrop" id="sidebar-backdrop"></div>
      <aside class="sidebar" id="sidebar">
        <a class="sidebar__brand" href="/">
          <img src="/assets/logo.svg" alt="" />
          <span>Adapt<span class="accent-py">Py</span></span>
        </a>
        ${profileHtml}
        <nav class="sidebar__nav">
          ${links}
          ${adminHtml}
        </nav>
        <div class="sidebar__spacer"></div>
        <a class="sidebar__link" href="https://github.com/ianmagyar/introduction-to-python" target="_blank" rel="noopener">
          <span class="ic">${ICONS.course}</span>
          <span data-i18n="sb.course">Stránka predmetu</span>
        </a>
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

  async function fetchIsAdmin() {
    try {
      const r = await fetch("/api/admin/me", { credentials: "include" });
      if (r.ok) { const d = await r.json(); return !!d.is_admin; }
    } catch (e) {}
    return false;
  }

  async function init() {
    // Guard: ak bola karta zatvorená a otvorená nanovo, odhlás a presmeruj na login.
    if (window.adaptpySessionGuard) {
      const ok = await window.adaptpySessionGuard();
      if (!ok) return; // guard už presmeroval
    }
    // Jedno zdieľané volanie /api/auth/dashboard (deduplikované) namiesto
    // 3 samostatných (/me, /dashboard, /admin/me) - výrazne rýchlejšie.
    let student = null, pretestDone = false, isAdmin = false;
    if (window.adaptpyGetDashboard) {
      const dash = await window.adaptpyGetDashboard();
      if (dash && !dash._unauth) {
        student = dash.student || null;
        pretestDone = !!(dash.pretest && dash.pretest.done);
        isAdmin = !!dash.is_admin;
      }
    } else {
      // fallback (ak by guard nebol načítaný)
      [student, pretestDone, isAdmin] = await Promise.all([fetchStudent(), fetchPretestDone(), fetchIsAdmin()]);
    }
    render(student, pretestDone, isAdmin);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
