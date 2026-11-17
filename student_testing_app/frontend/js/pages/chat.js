/* ============================================================
   AdaptPy - panel AI asistenta v cvičení: správanie okna.

   - desktop: panel je pripnutý vpravo a vždy sa celý zmestí do okna,
   - tablet/mobil: dok dole, rozbaľuje sa ťuknutím (náhľad poslednej odpovede),
     Escape / klik mimo ho zbalí.

   Správy, streamovanie odpovedí, zdroje a vloženie kódu do bunky rieši
   js/core/ai_chat.js a initAssistant() v js/pages/cvicenie.js.
   ============================================================ */
(function () {
  const messagesEl = document.getElementById("chat-messages");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  if (!messagesEl || !form || !input) return;

  function tr(key, fallback) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fallback;
  }

  // ---- Vzhľad panelu (cvičenie): náhľad poslednej odpovede, rozbalenie na mobile, rýchle otázky ----
  const panel = messagesEl.closest(".chat-panel");
  const previewEl = document.getElementById("chat-preview");
  const toggleBtn = document.getElementById("chat-toggle");

  function updatePreview() {
    if (!previewEl) return;
    const bots = messagesEl.querySelectorAll(".ul-row--agent .ai-body");
    const last = bots[bots.length - 1];
    previewEl.textContent = last ? last.textContent.replace(/\s+/g, " ").trim().slice(0, 160) : "";
  }
  function setExpanded(open) {
    if (!panel) return;
    panel.classList.toggle("is-expanded", open);
    if (toggleBtn) {
      toggleBtn.setAttribute("aria-expanded", open ? "true" : "false");
      toggleBtn.setAttribute("aria-label", open ? tr("chat.collapse", "Zbaliť chat") : tr("chat.expand", "Rozbaliť chat"));
    }
    if (open) {
      messagesEl.scrollTop = messagesEl.scrollHeight;
      // na počítači rovno do poľa (na dotyku nie, aby nevyskočila klávesnica)
      if (isDock() && window.matchMedia("(pointer: fine)").matches) setTimeout(() => { try { input.focus({ preventScroll: true }); } catch (e) {} }, 60);
    }
  }
  const isDock = () => !!toggleBtn && getComputedStyle(toggleBtn).display !== "none";
  if (toggleBtn) toggleBtn.addEventListener("click", (e) => { e.stopPropagation(); setExpanded(!panel.classList.contains("is-expanded")); });
  // v doku (tablet/mobil) rozbalí/zbalí aj ťuknutie na hlavičku
  const headerEl = panel && panel.querySelector(".chat-panel__header");
  if (headerEl) headerEl.addEventListener("click", () => { if (isDock()) setExpanded(!panel.classList.contains("is-expanded")); });
  // klik mimo rozbaleného doku ho zase zmenší
  document.addEventListener("pointerdown", (e) => {
    if (isDock() && panel.classList.contains("is-expanded") && !panel.contains(e.target)) setExpanded(false);
  });
  // keď sa okno zmenší a panel sa prepne do doku, začne zmenšený
  const dockMq = window.matchMedia("(max-width: 1180px), (max-height: 620px)");
  const onDockChange = () => { if (dockMq.matches) setExpanded(false); };
  if (dockMq.addEventListener) dockMq.addEventListener("change", onDockChange); else if (dockMq.addListener) dockMq.addListener(onDockChange);
  // Escape zbalí dok
  if (panel) panel.addEventListener("keydown", (e) => { if (e.key === "Escape" && isDock() && panel.classList.contains("is-expanded")) { setExpanded(false); toggleBtn.focus(); } });
  // na mobile sa po kliknutí do poľa chat rozbalí
  input.addEventListener("focus", () => { if (isDock()) setExpanded(true); });
  // náhľad poslednej odpovede (v zbalenom doku) - správy pridáva AI asistent (ai_chat.js),
  // preto sa náhľad obnoví pri každej zmene zoznamu správ
  let previewRaf = 0;
  new MutationObserver(() => {
    if (!previewRaf) previewRaf = requestAnimationFrame(() => { previewRaf = 0; updatePreview(); });
  }).observe(messagesEl, { childList: true, subtree: true, characterData: true });
  updatePreview();
  document.addEventListener("langchange", () => setTimeout(updatePreview, 0));

  // pre cvicenie.js (napr. po vložení kódu do bunky sa dok zbalí, aby bola bunka vidieť)
  window.adaptpyChatPanel = { setExpanded, isDock };

  // Desktop: panel je pripnutý vpravo a vždy sa celý zmestí do okna (vidno aj pole na písanie)
  const sidePanel = panel && panel.closest(".side-panel");
  const workspace = panel && panel.closest(".ex-workspace");
  if (sidePanel && workspace) {
    let raf = 0;
    const fit = () => {
      raf = 0;
      if (isDock()) { sidePanel.style.height = ""; return; }
      const toolbar = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--toolbar-h")) || 56;
      const ws = workspace.getBoundingClientRect();
      const top = Math.max(ws.top, toolbar + 16);
      // na konci stránky sa panel radšej zmenší, než by mu hlavička zašla pod lištu
      const h = Math.min(window.innerHeight - top - 24, ws.bottom - top);
      sidePanel.style.height = Math.max(320, h) + "px";
    };
    const schedule = () => { if (!raf) raf = requestAnimationFrame(fit); };
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    fit();
  }
})();
