/* ============================================================
   AdaptPy - i18n + prepínač témy
   - Slovník SK/EN, preklad cez atribút data-i18n
   - Uloženie voľby jazyka a témy do localStorage
   ============================================================ */

const TRANSLATIONS = {
  sk: {
    "nav.login": "Prihlásiť sa",
    "nav.logout": "Odhlásiť sa",
    "nav.theme": "Téma",

    // index
    "index.title": "Vitaj v Adapt<span class=\"accent-py\">Py</span>",
    "index.subtitle": "Adaptívne precvičovanie programovania v Pythone",
    "index.intro": "AdaptPy je nástroj pre personalizovanú výučbu programovania v jazyku Python. Systém sa prispôsobuje tvojej úrovni a dáva ti úlohy, ktoré ťa posúvajú vpred.",
    "index.how": "Ako to funguje",
    "index.step1": "Zaregistruj sa alebo sa prihlás.",
    "index.step2": "Vyplň krátky predtest, aby systém spoznal tvoje znalosti.",
    "index.step3": "Spusti hlavný test – úlohy podľa tvojej výkonnosti.",
    "index.step4": "Po dokončení testu uvidíš štatistiky svojho progresu.",
    "index.step5": "Nakoniec vyplň krátky dotazník spätnej väzby.",
    "index.cta": "Začať",
    "index.thesis": "Aplikácia vznikla ako súčasť diplomovej práce na Technickej univerzite v Košiciach, Fakulte elektrotechniky a informatiky.",

    // login
    "login.title": "Prihlásenie",
    "login.identifier": "Login alebo email",
    "login.password": "Heslo",
    "login.submit": "Prihlásiť sa",
    "login.forgot": "Zabudol si heslo?",
    "login.noAccount": "Nemáš účet? Zaregistruj sa",

    // register
    "register.title": "Registrácia",
    "register.name": "Meno",
    "register.surname": "Priezvisko",
    "register.email": "Email",
    "register.login": "Login",
    "register.password": "Heslo (min. 8 znakov)",
    "register.submit": "Zaregistrovať sa",
    "register.hasAccount": "Už máš účet? Prihlás sa",

    // forgot
    "forgot.title": "Zabudnuté heslo",
    "forgot.desc": "Zadaj email, na ktorý si sa registroval. Pošleme ti naň odkaz na nastavenie nového hesla.",
    "forgot.email": "Email",
    "forgot.submit": "Odoslať odkaz na reset",
    "forgot.back": "Späť na prihlásenie",

    // reset
    "reset.title": "Nové heslo",
    "reset.new": "Nové heslo (min. 8 znakov)",
    "reset.confirm": "Zopakuj nové heslo",
    "reset.submit": "Nastaviť nové heslo",
    "reset.back": "Späť na prihlásenie",

    // change
    "change.title": "Zmena hesla",
    "change.current": "Aktuálne heslo",
    "change.new": "Nové heslo (min. 8 znakov)",
    "change.confirm": "Zopakuj nové heslo",
    "change.submit": "Zmeniť heslo",
    "change.back": "Späť",

    // spoločné hlášky
    "msg.passwordsMismatch": "Heslá sa nezhodujú.",
    "msg.serverError": "Chyba pripojenia k serveru.",
    "msg.invalidLink": "Odkaz je neplatný. Vyžiadaj si prosím nový.",

    // prístupový modal
    "access.title": "Vstup do aplikácie",
    "access.placeholder": "Zadaj heslo",
    "access.submit": "Odomknúť",
    "access.error": "Nesprávne heslo",
  },

  en: {
    "nav.login": "Sign in",
    "nav.logout": "Sign out",
    "nav.theme": "Theme",

    "index.title": "Welcome to Adapt<span class=\"accent-py\">Py</span>",
    "index.subtitle": "Adaptive Python programming practice",
    "index.intro": "AdaptPy is a tool for personalized Python programming education. The system adapts to your level and gives you tasks that move you forward.",
    "index.how": "How it works",
    "index.step1": "Sign up or sign in.",
    "index.step2": "Complete a short pre-test so the system can assess your knowledge.",
    "index.step3": "Start the main test – tasks tailored to your performance.",
    "index.step4": "After finishing, you'll see statistics of your progress.",
    "index.step5": "Finally, fill in a short feedback questionnaire.",
    "index.cta": "Get started",
    "index.thesis": "This application was created as part of a master's thesis at the Technical University of Košice, Faculty of Electrical Engineering and Informatics.",

    "login.title": "Sign in",
    "login.identifier": "Login or email",
    "login.password": "Password",
    "login.submit": "Sign in",
    "login.forgot": "Forgot your password?",
    "login.noAccount": "No account? Sign up",

    "register.title": "Sign up",
    "register.name": "First name",
    "register.surname": "Last name",
    "register.email": "Email",
    "register.login": "Login",
    "register.password": "Password (min. 8 chars)",
    "register.submit": "Create account",
    "register.hasAccount": "Already have an account? Sign in",

    "forgot.title": "Forgot password",
    "forgot.desc": "Enter the email you registered with. We'll send you a link to set a new password.",
    "forgot.email": "Email",
    "forgot.submit": "Send reset link",
    "forgot.back": "Back to sign in",

    "reset.title": "New password",
    "reset.new": "New password (min. 8 chars)",
    "reset.confirm": "Repeat new password",
    "reset.submit": "Set new password",
    "reset.back": "Back to sign in",

    "change.title": "Change password",
    "change.current": "Current password",
    "change.new": "New password (min. 8 chars)",
    "change.confirm": "Repeat new password",
    "change.submit": "Change password",
    "change.back": "Back",

    "msg.passwordsMismatch": "Passwords do not match.",
    "msg.serverError": "Server connection error.",
    "msg.invalidLink": "The link is invalid. Please request a new one.",

    "access.title": "Enter the app",
    "access.placeholder": "Enter password",
    "access.submit": "Unlock",
    "access.error": "Incorrect password",
  },
};

