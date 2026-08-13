// Pomocník na preklad hlášok (funguje aj keď i18n.js nie je načítaný)
function tr(key, fallback) {
  try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
  return fallback;
}

async function changePassword() {
    const currentPassword = document.getElementById("current_password").value;
    const newPassword = document.getElementById("new_password").value;
    const newPasswordConfirm = document.getElementById("new_password_confirm").value;
    const errorMessage = document.getElementById("error-message");
    const infoMessage = document.getElementById("info-message");
    errorMessage.style.display = "none";
    infoMessage.style.display = "none";

    if (newPassword !== newPasswordConfirm) {
        errorMessage.innerText = tr("msg.passwordsMismatch", "Nové heslá sa nezhodujú.");
        errorMessage.style.display = "block";
        return;
    }

    try {
        const response = await fetch("/api/auth/change-password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });

        const data = await response.json();

        if (response.ok) {
            infoMessage.innerText = data.message + " " + tr("change.redirect", "Presmerúvam na dashboard…");
            infoMessage.style.display = "block";
            document.getElementById("change-password-form").reset();
            setTimeout(() => { window.location.href = "/dashboard"; }, 1500);
        } else if (response.status === 401) {
            errorMessage.innerText = "Nie si prihlásený, alebo je aktuálne heslo nesprávne. Prihlás sa prosím znova.";
            errorMessage.style.display = "block";
        } else {
            errorMessage.innerText = data.error || "Neznáma chyba.";
            errorMessage.style.display = "block";
        }
    } catch (error) {
        errorMessage.innerText = tr("msg.serverError", "Chyba pripojenia k serveru.");
        errorMessage.style.display = "block";
    }
}

window.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("change-password-form");
    if (form) {
        form.addEventListener("submit", (e) => {
            e.preventDefault();
            changePassword();
        });
    }
});
