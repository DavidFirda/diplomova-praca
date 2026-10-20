/* ============================================================
   AdaptPy - dashboard: asistent.

   Rovnaký asistent (okno, ikona, animácie) ako na stránke Úlohy, len všeobecný:
   orientuje sa v celej aplikácii (čo robiť ďalej, ako čo funguje), nie v konkrétnej
   úlohe. Okno, ikonu a bubliny rieši js/core/assistant.js.

   Voľné otázky zatiaľ dostávajú ukážkovú odpoveď. Keď bude hotový model, stačí
   nahradiť telo callModel() volaním backendu.
   ============================================================ */
(function () {
  if (typeof AdaptAssistant === "undefined") return;

  const tr = (key, fb) => {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  };

  const assistant = AdaptAssistant.create({ onSubmit: ask });
  if (!assistant) return;

  // pozdrav; kým sa nezačne konverzácia, prekladá sa pri zmene jazyka
  let greeting = null;
  function showGreeting() {
    const text = tr("as.greeting", "Ahoj! Som tvoj AI asistent. Pomôžem ti zorientovať sa v aplikácii.");
    if (greeting && greeting.isConnected) greeting.textContent = text;
    else greeting = assistant.addMessage("agent", text, false);
  }

  async function dashboardState() {
    try { return (window.adaptpyGetDashboard && await window.adaptpyGetDashboard()) || {}; }
    catch (e) { return {}; }
  }

  async function nextStepReply() {
    const d = await dashboardState();
    if (!(d.pretest && d.pretest.done)) return tr("as.replyPretest", "Najprv urob predtest.");
    const testsOn = !d.sections || d.sections.tests !== false;
    return tr("as.replyNext", "Pokračuj v úlohách.") + (testsOn ? tr("as.replyNextTests", "") : "");
  }

  // callModel: sem sa neskôr napojí vlastný model (voľné otázky)
  async function callModel() {
    await new Promise((res) => setTimeout(res, 600));
    return tr("chat.placeholderReply",
      "Zatiaľ som len ukážkový asistent 🙂 Čoskoro ma napojíme na vlastný model AdaptPy.");
  }

  async function reply(getText) {
    assistant.showTyping();
    let text;
    try { text = await getText(); }
    catch (e) { text = tr("chat.error", "Prepáč, niečo sa pokazilo. Skús to znova."); }
    assistant.hideTyping();
    assistant.addMessage("agent", text);
  }

  function ask(text) {
    assistant.addMessage("user", text);
    reply(() => callModel(text));
  }

  document.getElementById("agent-next").addEventListener("click", () => {
    assistant.addMessage("user", tr("as.chipNext", "Čo mám robiť ďalej?"));
    reply(nextStepReply);
  });
  document.getElementById("agent-how").addEventListener("click", () => {
    assistant.addMessage("user", tr("as.chipHow", "Ako funguje aplikácia?"));
    reply(async () => tr("as.replyHow", ""));
  });

  document.addEventListener("langchange", () => {
    const box = document.getElementById("agent-messages");
    if (box && box.querySelectorAll(".ul-row").length <= 1) showGreeting();
  });

  showGreeting();
  assistant.minimize();   // predvolene zbalené: vidno len ikonu robota
})();