const I18N = {
  lang: localStorage.getItem("adeptpy_lang") || "sk",

  t(key) {
    return (TRANSLATIONS[this.lang] && TRANSLATIONS[this.lang][key]) || key;
  },

  apply() {
    document.documentElement.lang = this.lang;
    // textový obsah
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = this.t(el.getAttribute("data-i18n"));
    });
    // HTML obsah (len pre naše statické preklady - napr. brandované "AdaptPy" s farebným Py)
    document.querySelectorAll("[data-i18n-html]").forEach((el) => {
      el.innerHTML = this.t(el.getAttribute("data-i18n-html"));
    });
    // placeholdery
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.placeholder = this.t(el.getAttribute("data-i18n-placeholder"));
    });
    // aktívny stav prepínača jazyka
    document.querySelectorAll(".lang-switch button").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.lang === this.lang);
    });
  },

  setLang(lang) {
    this.lang = lang;
    localStorage.setItem("adeptpy_lang", lang);
    this.apply();
  },
};

const THEME = {
  current: localStorage.getItem("adeptpy_theme") ||
           (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"),

  apply() {
    document.documentElement.setAttribute("data-theme", this.current);
    const icon = document.getElementById("theme-icon");
    if (icon) icon.textContent = this.current === "dark" ? "☀️" : "🌙";
  },

  toggle() {
    this.current = this.current === "dark" ? "light" : "dark";
    localStorage.setItem("adeptpy_theme", this.current);
    this.apply();
  },
};

// Aplikuj tému čo najskôr (zabráni bliknutiu)
THEME.apply();

// Event delegation - funguje aj pre tlačidlá, ktoré navbar.js vloží až po DOMContentLoaded
document.addEventListener("click", (e) => {
  const langBtn = e.target.closest(".lang-switch button");
  if (langBtn && langBtn.dataset.lang) {
    I18N.setLang(langBtn.dataset.lang);
    return;
  }
  const themeBtn = e.target.closest("#theme-toggle");
  if (themeBtn) {
    THEME.toggle();
  }
});

// Keď navbar.js vloží obsah, znova aplikuj preklady a stav prepínačov.
// (navbar.js beží synchrónne pri načítaní, takže po DOMContentLoaded je už v DOM.)
document.addEventListener("DOMContentLoaded", () => {
  I18N.apply();
  THEME.apply();
});

// Poistka: ak sa navbar vloží až po týchto volaniach, aplikuj ešte raz na konci event loopu
window.addEventListener("load", () => {
  I18N.apply();
  THEME.apply();
});
