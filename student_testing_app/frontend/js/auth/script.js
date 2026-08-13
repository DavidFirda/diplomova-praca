// Pomocník na preklad hlášok (funguje aj keď i18n.js nie je načítaný)
function tr(key, fallback) {
  try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
  return fallback;
}

// Preloží chybovú hlášku zo servera: ak má error_key, použije i18n preklad,
// inak zobrazí surový text (data.error / data.message) alebo generickú chybu.
function adaptpyErrText(data) {
  if (data && data.error_key) {
    const t = tr(data.error_key, null);
    if (t) return t;
  }
  return (data && (data.error || data.message)) || tr("msg.unknownError", "Neznáma chyba.");
}

// Naformátuje sekundy na "M:SS" (napr. 125 -> "2:05").
function adaptpyFmtTime(secs) {
  secs = Math.max(0, Math.floor(secs));
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return m + ":" + (s < 10 ? "0" : "") + s;
}

// Spustí odpočet po prekročení limitu: zablokuje tlačidlo a nad chybovou
// hláškou zobrazí časovač, dokedy sa nedá skúsiť znova. Po vypršaní tlačidlo
// znova povolí. Funguje v SK aj EN (texty cez i18n).
let _adaptpyLockoutTimer = null;
// Kľúč v localStorage, kam sa uloží čas (timestamp ms), dokedy trvá blokovanie.
var ADAPTPY_LOCKOUT_KEY = "adaptpy_login_lockout_until";

function adaptpyStartLockout(seconds, buttonId, buttonI18nKey, skipStore) {
  const errorMessage = document.getElementById("error-message");
  const btn = document.getElementById(buttonId);
  let remaining = Math.max(1, parseInt(seconds, 10) || 60);

  // ulož čas konca blokovania, aby prežil refresh stránky
  if (!skipStore) {
    try {
      localStorage.setItem(ADAPTPY_LOCKOUT_KEY, String(Date.now() + remaining * 1000));
    } catch (e) {}
  }

  if (_adaptpyLockoutTimer) clearInterval(_adaptpyLockoutTimer);

  // zablokuj tlačidlo
  if (btn) {
    btn.disabled = true;
    btn.style.opacity = "0.6";
    btn.style.cursor = "not-allowed";
  }

  function render() {
    if (errorMessage) {
      const line1 = tr("auth.retryIn", "Skús to znova o") + " " + adaptpyFmtTime(remaining);
      const line2 = tr("auth.tooManyLogin", "Príliš veľa pokusov o prihlásenie.");
      errorMessage.innerHTML =
        '<span style="font-weight:600;font-variant-numeric:tabular-nums;">' + line1 + "</span><br>" + line2;
      errorMessage.style.display = "block";
    }
  }
  render();

  _adaptpyLockoutTimer = setInterval(function () {
    remaining -= 1;
    if (remaining <= 0) {
      clearInterval(_adaptpyLockoutTimer);
      _adaptpyLockoutTimer = null;
      try { localStorage.removeItem(ADAPTPY_LOCKOUT_KEY); } catch (e) {}
      if (btn) {
        btn.disabled = false;
        btn.style.opacity = "";
        btn.style.cursor = "";
      }
      if (errorMessage) {
        errorMessage.innerText = tr("auth.canRetryNow", "Teraz to môžeš skúsiť znova.");
      }
      return;
    }
    render();
  }, 1000);
}

// Pri načítaní stránky obnoví časovač, ak blokovanie ešte trvá (prežije refresh).
function adaptpyRestoreLockout(buttonId) {
  try {
    const until = parseInt(localStorage.getItem(ADAPTPY_LOCKOUT_KEY), 10);
    if (!until) return;
    const remainingMs = until - Date.now();
    if (remainingMs > 0) {
      adaptpyStartLockout(Math.ceil(remainingMs / 1000), buttonId, "login.submit", true);
    } else {
      localStorage.removeItem(ADAPTPY_LOCKOUT_KEY);
    }
  } catch (e) {}
}

// Po načítaní stránky skús obnoviť prípadný bežiaci lockout na login tlačidle.
document.addEventListener("DOMContentLoaded", function () {
  if (document.getElementById("loginButton")) {
    adaptpyRestoreLockout("loginButton");
  }
});

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
        } else if (response.status === 429) {
            // Príliš veľa pokusov - spusti odpočet a zablokuj tlačidlo
            adaptpyStartLockout(data.retry_after || 60, "loginButton", "login.submit");
        } else {
            errorMessage.innerText = adaptpyErrText(data);
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
            errorMessage.innerText = adaptpyErrText(data);
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
            let msg = data.message;
            if (data.message_key && typeof I18N !== "undefined") {
                const t = I18N.t(data.message_key);
                if (t && t !== data.message_key) msg = t;
            }
            infoMessage.innerText = msg;
            infoMessage.style.display = "block";
        } else {
            errorMessage.innerText = adaptpyErrText(data);
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
            errorMessage.innerText = adaptpyErrText(data);
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