/* ============================================================
   AdaptPy - AI chat asistent (dashboard)
   Zatiaľ používa placeholder odpoveď. Keď budete mať vlastný
   model, stačí implementovať funkciu callModel() nižšie - poslať
   správu na váš backend endpoint a vrátiť odpoveď. Zvyšok
   (UI, história, scrollovanie) je hotový.
   ============================================================ */
(function () {
  const messagesEl = document.getElementById("chat-messages");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  if (!messagesEl || !form || !input) return;

  // História konverzácie - pripravená na odoslanie modelu ako kontext.
  const history = [];

  function tr(key, fallback) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fallback;
  }

  function addMessage(text, who) {
    const div = document.createElement("div");
    div.className = "chat-msg chat-msg--" + who;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function addTyping() {
    const div = document.createElement("div");
    div.className = "chat-msg chat-msg--bot chat-msg--typing";
    div.textContent = tr("chat.typing", "AdaptPy píše…");
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  /* ---------------------------------------------------------
     TU NAPOJÍTE VÁŠ MODEL.
     Momentálne vracia placeholder. Keď budete mať vlastný model,
     nahraďte telo tejto funkcie volaním vášho backendu, napr.:

       const r = await fetch("/api/chat", {
         method: "POST",
         headers: { "Content-Type": "application/json" },
         credentials: "include",
         body: JSON.stringify({ message: userText, history })
       });
       const data = await r.json();
       return data.reply;
     --------------------------------------------------------- */
  async function callModel(userText) {
    // Placeholder - kým nie je napojený reálny model
    await new Promise(res => setTimeout(res, 600));
    return tr("chat.placeholderReply",
      "Zatiaľ som len ukážkový asistent 🙂 Čoskoro ma napojíme na vlastný model AdaptPy.");
  }

  async function send(e) {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    addMessage(text, "user");
    history.push({ role: "user", content: text });
    input.value = "";
    input.disabled = true;

    const typing = addTyping();
    let reply;
    try {
      reply = await callModel(text);
    } catch (err) {
      reply = tr("chat.error", "Prepáč, niečo sa pokazilo. Skús to znova.");
    }
    typing.remove();

    addMessage(reply, "bot");
    history.push({ role: "assistant", content: reply });
    input.disabled = false;
    input.focus();
  }

  form.addEventListener("submit", send);
})();
