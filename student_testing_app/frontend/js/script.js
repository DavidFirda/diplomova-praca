// Pomocník na preklad hlášok (funguje aj keď i18n.js nie je načítaný)
function tr(key, fallback) {
  try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
  return fallback;
}

function checkAccessCode() {
    const access = sessionStorage.getItem("access_granted");
    if (!access || access !== "true") {
      if (window.location.pathname !== "/") {
        // ❌ Ak nie je povolený prístup a nie sme na indexe, presmeruj späť
        window.location.href = "/";
      } else {
        showPasswordPrompt();
      }
    }
  }
  
  function showPasswordPrompt() {
    if (document.getElementById("access-overlay")) return;

    const overlay = document.createElement("div");
    overlay.id = "access-overlay";
    overlay.style.cssText = `
      position: fixed; inset: 0;
      background: rgba(8, 12, 18, 0.6);
      backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
      display: flex; justify-content: center; align-items: center;
      z-index: 9999; padding: 20px;
    `;

    overlay.innerHTML = `
      <div style="
        background: var(--surface);
        border: 1px solid var(--border);
        padding: 32px 28px;
        border-radius: var(--radius-lg);
        box-shadow: var(--shadow-lg);
        text-align: center;
        width: 100%; max-width: 340px;
      ">
        <img src="/assets/logo.svg" alt="AdaptPy" width="52" height="52"
             style="border-radius:14px; box-shadow: var(--shadow-md); margin-bottom: 14px;" />
        <h2 style="margin: 0 0 18px; color: var(--text); font-size: 1.3rem;" data-i18n="access.title">${tr("access.title", "Vstup do aplikácie")}</h2>
        <input type="password" id="popup-password" data-i18n-placeholder="access.placeholder"
               placeholder="${tr("access.placeholder", "Zadaj heslo")}"
               onkeydown="if(event.key==='Enter'){validateAccess();}" />
        <button onclick="validateAccess()" data-i18n="access.submit">${tr("access.submit", "Odomknúť")}</button>
        <p id="popup-error" class="error-message" style="display:none; margin-top: 12px;" data-i18n="access.error">${tr("access.error", "Nesprávne heslo")}</p>
      </div>
    `;

    document.body.appendChild(overlay);
    if (typeof I18N !== "undefined") I18N.apply();
    const input = document.getElementById("popup-password");
    if (input) input.focus();
  }
  
  function validateAccess() {
    const password = document.getElementById("popup-password").value;
    console.log("Zadané:", password);
    console.log("Načítané ACCESS_CODE:", ACCESS_CODE);
    if (typeof ACCESS_CODE !== "undefined" && password === ACCESS_CODE) {
      sessionStorage.setItem("access_granted", "true");
      location.reload();
    } else {
      document.getElementById("popup-error").style.display = "block";
    }
  }

// LOGIN funkcia
async function login() {
    let loginInput = document.getElementById("login").value;
    let passwordInput = document.getElementById("password").value;
    let errorMessage = document.getElementById("error-message");

    try {
        let response = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ login: loginInput, password: passwordInput })
        });

        let data = await response.json();

        if (response.ok && data.student) {
            localStorage.setItem("student_id", data.student.id);
            // Značka pre túto kartu - session-guard podľa nej pozná,
            // že karta nebola medzičasom zatvorená.
            if (window.adaptpyMarkTabSession) window.adaptpyMarkTabSession();
            // Po prihlásení ide používateľ na dashboard (rozcestník),
            // nie automaticky do testu.
            window.location.href = "/dashboard";
        } else {
            errorMessage.innerText = data.error || "Neznáma chyba.";
            errorMessage.style.display = "block";
        }
    } catch (error) {
        errorMessage.innerText = tr("msg.serverError", "Chyba pripojenia k serveru.");
        errorMessage.style.display = "block";
    }
}

