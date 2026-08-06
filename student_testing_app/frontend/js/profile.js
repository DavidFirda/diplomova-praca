/* AdaptPy - profil: načíta údaje, umožní ich upraviť (prázdne = nemení sa) */
(function () {
  function tr(key, fallback) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fallback;
  }

  async function load() {
    try {
      const r = await fetch("/api/auth/me", { credentials: "include" });
      if (r.status === 401) { window.location.href = "/login"; return; }
      const data = await r.json();
      const s = data.student || {};
      const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ""; };
      set("p-name", s.name);
      set("p-surname", s.surname);
      set("p-email", s.email);
      set("p-login", s.login);

      // Rola (len na zobrazenie)
      const role = (s.role || "user").toLowerCase();
      const roleLabel = document.getElementById("p-role-label");
      const roleBadge = document.getElementById("p-role-badge");
      if (roleLabel) {
        const key = role === "admin" ? "role.admin" : "role.user";
        let text = role;
        try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) text = v; } } catch (e) {}
        roleLabel.textContent = text;
        roleLabel.setAttribute("data-i18n", key);
      }
      if (roleBadge) {
        roleBadge.classList.toggle("role-badge--admin", role === "admin");
      }
    } catch (e) {
      window.location.href = "/login";
    }
  }

  async function save(e) {
    e.preventDefault();
    const errorMessage = document.getElementById("error-message");
    const infoMessage = document.getElementById("info-message");
    errorMessage.style.display = "none";
    infoMessage.style.display = "none";

    const payload = {
      name: document.getElementById("p-name").value,
      surname: document.getElementById("p-surname").value,
      email: document.getElementById("p-email").value,
      login: document.getElementById("p-login").value,
    };

    try {
      const r = await fetch("/api/auth/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
      const data = await r.json();
      if (r.ok) {
        infoMessage.innerText = tr("profile.saved", "Profil bol uložený.");
        infoMessage.style.display = "block";
        // aktualizuj polia podľa odpovede
        if (data.student) {
          document.getElementById("p-name").value = data.student.name || "";
          document.getElementById("p-surname").value = data.student.surname || "";
          document.getElementById("p-email").value = data.student.email || "";
          document.getElementById("p-login").value = data.student.login || "";
        }
      } else if (r.status === 401) {
        window.location.href = "/login";
      } else {
        errorMessage.innerText = data.error || tr("msg.serverError", "Chyba.");
        errorMessage.style.display = "block";
      }
    } catch (err) {
      errorMessage.innerText = tr("msg.serverError", "Chyba pripojenia k serveru.");
      errorMessage.style.display = "block";
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    load();
    const form = document.getElementById("profile-form");
    if (form) form.addEventListener("submit", save);
  });
})();
