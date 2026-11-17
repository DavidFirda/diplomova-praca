/* AdaptPy - animované postavičky na prihlásení, registrácii a obnove hesla.
   Tvary a správanie pri hesle ostávajú pôvodné, pribudla scéna a viac pohybu.

   Stavy (trieda na .auth-hero):
   - idle:     oči sledujú kurzor (na dotykových zariadeniach sa samy rozhliadajú),
               telá sa pohupujú, nohy prešľapujú, postavičky žmurkajú.
   - watch:    píšeš do bežného poľa - pozerajú na formulár a pri písmenkách poskakujú.
   - away:     píšeš skryté heslo - otočia hlavy preč a zavrú oči.
   - looking:  heslo je zobrazené (klik na oko) - zvedavo nakuknú, vycerí zuby.
   - sad:      zobrazí sa chyba - pokrútia hlavami a pozrú dole.
   - cheer:    úspešné prihlásenie/registrácia - radostne vyskočia.
   Klik na postavičku = vyskočí.

   API: window.adaptpyBuddiesPeek(show) - volá ho prepínač zobrazenia hesla. */
(function () {
  /* ---------- Scéna za postavičkami: škvrny, plávajúce symboly, zadná vlna ---------- */
  const SCENE_SVG = `
    <svg class="auth-scene" viewBox="0 0 400 480" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
      <path class="sc-blob sc-blob--1" d="M-60 150 C 10 60, 150 70, 185 150 S 130 300, 20 285 S -130 235, -60 150Z"/>
      <path class="sc-blob sc-blob--2" d="M290 60 C 370 10, 470 70, 445 165 S 330 240, 295 175 S 230 95, 290 60Z"/>
      <circle class="sc-blob sc-blob--3" cx="345" cy="330" r="62"/>
      <g class="sc-syms">
        <text class="sc-sym" x="40"  y="470" style="--t:13s;--d:0s">{ }</text>
        <text class="sc-sym" x="300" y="470" style="--t:11s;--d:2.4s">&gt;&gt;&gt;</text>
        <text class="sc-sym" x="175" y="470" style="--t:15s;--d:5s">#</text>
        <text class="sc-sym" x="95"  y="470" style="--t:12s;--d:7.2s">( )</text>
        <text class="sc-sym" x="355" y="470" style="--t:14s;--d:8.6s">def</text>
        <text class="sc-sym" x="240" y="470" style="--t:12.5s;--d:10.4s">[ ]</text>
        <circle class="sc-bubble" cx="140" cy="470" r="5" style="--t:10s;--d:1.2s"/>
        <circle class="sc-bubble" cx="268" cy="470" r="3.5" style="--t:9s;--d:4.1s"/>
        <circle class="sc-bubble" cx="62"  cy="470" r="4"  style="--t:11s;--d:6.4s"/>
        <circle class="sc-bubble" cx="330" cy="470" r="6"  style="--t:12s;--d:9.5s"/>
      </g>
      <g class="sc-wave sc-wave--back">
        <path d="M0 418 Q50 398 100 418 T200 418 T300 418 T400 418 T500 418 T600 418 T700 418 T800 418 V480 H0Z"/>
      </g>
    </svg>`;

  /* ---------- Predná vlna (prekryje päty postavičiek) ---------- */
  const FRONT_SVG = `
    <svg class="auth-front" viewBox="0 0 400 40" preserveAspectRatio="none" aria-hidden="true">
      <g class="sc-wave sc-wave--front">
        <path d="M0 16 Q50 4 100 16 T200 16 T300 16 T400 16 T500 16 T600 16 T700 16 T800 16 V40 H0Z"/>
      </g>
    </svg>`;

  /* ---------- Postavičky (pôvodné tvary + tieňovanie, lesk v očiach, líčka) ----------
     Oko = biele bulvo + zrenica (sleduje kurzor) + viečko vo farbe tela, ktoré sa
     zosúva zhora (žmurknutie, zavreté oči pri hesle, privreté pri chybe).
     Pri úplne zavretom oku sa ukáže jemná oblúková čiarka „‿“. */
  let eyeN = 0;
  const eye = (cx, cy, r, gx, gy, pr, lid) => {
    const id = "bd-eye-" + (++eyeN);
    const lw = Math.max(2.4, r * 0.2).toFixed(1);
    return `
    <g class="eyeball">
      <clipPath id="${id}"><circle cx="${cx}" cy="${cy}" r="${r}"/></clipPath>
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="#fff"/>
      <g class="eye" data-cx="${gx}" data-cy="${gy}" data-r="${pr}">
        <circle cx="${cx}" cy="${cy}" r="${pr}" fill="#2b2b33"/>
        <circle cx="${cx + pr * 0.38}" cy="${cy - pr * 0.4}" r="${Math.max(1.6, pr * 0.32)}" fill="#fff"/>
      </g>
      <g clip-path="url(#${id})">
        <g class="lid" style="--up:${-(r + 2)}px;--half:${(-r * 0.12).toFixed(1)}px;--down:${r + 1}px">
          <rect x="${cx - r - 1}" y="${cy - 2 * r - 2}" width="${2 * r + 2}" height="${2 * r + 2}" fill="${lid}"/>
          <rect x="${cx - r - 1}" y="${cy - 2.6}" width="${2 * r + 2}" height="2.6" fill="#000" opacity=".18"/>
        </g>
      </g>
      <circle cx="${cx}" cy="${cy}" r="${r - 0.6}" fill="none" stroke="#000" stroke-opacity=".07" stroke-width="1.2"/>
      <path class="eye-closed" d="M${cx - r * 0.62} ${cy + r * 0.05} Q${cx} ${cy + r * 0.62} ${cx + r * 0.62} ${cy + r * 0.05}"
        fill="none" stroke="#2b2b33" stroke-width="${lw}" stroke-linecap="round"/>
    </g>`;
  };

  // chlpatá hlava tyrkysovej postavičky - pravidelný „bambuľkový“ obrys
  const fluff = (() => {
    let c = '<circle cx="86" cy="228" r="46"/>';
    for (let i = 0; i < 14; i++) {
      const a = (i / 14) * Math.PI * 2 - Math.PI / 2;
      const rr = 15 + (i % 2) * 2.5;
      c += `<circle cx="${(86 + Math.cos(a) * 44).toFixed(1)}" cy="${(228 + Math.sin(a) * 42).toFixed(1)}" r="${rr}"/>`;
    }
    return c;
  })();

  const BUDDIES_SVG = `
    <svg viewBox="0 0 320 400" preserveAspectRatio="xMidYMax meet" aria-hidden="true">
      <defs>
        <linearGradient id="bdg-pink" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fbcbdf"/><stop offset="1" stop-color="#f19bbf"/></linearGradient>
        <linearGradient id="bdg-red" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f4789f"/><stop offset="1" stop-color="#df3f7b"/></linearGradient>
        <linearGradient id="bdg-redleg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ef5e90"/><stop offset="1" stop-color="#d43873"/></linearGradient>
        <linearGradient id="bdg-teal" gradientUnits="userSpaceOnUse" x1="40" y1="180" x2="130" y2="280"><stop offset="0" stop-color="#a6e9e4"/><stop offset="1" stop-color="#5cc1ba"/></linearGradient>
        <linearGradient id="bdg-blue" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6ab9ff"/><stop offset="1" stop-color="#2a84e4"/></linearGradient>
      </defs>

      <!-- RUŽOVÁ: veľký oblúk, jedno veľké oko, ústa so zúbkami -->
      <g class="bd bd--ghost"><g class="bd__enter"><g class="bd__bob">
        <path class="bd__body" d="M136 132 a77 77 0 0 1 154 0 V400 H136 Z" fill="url(#bdg-pink)"/>
        <ellipse cx="168" cy="104" rx="20" ry="9" fill="#fff" opacity=".35" transform="rotate(-38 168 104)"/>
        <g class="bd__head">
          ${eye(204, 192, 31, 204, 192, 13, "#f6b3d0")}
          <ellipse class="blush" cx="170" cy="236" rx="11" ry="6" fill="#ef6f9e" opacity=".35"/>
          <g class="mouth" data-cx="252" data-cy="240" data-r="4">
            <ellipse cx="252" cy="240" rx="10" ry="12" fill="#b85c78"/>
            <rect x="245.5" y="230" width="6" height="6.5" rx="2" fill="#fff"/>
            <rect x="252.5" y="230" width="6" height="6.5" rx="2" fill="#fff"/>
          </g>
        </g>
      </g></g></g>

      <!-- ČERVENÁ: pilulková hlava s očami navrchu, plné zuby, rozkročené nohy -->
      <g class="bd bd--tall"><g class="bd__enter"><g class="bd__bob">
        <rect class="leg leg--l" x="80" y="95" width="16" height="305" rx="8" fill="url(#bdg-redleg)"/>
        <rect class="leg leg--r" x="102" y="95" width="16" height="305" rx="8" fill="url(#bdg-redleg)"/>
        <g class="bd__head">
          <g class="mouth-closed">
            <rect x="20" y="69" width="126" height="46" rx="20" fill="url(#bdg-red)"/>
            <rect x="30" y="74" width="40" height="7" rx="3.5" fill="#fff" opacity=".3"/>
            <rect class="mouth" data-cx="120" data-cy="74" data-r="4" x="108" y="83" width="24" height="11" rx="5.5" fill="#fff"/>
          </g>
          <g class="mouth-open">
            <rect x="22" y="65" width="130" height="46" rx="23" fill="url(#bdg-red)"/>
            <rect x="32" y="75" width="110" height="26" rx="8" fill="#fff"/>
            <g stroke="#e84c86" stroke-width="2">
              <line x1="48" y1="75" x2="48" y2="101"/><line x1="64" y1="75" x2="64" y2="101"/>
              <line x1="80" y1="75" x2="80" y2="101"/><line x1="96" y1="75" x2="96" y2="101"/>
              <line x1="112" y1="75" x2="112" y2="101"/><line x1="128" y1="75" x2="128" y2="101"/>
              <line x1="32" y1="88" x2="142" y2="88"/>
            </g>
          </g>
          ${eye(76, 61, 15, 76, 46, 6.5, "#ea5f8f")}
          ${eye(104, 61, 15, 104, 46, 6.5, "#ea5f8f")}
        </g>
      </g></g></g>

      <!-- TYRKYSOVÁ: chlpatá guľa -->
      <g class="bd bd--fluff"><g class="bd__enter"><g class="bd__bob">
        <rect class="leg leg--l" x="66" y="262" width="14" height="138" rx="7" fill="#6fcdc6"/>
        <rect class="leg leg--r" x="96" y="262" width="14" height="138" rx="7" fill="#5fc3bc"/>
        <g class="bd__head">
          <g fill="url(#bdg-teal)">
            ${fluff}
          </g>
          <ellipse cx="62" cy="196" rx="9" ry="5" fill="#fff" opacity=".35" transform="rotate(-30 62 196)"/>
          ${eye(72, 222, 14.5, 72, 222, 6.5, "#86d6cf")}
          ${eye(100, 222, 14.5, 100, 222, 6.5, "#86d6cf")}
          <ellipse class="blush" cx="56" cy="244" rx="8" ry="4.5" fill="#2f9f97" opacity=".3"/>
          <ellipse class="blush" cx="117" cy="244" rx="8" ry="4.5" fill="#2f9f97" opacity=".3"/>
          <ellipse class="mouth mouth-fluff-small" data-cx="87" data-cy="248" data-r="3" cx="87" cy="248" rx="8" ry="6" fill="#2a7f79"/>
          <rect class="mouth-fluff-dash" x="70" y="243" width="34" height="10" rx="5" fill="#2a7f79"/>
        </g>
      </g></g></g>

      <!-- MODRÁ: guľatá -->
      <g class="bd bd--blue"><g class="bd__enter"><g class="bd__bob">
        <rect class="leg leg--l" x="142" y="322" width="14" height="78" rx="7" fill="#3a95ef"/>
        <rect class="leg leg--r" x="172" y="322" width="14" height="78" rx="7" fill="#2f86e0"/>
        <g class="bd__head">
          <circle cx="163" cy="292" r="44" fill="url(#bdg-blue)"/>
          <ellipse cx="141" cy="263" rx="11" ry="6" fill="#fff" opacity=".35" transform="rotate(-35 141 263)"/>
          ${eye(150, 282, 14, 150, 282, 6, "#4ea2f6")}
          ${eye(176, 282, 14, 176, 282, 6, "#4ea2f6")}
          <ellipse class="blush" cx="136" cy="304" rx="7" ry="4" fill="#ff8fb6" opacity=".45"/>
          <ellipse class="blush" cx="191" cy="304" rx="7" ry="4" fill="#ff8fb6" opacity=".45"/>
          <ellipse class="mouth mouth-blue-small" data-cx="164" data-cy="308" data-r="3" cx="164" cy="308" rx="7" ry="5.5" fill="#0a4a8f"/>
          <g class="mouth-blue-open">
            <ellipse cx="164" cy="311" rx="10" ry="11" fill="#0a4a8f"/>
            <rect x="158.5" y="302" width="5" height="5.5" rx="1.8" fill="#fff"/>
            <rect x="165.5" y="302" width="5" height="5.5" rx="1.8" fill="#fff"/>
          </g>
        </g>
      </g></g></g>
    </svg>`;

  function init() {
    const mount = document.getElementById("buddies-mount");
    if (!mount) return;
    const hero = mount.closest(".auth-hero");
    mount.innerHTML = BUDDIES_SVG;
    if (hero) {
      hero.insertAdjacentHTML("afterbegin", SCENE_SVG);
      hero.insertAdjacentHTML("beforeend", FRONT_SVG);
    }

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const svg = mount.querySelector("svg");
    const buddies = [].slice.call(mount.querySelectorAll(".bd"));
    const movers = [].slice.call(mount.querySelectorAll(".eye, .mouth"));
    const isRight = hero && hero.classList.contains("auth-hero--right");
    const dirToForm = isRight ? -1 : 1;
    const STATES = ["buddies-away", "buddies-looking", "buddies-watch", "buddies-sad", "buddies-cheer"];

    let state = "idle";
    let lastPointer = 0;
    let tempTimer = null;

    /* ---- pohľad ---- */
    function moveTo(el, ox, oy) {
      el.setAttribute("transform", "translate(" + ox.toFixed(1) + "," + oy.toFixed(1) + ")");
    }
    function follow(clientX, clientY) {
      if (state !== "idle") return;
      const r = svg.getBoundingClientRect();
      if (!r.width) return;
      const vb = svg.viewBox.baseVal;
      const sx = vb.width / r.width, sy = vb.height / r.height;
      const mx = (clientX - r.left) * sx, my = (clientY - r.top) * sy;
      movers.forEach(function (el) {
        const ex = +el.dataset.cx, ey = +el.dataset.cy, mo = +el.dataset.r;
        const dx = mx - ex, dy = my - ey, d = Math.hypot(dx, dy) || 1;
        moveTo(el, dx / d * Math.min(mo, d), dy / d * Math.min(mo, d));
      });
    }
    function setGaze(sx, sy) {
      movers.forEach(function (el) {
        const mo = +el.dataset.r;
        moveTo(el, dirToForm * sx * mo, (sy || 0) * mo);
      });
    }
    document.addEventListener("pointermove", function (e) {
      if (e.pointerType === "mouse") { lastPointer = Date.now(); follow(e.clientX, e.clientY); }
    });

    /* ---- stavy ---- */
    function apply(next) {
      state = next;
      if (!hero) return;
      STATES.forEach(function (c) { hero.classList.remove(c); });
      if (next === "away") { hero.classList.add("buddies-away"); setGaze(-1, 0.15); }
      else if (next === "looking") { hero.classList.add("buddies-looking"); setGaze(1, -0.45); }
      else if (next === "watch") { hero.classList.add("buddies-watch"); setGaze(0.9, 0.35); }
      else if (next === "sad") { hero.classList.add("buddies-sad"); setGaze(0.2, 0.9); }
      else if (next === "cheer") { hero.classList.add("buddies-cheer"); setGaze(0, -0.5); }
      else setGaze(0, 0);
    }
    function settle() {
      const a = document.activeElement;
      if (isPw(a)) apply(a.type === "password" ? "away" : "looking");
      else if (isField(a)) apply("watch");
      else apply("idle");
    }
    function temporary(next, ms) {
      clearTimeout(tempTimer);
      apply(next);
      tempTimer = setTimeout(settle, ms);
    }

    /* ---- jednorazové pohyby ---- */
    function once(el, cls, ms) {
      el.classList.remove(cls);
      void el.getBoundingClientRect();   // reštart animácie
      el.classList.add(cls);
      setTimeout(function () { el.classList.remove(cls); }, ms);
    }
    function hop(b) { if (!reduce) once(b, "is-hop", 340); }
    function jump(b) { if (!reduce) once(b, "is-jump", 700); }
    function blink(b) { once(b, "is-blink", 200); }

    buddies.forEach(function (b) {
      b.addEventListener("click", function () { jump(b); });
    });

    // žmurkanie - každá postavička vo vlastnom rytme
    if (!reduce) {
      buddies.forEach(function (b, i) {
        (function loop() {
          setTimeout(function () {
            if (state !== "away") {
              blink(b);
              if (Math.random() < 0.25) setTimeout(function () { blink(b); }, 260);   // občas dvojité žmurknutie
            }
            loop();
          }, 2200 + Math.random() * 3800 + i * 300);
        })();
      });

      // bez myši (mobil): postavičky sa samy rozhliadajú
      setInterval(function () {
        if (state !== "idle" || Date.now() - lastPointer < 4000) return;
        setGaze((Math.random() * 2 - 1) * dirToForm, Math.random() * 1.2 - 0.6);
      }, 2600);
    }

    /* ---- heslo, písanie, chyby, úspech ---- */
    window.adaptpyBuddiesPeek = function (show) { apply(show ? "looking" : (isPw(document.activeElement) ? "away" : "idle")); };

    function isPw(el) {
      return !!el && el.tagName === "INPUT" &&
        (el.type === "password" || el.type === "text") &&
        (el.id === "password" || el.id === "new_password" || el.id === "new_password_confirm" ||
         el.getAttribute("autocomplete") === "current-password" ||
         el.getAttribute("autocomplete") === "new-password");
    }
    function isField(el) {
      return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA") && !!el.closest(".auth-panel") && !isPw(el);
    }

    let lastHop = 0;
    document.addEventListener("focusin", function (e) {
      const el = e.target;
      if (isPw(el)) { clearTimeout(tempTimer); apply(el.type === "password" ? "away" : "looking"); }
      else if (isField(el)) { clearTimeout(tempTimer); apply("watch"); }
    });
    document.addEventListener("input", function (e) {
      const el = e.target;
      if (isPw(el)) { apply(el.type === "password" ? "away" : "looking"); return; }
      if (!isField(el)) return;
      if (state !== "watch") apply("watch");
      const now = Date.now();
      if (now - lastHop > 140) {
        lastHop = now;
        hop(buddies[Math.floor(Math.random() * buddies.length)]);
      }
    });
    document.addEventListener("focusout", function (e) {
      if (!isPw(e.target) && !isField(e.target)) return;
      setTimeout(function () { if (state !== "sad" && state !== "cheer") settle(); }, 0);
    });

    // chybová hláška formulára -> postavičky posmutnejú
    const err = document.getElementById("error-message");
    if (err && "MutationObserver" in window) {
      new MutationObserver(function () {
        const visible = err.style.display !== "none" && err.textContent.trim() !== "";
        if (visible) temporary("sad", 1800);
      }).observe(err, { attributes: true, attributeFilter: ["style"], childList: true, characterData: true, subtree: true });
    }

    // úspech (posiela js/auth/script.js) -> radosť
    document.addEventListener("adaptpy:auth-success", function () {
      temporary("cheer", 2000);
      buddies.forEach(function (b, i) { setTimeout(function () { jump(b); }, i * 90); });
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
