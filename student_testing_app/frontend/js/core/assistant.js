/* ============================================================
   AdaptPy - asistent: spoločný komponent (Úlohy aj dashboard).

   Stará sa o všetko okolo okna: ikona robota (FAB), otvorenie/minimalizovanie
   s animáciou (CSS triedy), Esc, bubliny správ, indikátor písania a odoslanie
   formulára. Čo asistent odpovedá, rieši stránka (callback onSubmit):
     - Úlohy: backend /api/ulohy/agent (nápoveda, vysvetlenie chyby),
     - Dashboard: všeobecná orientácia v aplikácii.

   Markup: pozri pages/ulohy.html alebo pages/dashboard.html (rovnaké id: agent-*).
   Štýly: css/parts/13-assistant.css.
   ============================================================ */
window.AdaptAssistant = (function () {
  const ROBOT = '<svg class="ul-icon" aria-hidden="true"><use href="#ul-robot"/></svg>';

  function timeNow() {
    const lang = (typeof I18N !== "undefined" && I18N.lang) || "sk";
    return new Date().toLocaleTimeString(lang === "sk" ? "sk-SK" : "en-GB", { hour: "2-digit", minute: "2-digit" });
  }

  /**
   * @param {Object}   o
   * @param {Function} [o.onSubmit]    volá sa s textom, ktorý študent napísal
   * @param {Function} [o.canShowFab]  smie sa ikona po minimalizovaní zobraziť? (predvolene áno)
   */
  function create(o) {
    const fab = document.getElementById("agent-fab");
    const panel = document.getElementById("agent-panel");
    const minBtn = document.getElementById("agent-minimize");
    const box = document.getElementById("agent-messages");
    const form = document.getElementById("agent-form");
    const input = document.getElementById("agent-input");
    if (!fab || !panel || !box) return null;
    const canShowFab = o.canShowFab || (() => true);

    const isOpen = () => panel.classList.contains("is-open");
    const scrollDown = () => { box.scrollTop = box.scrollHeight; };
    // Rezerva pod obsahom (CSS), aby ikona neprekrývala koniec stránky.
    const syncBody = () =>
      document.body.classList.toggle("has-assistant", fab.classList.contains("is-visible") || isOpen());

    function setFab(visible, pulsing = false) {
      fab.classList.toggle("is-visible", visible);
      fab.classList.toggle("is-pulsing", visible && pulsing);
      syncBody();
    }

    function open() {
      panel.classList.add("is-open");
      panel.setAttribute("aria-hidden", "false");
      fab.setAttribute("aria-expanded", "true");
      setFab(false);
      syncBody();
      scrollDown();
      if (input) setTimeout(() => input.focus({ preventScroll: true }), 300);
    }

    // minimalizovanie = okno sa zmenší späť do ikony robota (správy ostávajú)
    function minimize() {
      panel.classList.remove("is-open");
      panel.setAttribute("aria-hidden", "true");
      fab.setAttribute("aria-expanded", "false");
      setFab(!!canShowFab());
    }

    // schová okno aj ikonu (asistent teraz nie je k dispozícii)
    function hide() {
      panel.classList.remove("is-open");
      panel.setAttribute("aria-hidden", "true");
      fab.setAttribute("aria-expanded", "false");
      setFab(false);
    }

    function addMessage(who, text, withTime = true) {
      const row = document.createElement("div");
      row.className = `ul-row ul-row--${who}`;
      if (who === "agent") {
        const av = document.createElement("div");
        av.className = "ul-avatar";
        av.innerHTML = ROBOT;
        row.appendChild(av);
      }
      const wrap = document.createElement("div");
      wrap.className = "ul-bubble-wrap";
      const bubble = document.createElement("div");
      bubble.className = `ul-msg ul-msg--${who}`;
      bubble.textContent = text;
      wrap.appendChild(bubble);
      if (withTime) {
        const time = document.createElement("span");
        time.className = "ul-time";
        time.textContent = timeNow();
        wrap.appendChild(time);
      }
      row.appendChild(wrap);
      box.appendChild(row);
      scrollDown();
      return bubble;
    }

    function showTyping() {
      hideTyping();
      const row = document.createElement("div");
      row.className = "ul-row ul-row--agent";
      row.id = "agent-typing";
      row.innerHTML = `<div class="ul-avatar">${ROBOT}</div>
        <div class="ul-bubble-wrap"><div class="ul-msg ul-msg--agent ul-typing"><i></i><i></i><i></i></div></div>`;
      box.appendChild(row);
      scrollDown();
    }
    function hideTyping() {
      const el = document.getElementById("agent-typing");
      if (el) el.remove();
    }

    fab.addEventListener("click", open);
    if (minBtn) minBtn.addEventListener("click", minimize);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && isOpen()) minimize();
    });
    if (form && input) {
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        input.value = "";
        if (o.onSubmit) o.onSubmit(text);
      });
    }

    return { open, minimize, hide, setFab, isOpen, addMessage, showTyping, hideTyping, scrollDown };
  }

  return { create };
})();
