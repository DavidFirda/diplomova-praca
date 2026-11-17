/* ============================================================
   AdaptPy - pohyb (animácie). Načíta sa automaticky z i18n.js.
   - Karty pri načítaní stránky jemne nastúpia (postupne, krátko).
   - Čísla v metrikách sa "dopočítajú" od nuly.
   - Prvky s atribútom data-reveal sa ukážu pri scrollovaní.
   Všetko sa vypne, keď má človek v systéme "Obmedziť pohyb".
   Logiku stránok to nemení - iba pridáva CSS triedy.
   ============================================================ */
(function () {
  if (window.__adaptpyMotion) return;
  window.__adaptpyMotion = true;

  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (reduce.matches) return;

  // Prvky, ktoré pri prvom zobrazení nastúpia (fade + mierny posun).
  const ENTER = [
    ".app-topbar__greeting", ".metric-row", ".task-row", ".dash-hero", ".dash-card", ".dash-ex",
    ".app-main > .card", ".centered-card", ".test-card", ".ex-row", ".ex-head", ".nb-code", ".nb-md",
    ".ux-ex", ".chat-panel", ".auth-card", ".page > .card", ".admin-q", ".exadmin-item"
  ].join(",");
  // Pruhy pokroku, ktoré sa pri zobrazení "naplnia".
  const BARS = ".dash-bar__fill, .ex-progress__fill, .cat-bar__fill, .dash-dot, .ul-dot";
  // Čísla, ktoré sa dopočítajú.
  const COUNT = ".metric__value, .stats-big__value";

  const ENTER_WINDOW_MS = 2500;   // nové prvky animujeme len krátko po načítaní stránky
  const start = performance.now();
  const inWindow = () => performance.now() - start < ENTER_WINDOW_MS;

  function tagEnter(nodes) {
    let i = 0;
    nodes.forEach((el) => {
      if (el.classList.contains("mo-in") || el.closest(".mo-skip")) return;
      el.style.setProperty("--mo-i", Math.min(i++, 8));
      el.classList.add("mo-in");
    });
  }
  function tagBars(nodes) {
    nodes.forEach((el) => { if (!el.classList.contains("mo-bar")) el.classList.add("mo-bar"); });
  }

  function scan(root) {
    if (!(root instanceof Element) && root !== document) return;
    const enter = [];
    const bars = [];
    if (root instanceof Element) {
      if (root.matches(ENTER)) enter.push(root);
      if (root.matches(BARS)) bars.push(root);
    }
    root.querySelectorAll(ENTER).forEach((el) => enter.push(el));
    root.querySelectorAll(BARS).forEach((el) => bars.push(el));
    tagEnter(enter);
    tagBars(bars);
  }

  // ---------- Dopočítanie čísel ----------
  const NUM_RE = /\d+(?:[.,]\d+)?/g;
  function countUp(el) {
    if (el.dataset.moCounting === "1" || el.dataset.moCounted === "1") return;
    const target = el.textContent;
    const nums = target.match(NUM_RE);
    if (!nums || target.trim() === "0") return;
    el.dataset.moCounted = "1";
    el.dataset.moCounting = "1";
    const values = nums.map((n) => parseFloat(n.replace(",", ".")));
    const decimals = nums.map((n) => (n.split(/[.,]/)[1] || "").length);
    const sep = nums.map((n) => (n.includes(",") ? "," : "."));
    const dur = 700;
    const t0 = performance.now();
    const ease = (t) => 1 - Math.pow(1 - t, 3);
    function frame(now) {
      const p = Math.min(1, (now - t0) / dur);
      let k = 0;
      el.textContent = target.replace(NUM_RE, () => {
        const v = values[k] * ease(p);
        const s = v.toFixed(decimals[k]).replace(".", sep[k]);
        k++;
        return s;
      });
      if (p < 1) requestAnimationFrame(frame);
      else { el.textContent = target; el.dataset.moCounting = "0"; }
    }
    requestAnimationFrame(frame);
  }
  function watchCounters() {
    document.querySelectorAll(COUNT).forEach((el) => {
      if (el.__moObs) return;
      el.__moObs = new MutationObserver(() => {
        if (el.dataset.moCounting === "1") return;
        if (inWindow()) countUp(el);
      });
      el.__moObs.observe(el, { childList: true, characterData: true, subtree: true });
      // hodnota už môže byť vyplnená
      if (/\d/.test(el.textContent) && el.textContent.trim() !== "0") countUp(el);
    });
  }

  // ---------- Zobrazenie pri scrollovaní (data-reveal) ----------
  function setupReveal() {
    const items = document.querySelectorAll("[data-reveal]");
    if (!items.length) return;
    if (!("IntersectionObserver" in window)) { items.forEach((el) => el.classList.add("is-revealed")); return; }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add("is-revealed"); io.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
    items.forEach((el) => io.observe(el));
  }

  function init() {
    document.documentElement.classList.add("mo");
    scan(document);
    watchCounters();
    setupReveal();
    // Obsah, ktorý doplní JS po načítaní dát (karty, riadky, pruhy).
    const mo = new MutationObserver((muts) => {
      // Po úvodnom načítaní už nič neanimujeme (prepnutie jazyka, časté akcie) -
      // pohyb pri častých interakciách skôr ruší.
      if (!inWindow()) { mo.disconnect(); return; }
      for (const m of muts) {
        m.addedNodes.forEach((n) => { if (n instanceof Element) scan(n); });
      }
      watchCounters();
    });
    mo.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
