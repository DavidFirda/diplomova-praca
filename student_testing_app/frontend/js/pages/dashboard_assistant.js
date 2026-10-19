/* ============================================================
   AdaptPy - dashboard: asistent.

   Rovnako ako na stránke Úlohy: v rohu je len ikona robota (tooltip "Asistent").
   Klik ju rozbalí na okno cez výšku obrazovky (animované), tlačidlo "—"
   (alebo Esc) ho minimalizuje späť na ikonu.

   Samotný chat (správy, odosielanie) rieši chat.js, tu je len otváranie.
   ============================================================ */
(function () {
  const panel = document.getElementById("dash-assistant");
  const fab = document.getElementById("chat-fab");
  const minBtn = document.getElementById("chat-minimize");
  if (!panel || !fab) return;

  const isOpen = () => panel.classList.contains("is-open");

  function open() {
    panel.classList.add("is-open");
    panel.setAttribute("aria-hidden", "false");
    fab.classList.remove("is-visible");
    fab.setAttribute("aria-expanded", "true");
    setTimeout(() => {
      const input = document.getElementById("chat-input");
      if (input) input.focus({ preventScroll: true });
    }, 300);
  }

  function minimize() {
    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    fab.setAttribute("aria-expanded", "false");
    fab.classList.add("is-visible");
  }

  fab.addEventListener("click", open);
  if (minBtn) minBtn.addEventListener("click", minimize);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isOpen()) minimize();
  });

  document.body.classList.add("dash-has-fab");
  minimize();   // predvolene zbalené: vidno len ikonu
})();
