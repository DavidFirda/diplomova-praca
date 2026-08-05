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
    "index.step3": "Spustí sa hlavný test – úlohy podľa tvojej výkonnosti.",
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
    "change.back": "Späť na dashboard",
    "change.forgot": "Zabudol si heslo?",
    "change.redirect": "Presmerúvam na dashboard…",

    // spoločné hlášky
    "msg.passwordsMismatch": "Heslá sa nezhodujú.",
    "msg.serverError": "Chyba pripojenia k serveru.",
    "msg.invalidLink": "Odkaz je neplatný. Vyžiadaj si prosím nový.",

    // prístupový modal
    "access.title": "Vstup do aplikácie",
    "access.placeholder": "Zadaj heslo",
    "access.submit": "Odomknúť",
    "access.error": "Nesprávne heslo",

    // sidebar
    "sb.dashboard": "Prehľad",
    "sb.pretest": "Predtest",
    "sb.tests": "Testy",
    "sb.stats": "Štatistika",
    "sb.profile": "Profil",
    "sb.feedback": "Dotazník",
    "sb.logout": "Odhlásiť sa",

    // chat
    "chat.title": "AdaptPy asistent",
    "chat.greeting": "Ahoj! Som tvoj AI asistent. Opýtaj sa ma na čokoľvek ohľadom Pythonu alebo tvojho progresu.",
    "chat.placeholder": "Napíš správu…",
    "chat.typing": "AdaptPy píše…",
    "chat.placeholderReply": "Zatiaľ som len ukážkový asistent 🙂 Čoskoro ma napojíme na vlastný model AdaptPy.",
    "chat.error": "Prepáč, niečo sa pokazilo. Skús to znova.",

    // dashboard
    "dash.welcome": "Vitaj späť",
    "dash.subtitle": "Tu je tvoj prehľad. Vyber si, čo chceš robiť.",
    "dash.pretest.title": "Predtest",
    "dash.pretest.desc": "Úvodný test, ktorý zistí tvoju úroveň. Spraví sa iba raz.",
    "dash.pretest.start": "Spustiť predtest",
    "dash.pretest.done": "Predtest dokončený",
    "dash.pretest.locked": "Najprv dokonči predtest",
    "dash.main.title": "Hlavné testy",
    "dash.main.desc": "Adaptívne testy podľa tvojej výkonnosti. Môžeš ich spraviť viac.",
    "dash.main.start": "Spustiť nový test",
    "dash.main.count": "Absolvované testy",
    "dash.stats.title": "Moja štatistika",
    "dash.stats.desc": "Pozri si svoj progres a úspešnosť.",
    "dash.stats.open": "Zobraziť štatistiku",
    "dash.stats.accuracy": "Úspešnosť",
    "dash.stats.answers": "Odpovede",
    "dash.profile.title": "Môj profil",
    "dash.profile.desc": "Uprav svoje údaje a heslo.",
    "dash.profile.open": "Spravovať profil",
    "dash.feedback.title": "Dotazník",
    "dash.feedback.desc": "Podeľ sa o spätnú väzbu a pomôž nám aplikáciu zlepšiť.",
    "dash.feedback.open": "Vyplniť dotazník",
    "dash.feedback.done": "Dotazník vyplnený",

    // profil
    "profile.title": "Môj profil",
    "profile.subtitle": "Uprav svoje údaje. Prázdne pole ostane nezmenené.",
    "profile.name": "Meno",
    "profile.surname": "Priezvisko",
    "profile.email": "Email",
    "profile.login": "Login",
    "profile.save": "Uložiť zmeny",
    "profile.saved": "Profil bol uložený.",
    "profile.changePassword": "Zmeniť heslo",
    "profile.back": "Späť na dashboard",
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
    "change.back": "Back to dashboard",
    "change.forgot": "Forgot your password?",
    "change.redirect": "Redirecting to dashboard…",

    "msg.passwordsMismatch": "Passwords do not match.",
    "msg.serverError": "Server connection error.",
    "msg.invalidLink": "The link is invalid. Please request a new one.",

    "access.title": "Enter the app",
    "access.placeholder": "Enter password",
    "access.submit": "Unlock",
    "access.error": "Incorrect password",

    "sb.dashboard": "Overview",
    "sb.pretest": "Pre-test",
    "sb.tests": "Tests",
    "sb.stats": "Statistics",
    "sb.profile": "Profile",
    "sb.feedback": "Feedback",
    "sb.logout": "Sign out",

    "chat.title": "AdaptPy assistant",
    "chat.greeting": "Hi! I'm your AI assistant. Ask me anything about Python or your progress.",
    "chat.placeholder": "Type a message…",
    "chat.typing": "AdaptPy is typing…",
    "chat.placeholderReply": "I'm just a demo assistant for now 🙂 We'll soon connect me to a custom AdaptPy model.",
    "chat.error": "Sorry, something went wrong. Please try again.",

    "dash.welcome": "Welcome back",
    "dash.subtitle": "Here's your overview. Choose what you'd like to do.",
    "dash.pretest.title": "Pre-test",
    "dash.pretest.desc": "An initial test to assess your level. Taken only once.",
    "dash.pretest.start": "Start pre-test",
    "dash.pretest.done": "Pre-test completed",
    "dash.pretest.locked": "Complete the pre-test first",
    "dash.main.title": "Main tests",
    "dash.main.desc": "Adaptive tests based on your performance. You can take several.",
    "dash.main.start": "Start a new test",
    "dash.main.count": "Completed tests",
    "dash.stats.title": "My statistics",
    "dash.stats.desc": "See your progress and accuracy.",
    "dash.stats.open": "View statistics",
    "dash.stats.accuracy": "Accuracy",
    "dash.stats.answers": "Answers",
    "dash.profile.title": "My profile",
    "dash.profile.desc": "Edit your details and password.",
    "dash.profile.open": "Manage profile",
    "dash.feedback.title": "Questionnaire",
    "dash.feedback.desc": "Share your feedback and help us improve the app.",
    "dash.feedback.open": "Fill in the questionnaire",
    "dash.feedback.done": "Questionnaire completed",

    "profile.title": "My profile",
    "profile.subtitle": "Edit your details. Empty fields stay unchanged.",
    "profile.name": "First name",
    "profile.surname": "Last name",
    "profile.email": "Email",
    "profile.login": "Login",
    "profile.save": "Save changes",
    "profile.saved": "Profile saved.",
    "profile.changePassword": "Change password",
    "profile.back": "Back to dashboard",
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
