/* ============================================================
   AdaptPy - bočný sidebar (app shell).
   ============================================================ */
(function () {
  const ICONS = {
    dashboard: '<svg viewBox="0 0 24 24" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/></svg>',
    pretest: '<svg viewBox="0 0 24 24" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/></svg>',
    tests: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 12l2 2 4-4"/></svg>',
    stats: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M3 3v18h18"/><path d="M7 15l3-4 3 2 4-6"/></svg>',
    profile: '<svg viewBox="0 0 24 24" stroke-width="1.8"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/></svg>',
    feedback: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 12h6M9 16h4"/></svg>',
    feedbackForm: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    logout: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg>',
    course: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
    adminUsers: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    adminFeedback: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M9 13h6M9 17h4"/></svg>',
    ulohy: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M8 7l-5 5 5 5"/><path d="M16 7l5 5-5 5"/><path d="M14 4l-4 16"/></svg>',
    exercises: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M4 4h11l5 5v11a0 0 0 0 1 0 0H4z"/><path d="M14 4v5h5"/><path d="M8 13l2 2 4-4"/></svg>',
    adminTests: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 14h6M9 17h4"/></svg>',
    adminExercises: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M4 4h11l5 5v11H4z"/><path d="M14 4v5h5"/><path d="M8 14h6M8 17h4"/></svg>',
    materials: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z"/><path d="M22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z"/></svg>',
    adminAssistant: '<svg viewBox="0 0 24 24" stroke-width="1.8"><rect x="4.5" y="6.5" width="15" height="12.5" rx="4.2"/><path d="M12 3.2v3"/><path d="M9 12h.01M15 12h.01"/><path d="M9.4 15.6c.75.6 1.6.9 2.6.9s1.85-.3 2.6-.9"/></svg>',
    adminMaterials: '<svg viewBox="0 0 24 24" stroke-width="1.8"><path d="M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z"/><path d="M22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z"/><path d="M15 9h4"/></svg>',
  };


  const NAV = [
    { key: "dashboard", href: "/dashboard", i18n: "sb.dashboard", label: "Dashboard" },
    { key: "pretest", href: "/predtest", i18n: "sb.pretest", label: "Predtest" },
    { key: "exercises", href: "/cvicenia", i18n: "sb.exercises", label: "Cvičenia" },
    { key: "ulohy", href: "/ulohy", i18n: "sb.ulohy", label: "Úlohy" },
    { key: "tests", href: "/hlavnytest", i18n: "sb.tests", label: "Testy", sectionKey: "tests" },
    { key: "stats", href: "/analyza", i18n: "sb.stats", label: "Štatistika" },
    { key: "materials", href: "/materialy", i18n: "sb.materials", label: "Materiály", materialsOnly: true },
    { key: "feedbackForm", href: "/feedback-form", i18n: "sb.feedbackForm", label: "Spätná väzba" },
    { key: "feedback", href: "/feedback", i18n: "sb.feedback", label: "Dotazník", questionnaireOnly: true },
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

  function render(student, pretestDone, isAdmin, questionnairePublished, sections, materialsCount) {
    const mount = document.getElementById("sidebar-mount");
    if (!mount) return;
    const active = mount.getAttribute("data-active") || "dashboard";

    // Ak je predtest hotový, odstráň ho z navigácie (už sa nedá opakovať)
    const sectionOff = (i) => !!(i.sectionKey && sections && sections[i.sectionKey] === false);
    const navItems = NAV.filter(i =>
      !(pretestDone && i.key === "pretest") &&
      !(i.questionnaireOnly && !questionnairePublished) &&
      !(i.materialsOnly && !materialsCount && !isAdmin) &&
      !(sectionOff(i) && !isAdmin));

    const linkHtml = item => `
      <a class="sidebar__link ${item.key === active ? "active" : ""}" href="${item.href}"${item.key === active ? ' aria-current="page"' : ""}>
        <span class="ic">${ICONS[item.key]}</span>
        <span data-i18n="${item.i18n}">${item.label}</span>
        ${sectionOff(item) ? '<span class="sidebar__tag" data-i18n="sb.hiddenTag" title="Skryté pre študentov">skryté</span>' : ""}
      </a>
    `;
    // Učenie (hlavné sekcie) a Ďalšie (spätná väzba, dotazník)
    const MORE_KEYS = ["feedbackForm", "feedback"];
    const learnItems = navItems.filter(i => !MORE_KEYS.includes(i.key));
    const moreItems = navItems.filter(i => MORE_KEYS.includes(i.key));
    const links = `
      <div class="sidebar__section-label" data-i18n="sb.learn">Učenie</div>
      ${learnItems.map(linkHtml).join("")}
      ${moreItems.length ? `<div class="sidebar__section-label" data-i18n="sb.more">Ďalšie</div>${moreItems.map(linkHtml).join("")}` : ""}
    `;

    // Mobilný tab bar: najdôležitejšie sekcie (zvyšok je v menu cez hamburger)
    const tabKeys = ["dashboard", pretestDone ? "ulohy" : "pretest", "exercises", "tests", "stats"];
    const tabItems = tabKeys
      .map(k => navItems.find(i => i.key === k))
      .filter(Boolean)
      .slice(0, 5);
    const tabbarHtml = `
      <nav class="tabbar" aria-label="Hlavné sekcie">
        ${tabItems.map(item => `
          <a class="tabbar__item ${item.key === active ? "active" : ""}" href="${item.href}"${item.key === active ? ' aria-current="page"' : ""}>
            ${ICONS[item.key]}
            <span data-i18n="${item.i18n}">${item.label}</span>
          </a>`).join("")}
      </nav>
    `;


    let adminHtml = "";
    if (isAdmin) {
      const adminNav = [
        { key: "adminUsers", href: "/admin-users", i18n: "sb.adminUsers", label: "Používatelia", active: "admin-users" },
        { key: "adminAssistant", href: "/admin-assistant", i18n: "sb.adminAssistant", label: "AI asistent", active: "admin-assistant" },
        { key: "adminExercises", href: "/admin-exercises", i18n: "sb.adminExercises", label: "Cvičenia (správa)", active: "admin-exercises" },
        { key: "adminTests", href: "/admin-tests", i18n: "sb.adminTests", label: "Testy (správa)", active: "admin-tests" },
        { key: "adminMaterials", href: "/admin-materials", i18n: "sb.adminMaterials", label: "Materiály (správa)", active: "admin-materials" },
        { key: "adminFeedback", href: "/admin-feedback", i18n: "sb.adminFeedback", label: "Dotazník a feedback", active: "admin-feedback" },
      ];
      const adminLinks = adminNav.map(item => `
        <a class="sidebar__link ${item.active === active ? "active" : ""}" href="${item.href}"${item.active === active ? ' aria-current="page"' : ""}>
          <span class="ic">${ICONS[item.key]}</span>
          <span data-i18n="${item.i18n}">${item.label}</span>
        </a>
      `).join("");
      adminHtml = `
        <div class="sidebar__section-label" data-i18n="sb.adminSection">Administrácia</div>
        ${adminLinks}
      `;
    }

    // Profil dole v sidebare (ako vo Finderi): avatar + meno + "Profil a nastavenia"
    let profileHtml = "";
    if (student) {
      const fullName = (student.name && student.surname)
        ? `${student.name} ${student.surname}`
        : (student.name || student.login || "");
      const initial = ((student.name || student.login || "?")[0] || "?").toUpperCase();
      profileHtml = `
        <a class="sidebar__profile${active === "profile" ? " active" : ""}" href="/profile" title="${student.login || ""}"${active === "profile" ? ' aria-current="page"' : ""}>
          <span class="sidebar__profile-avatar" aria-hidden="true">${initial}</span>
          <span class="sidebar__profile-info">
            <span class="sidebar__profile-name">${fullName}</span>
            <span class="sidebar__profile-sub" data-i18n="sb.profileSub">Profil a nastavenia</span>
          </span>
        </a>
      `;
    }

    const EXT_ICON = '<svg class="sidebar__ext" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17L17 7"/><path d="M8 7h9v9"/></svg>';

    mount.innerHTML = `
      <div class="sidebar-backdrop" id="sidebar-backdrop"></div>
      <aside class="sidebar" id="sidebar" aria-label="Menu">
        <a class="sidebar__brand" href="/">
          <img src="/assets/logo.svg" alt="" />
          <span>Adapt<span class="accent-py">Py</span></span>
        </a>
        <nav class="sidebar__nav">
          ${links}
          ${adminHtml}
        </nav>
        <div class="sidebar__spacer"></div>
        <div class="sidebar__footer">
          <a class="sidebar__link" href="https://github.com/ianmagyar/introduction-to-python" target="_blank" rel="noopener">
            <span class="ic">${ICONS.course}</span>
            <span data-i18n="sb.course">Stránka predmetu</span>
            ${EXT_ICON}
          </a>
          ${profileHtml}
        </div>
      </aside>
      ${tabbarHtml}
    `;

    const backdrop = document.getElementById("sidebar-backdrop");
    const sidebar = document.getElementById("sidebar");
    const setOpen = (open) => {
      sidebar.classList.toggle("open", open);
      backdrop.classList.toggle("show", open);
      document.querySelectorAll(".topbar-hamburger").forEach(b => b.setAttribute("aria-expanded", open ? "true" : "false"));
    };
    window.adaptpyToggleSidebar = function () {
      setOpen(!sidebar.classList.contains("open"));
    };
    if (backdrop) backdrop.addEventListener("click", () => setOpen(false));
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && sidebar.classList.contains("open")) setOpen(false);
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
    if (window.adaptpySessionGuard) {
      const ok = await window.adaptpySessionGuard();
      if (!ok) return; // guard už presmeroval
    }

    let student = null, pretestDone = false, isAdmin = false, questionnairePublished = false, sections = null,
        materialsCount = 0;
    if (window.adaptpyGetDashboard) {
      const dash = await window.adaptpyGetDashboard();
      if (dash && !dash._unauth) {
        student = dash.student || null;
        pretestDone = !!(dash.pretest && dash.pretest.done);
        isAdmin = !!dash.is_admin;
        questionnairePublished = !!dash.questionnaire_published;
        sections = dash.sections || null;
        materialsCount = dash.materials_count || 0;
      }
    } else {
      [student, pretestDone, isAdmin] = await Promise.all([fetchStudent(), fetchPretestDone(), fetchIsAdmin()]);
    }
    render(student, pretestDone, isAdmin, questionnairePublished, sections, materialsCount);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
