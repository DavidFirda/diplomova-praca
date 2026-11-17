/* ============================================================
   AdaptPy - dashboard: AI asistent pre orientáciu v aplikácii.

   Odpovedá jazykový model (/api/assistant/stream, režim "dashboard"): ako funguje
   aplikácia z pohľadu študenta, jeho štatistiky, čo robiť ďalej, odkazy na cvičenia
   a prednášky. Nikdy nič o kóde aplikácie, admin rozhraní ani heslách (kontroluje
   to aj strážca na serveri). História sa obnoví z DB.

   Okno a ikonu rieši js/core/assistant.js, bubliny a streamovanie js/core/ai_chat.js.
   Ak model nie je dostupný, tlačidlá odpovedia pôvodnými statickými textami.
   ============================================================ */
(function () {
  if (typeof AdaptAssistant === "undefined" || typeof AiChat === "undefined") return;

  const tr = (key, fb) => {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  };

  let busy = false;
  const assistant = AdaptAssistant.create({ onSubmit: (text) => ask(text) });
  if (!assistant) return;
  const box = document.getElementById("agent-messages");
  const input = document.getElementById("agent-input");
  const chat = AiChat.view(box);

  let greeting = null;
  function showGreeting() {
    const text = tr("as.greeting", "Ahoj! Som tvoj AI asistent. Pomôžem ti zorientovať sa v aplikácii.");
    if (greeting && greeting.el.isConnected) greeting.set(text);
    else greeting = chat.plain(text, false);
  }

  async function dashboardState() {
    try { return (window.adaptpyGetDashboard && await window.adaptpyGetDashboard()) || {}; }
    catch (e) { return {}; }
  }

  // záložné odpovede bez modelu
  async function fallback(kind) {
    if (kind === "how") return tr("as.replyHow", "");
    const d = await dashboardState();
    if (!(d.pretest && d.pretest.done)) return tr("as.replyPretest", "Najprv urob predtest.");
    const testsOn = !d.sections || d.sections.tests !== false;
    return tr("as.replyNext", "Pokračuj v úlohách.") + (testsOn ? tr("as.replyNextTests", "") : "");
  }

  function setBusy(on) {
    busy = on;
    if (input) input.disabled = on;
    document.querySelectorAll("#agent-next, #agent-how").forEach((b) => { b.disabled = on; });
  }

  async function ask(text, fallbackKind) {
    if (busy || !text) return;
    setBusy(true);
    const res = await AiChat.ask(chat, { mode: "dashboard", message: text }, { userText: text });
    if (!res.ok && fallbackKind && !(res.data && res.data.status === 429)) {
      const t = await fallback(fallbackKind);
      if (t) chat.plain(t);
    }
    setBusy(false);
    if (input) input.focus({ preventScroll: true });
  }

  document.getElementById("agent-next").addEventListener("click", () =>
    ask(tr("as.chipNext", "Čo mám robiť ďalej?"), "next"));
  document.getElementById("agent-how").addEventListener("click", () =>
    ask(tr("as.chipHow", "Ako funguje aplikácia?"), "how"));

  document.addEventListener("langchange", () => {
    if (greeting && box.querySelectorAll(".ul-row").length <= 1) showGreeting();
  });

  (async function init() {
    const messages = await AiChat.history({ mode: "dashboard" });
    if (messages.length) chat.restore(messages);
    else showGreeting();
    assistant.minimize();   // predvolene zbalené: vidno len ikonu robota
  })();
})();
