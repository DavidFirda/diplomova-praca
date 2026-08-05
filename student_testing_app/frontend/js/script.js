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
    const overlay = document.createElement("div");
    overlay.style.cssText = `
      position: fixed; top: 0; left: 0; width: 100%; height: 100%;
      background-color: rgba(0,0,0,0.5);
      display: flex; justify-content: center; align-items: center;
      z-index: 9999;
    `;
  
    overlay.innerHTML = `
      <div style="
        background: white;
        padding: 30px;
        border-radius: 10px;
        box-shadow: 0 0 20px rgba(0,0,0,0.3);
        text-align: center;
        width: 300px;
      ">
        <h2>Vstup do aplikácie</h2>
        <input type="password" id="popup-password" placeholder="Zadaj heslo" style="
          width: 93%;
          padding: 10px;
          margin: 15px 0;
          border: 1px solid #ccc;
          border-radius: 5px;
        " />
        <button onclick="validateAccess()" style="
          padding: 10px 20px;
          background: #1c3f60;
          color: white;
          border: none;
          border-radius: 5px;
          cursor: pointer;
        ">Odomknúť</button>
        <p id="popup-error" style="color: red; display: none; margin-top: 10px;">❌ Nesprávne heslo</p>
      </div>
    `;
  
    document.body.appendChild(overlay);
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

            const statsResp = await fetch("/admin/students/summary?token=" + token);
            const stats = await statsResp.json();
            const current = stats.find(s => s.id === data.student.id);

            if (current && current.predtest.total_answers > 0) {
                localStorage.setItem("test_categories", JSON.stringify(["Sorting", "Syntax", "Data Structures", "Scientific Computing"]));
                localStorage.removeItem("main_test_session");
                window.location.href = "/hlavnytest";
            } else {
                window.location.href = "/predtest";
            }
        } else {
            errorMessage.innerText = data.error || "Neznáma chyba.";
            errorMessage.style.display = "block";
        }
    } catch (error) {
        errorMessage.innerText = "Chyba pripojenia k serveru.";
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
        errorMessage.innerText = "Chyba pripojenia k serveru.";
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
        errorMessage.innerText = "Chyba pripojenia k serveru.";
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
        errorMessage.innerText = "Heslá sa nezhodujú.";
        errorMessage.style.display = "block";
        return;
    }

    const params = new URLSearchParams(window.location.search);
    const uid = params.get("uid");
    const tokenParam = params.get("token");

    if (!uid || !tokenParam) {
        errorMessage.innerText = "Odkaz na reset hesla je neplatný. Vyžiadaj si prosím nový.";
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
        errorMessage.innerText = "Chyba pripojenia k serveru.";
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