function checkAccessCode() {
    const access = sessionStorage.getItem("access_granted");
    if (!access || access !== "true") {
      if (window.location.pathname !== "/index.html" && window.location.pathname !== "/") {
        // ❌ Ak nie je povolený prístup a nie sme na indexe, presmeruj späť
        window.location.href = "/index.html";
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
    let errorMessage = document.getElementById("error-message");

    try {
        let response = await fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ login: loginInput })
        });

        let data = await response.json();

        if (response.ok && data.id) {
            localStorage.setItem("student_id", data.id);

            const statsResp = await fetch("/admin/students/summary?token="+ token);
            const stats = await statsResp.json();
            const current = stats.find(s => s.id === data.id);

            if (current && current.predtest.total_answers > 0) {
                localStorage.setItem("test_categories", JSON.stringify(["Sorting", "Syntax", "Data Structures","Scientific Computing"])); // alebo tvoje kategórie
                localStorage.removeItem("main_test_session");
                window.location.href = "/hlavnytest.html";
            } else {
                window.location.href = "predtest.html";
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
    let loginInput = document.getElementById("login").value;
    let errorMessage = document.getElementById("error-message");

    try {
        let response = await fetch("/api/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: nameInput, login: loginInput })
        });

        let data = await response.json();

        if (response.ok && data.id) {
            alert("Registrácia úspešná!");
            window.location.href = "login.html";
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
});