// REGISTRÁCIA funkcia
async function register() {
    let nameInput = document.getElementById("name").value;
    let surnameInput = document.getElementById("surname").value;
    let emailInput = document.getElementById("email").value;
    let loginInput = document.getElementById("login").value;
    let passwordInput = document.getElementById("password").value;
    let errorMessage = document.getElementById("error-message");

    try {
        let response = await fetch("/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
                name: nameInput,
                surname: surnameInput,
                email: emailInput,
                login: loginInput,
                password: passwordInput
            })
        });

        let data = await response.json();

        if (response.ok && data.student) {
            alert("Registrácia úspešná! Teraz sa môžeš prihlásiť.");
            window.location.href = "/login";
        } else {
            errorMessage.innerText = data.error || "Neznáma chyba.";
            errorMessage.style.display = "block";
        }
    } catch (error) {
        errorMessage.innerText = tr("msg.serverError", "Chyba pripojenia k serveru.");
        errorMessage.style.display = "block";
    }
}

// ZABUDNUTÉ HESLO - žiadosť o reset link na email
async function forgotPassword() {
    let emailInput = document.getElementById("email").value;
    let errorMessage = document.getElementById("error-message");
    let infoMessage = document.getElementById("info-message");
    errorMessage.style.display = "none";
    infoMessage.style.display = "none";

    try {
        let response = await fetch("/api/auth/forgot-password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: emailInput })
        });

        let data = await response.json();

        if (response.ok) {
            infoMessage.innerText = data.message;
            infoMessage.style.display = "block";
        } else {
            errorMessage.innerText = data.error || "Neznáma chyba.";
            errorMessage.style.display = "block";
        }
    } catch (error) {
        errorMessage.innerText = tr("msg.serverError", "Chyba pripojenia k serveru.");
        errorMessage.style.display = "block";
    }
}

// NOVÉ HESLO - nastavenie hesla cez token z emailu
async function resetPassword() {
    let newPassword = document.getElementById("new_password").value;
    let newPasswordConfirm = document.getElementById("new_password_confirm").value;
    let errorMessage = document.getElementById("error-message");
    let infoMessage = document.getElementById("info-message");
    errorMessage.style.display = "none";
    infoMessage.style.display = "none";

    if (newPassword !== newPasswordConfirm) {
        errorMessage.innerText = tr("msg.passwordsMismatch", "Heslá sa nezhodujú.");
        errorMessage.style.display = "block";
        return;
    }

    const params = new URLSearchParams(window.location.search);
    const uid = params.get("uid");
    const tokenParam = params.get("token");

    if (!uid || !tokenParam) {
        errorMessage.innerText = tr("msg.invalidLink", "Odkaz je neplatný. Vyžiadaj si prosím nový.");
        errorMessage.style.display = "block";
        return;
    }

    try {
        let response = await fetch("/api/auth/reset-password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ uid: uid, token: tokenParam, new_password: newPassword })
        });

        let data = await response.json();

        if (response.ok) {
            infoMessage.innerText = data.message + " Presmerúvam ťa na prihlásenie...";
            infoMessage.style.display = "block";
            setTimeout(() => { window.location.href = "/login"; }, 2000);
        } else {
            errorMessage.innerText = data.error || "Neznáma chyba.";
            errorMessage.style.display = "block";
        }
    } catch (error) {
        errorMessage.innerText = tr("msg.serverError", "Chyba pripojenia k serveru.");
        errorMessage.style.display = "block";
    }
}

// Pridanie event listenerov pri načítaní stránky
window.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById("login-form");
    if (loginForm) {
        loginForm.addEventListener("submit", (e) => {
            e.preventDefault();
            login();
        });
    }

    const registerForm = document.getElementById("register-form");
    if (registerForm) {
        registerForm.addEventListener("submit", (e) => {
            e.preventDefault();
            register();
        });
    }

    const forgotPasswordForm = document.getElementById("forgot-password-form");
    if (forgotPasswordForm) {
        forgotPasswordForm.addEventListener("submit", (e) => {
            e.preventDefault();
            forgotPassword();
        });
    }

    const resetPasswordForm = document.getElementById("reset-password-form");
    if (resetPasswordForm) {
        resetPasswordForm.addEventListener("submit", (e) => {
            e.preventDefault();
            resetPassword();
        });
    }
});