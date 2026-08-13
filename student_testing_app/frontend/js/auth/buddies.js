/* AdaptPy - animované postavičky (kreslené presne podľa gifu).
   Stavy:
   - IDLE: oči/ústa sledujú kurzor, telá sa pohupujú, nohy prešľapujú.
   - AWAY (píšeš skryté heslo): červená VÝRAZNE sklopí hlavu nabok so zavretou
     hubou (biela čiarka), tyrkysová má širokú plochú čiarku, modrá malé ústa,
     všetky oči pozerajú preč od formulára.
   - LOOKING (klik na oko): hlavy k formuláru, červená vycerí plné zuby,
     ružová ukáže zúbky, modrá otvorí hubu - pozerajú na heslo. */
(function () {
  const BUDDIES_SVG = `
    <svg viewBox="0 0 320 400" preserveAspectRatio="xMidYMax meet" aria-hidden="true">
      <!-- RUŽOVÁ: veľký oblúk s rovným dnom, veľké oko, ústa so zúbkami -->
      <g class="bd bd--ghost">
        <path d="M136 132 a77 77 0 0 1 154 0 V400 H136 Z" fill="#f7b6cf"/>
        <g class="bd__head">
          <circle cx="204" cy="192" r="31" fill="#fff"/>
          <circle class="eye" data-cx="204" data-cy="192" data-r="13" cx="204" cy="192" r="13" fill="#333333"/>
          <g class="mouth" data-cx="252" data-cy="240" data-r="4">
            <ellipse cx="252" cy="240" rx="10" ry="12" fill="#b85c78"/>
            <rect x="245.5" y="230" width="6" height="6.5" rx="2" fill="#fff"/>
            <rect x="252.5" y="230" width="6" height="6.5" rx="2" fill="#fff"/>
          </g>
        </g>
      </g>

      <!-- ČERVENÁ: pilulková hlava s očami NAVRCHU, plné zuby, krížené nohy -->
      <g class="bd bd--tall">
        <rect class="leg leg--l" x="80" y="95" width="16" height="305" rx="8" fill="#e84c86"/>
        <rect class="leg leg--r" x="102" y="95" width="16" height="305" rx="8" fill="#e84c86"/>
        <g class="bd__head">
          <!-- zavretá huba (idle/away): pilulka s bielou čiarkou -->
          <g class="mouth-closed">
            <rect x="20" y="69" width="126" height="46" rx="20" fill="#e84c86"/>
            <rect class="mouth" data-cx="120" data-cy="74" data-r="4" x="108" y="83" width="24" height="11" rx="5.5" fill="#fff"/>
          </g>
          <!-- otvorená huba s plnými zubami (looking) -->
          <g class="mouth-open">
            <rect x="22" y="65" width="130" height="46" rx="23" fill="#e84c86"/>
            <rect x="32" y="75" width="110" height="26" rx="8" fill="#fff"/>
            <g stroke="#e84c86" stroke-width="2">
              <line x1="48" y1="75" x2="48" y2="109"/><line x1="64" y1="75" x2="64" y2="109"/>
              <line x1="80" y1="75" x2="80" y2="109"/><line x1="96" y1="75" x2="96" y2="109"/>
              <line x1="112" y1="75" x2="112" y2="109"/><line x1="128" y1="75" x2="128" y2="109"/>
            </g>
          </g>
          <!-- oči NAVRCHU hlavy -->
          <circle cx="76" cy="61" r="15" fill="#fff"/><circle cx="104" cy="61" r="15" fill="#fff"/>
          <circle class="eye" data-cx="76" data-cy="46" data-r="6.5" cx="76" cy="61" r="6.5" fill="#333333"/>
          <circle class="eye" data-cx="104" data-cy="46" data-r="6.5" cx="104" cy="61" r="6.5" fill="#333333"/>
        </g>
      </g>

      <!-- TYRKYSOVÁ: chlpatá guľa, ústa: malé (idle) / široká čiarka (away) -->
      <g class="bd bd--fluff">
        <rect class="leg leg--l" x="66" y="262" width="14" height="138" rx="7" fill="#84d6d0"/>
        <rect class="leg leg--r" x="96" y="262" width="14" height="138" rx="7" fill="#84d6d0"/>
        <g class="bd__head">
          <circle cx="86" cy="228" r="50" fill="#84d6d0"/>
          <circle cx="56" cy="202" r="19" fill="#84d6d0"/><circle cx="114" cy="200" r="19" fill="#84d6d0"/>
          <circle cx="46" cy="240" r="16" fill="#84d6d0"/><circle cx="124" cy="244" r="16" fill="#84d6d0"/>
          <circle cx="66" cy="256" r="14" fill="#84d6d0"/><circle cx="106" cy="260" r="14" fill="#84d6d0"/>
          <circle cx="72" cy="222" r="14.5" fill="#fff"/><circle cx="100" cy="222" r="14.5" fill="#fff"/>
          <circle class="eye" data-cx="72" data-cy="222" data-r="6.5" cx="72" cy="222" r="6.5" fill="#333333"/>
          <circle class="eye" data-cx="100" data-cy="222" data-r="6.5" cx="100" cy="222" r="6.5" fill="#333333"/>
          <ellipse class="mouth mouth-fluff-small" data-cx="87" data-cy="248" data-r="3" cx="87" cy="248" rx="8" ry="6" fill="#2f8b85"/>
          <rect class="mouth-fluff-dash" x="70" y="243" width="34" height="10" rx="5" fill="#2f8b85"/>
        </g>
      </g>

      <!-- MODRÁ: guľatá, ústa: malé / otvorené so zúbkami (looking) -->
      <g class="bd bd--blue">
        <rect class="leg leg--l" x="142" y="322" width="14" height="78" rx="7" fill="#3a9bf5"/>
        <rect class="leg leg--r" x="172" y="322" width="14" height="78" rx="7" fill="#3a9bf5"/>
        <g class="bd__head">
          <circle cx="163" cy="292" r="44" fill="#3a9bf5"/>
          <circle cx="150" cy="282" r="14" fill="#fff"/><circle cx="176" cy="282" r="14" fill="#fff"/>
          <circle class="eye" data-cx="150" data-cy="282" data-r="6" cx="150" cy="282" r="6" fill="#333333"/>
          <circle class="eye" data-cx="176" data-cy="282" data-r="6" cx="176" cy="282" r="6" fill="#333333"/>
          <ellipse class="mouth mouth-blue-small" data-cx="164" data-cy="308" data-r="3" cx="164" cy="308" rx="7" ry="5.5" fill="#0a4a8f"/>
          <g class="mouth-blue-open">
            <ellipse cx="164" cy="311" rx="10" ry="11" fill="#0a4a8f"/>
            <rect x="158.5" y="302" width="5" height="5.5" rx="1.8" fill="#fff"/>
            <rect x="165.5" y="302" width="5" height="5.5" rx="1.8" fill="#fff"/>
          </g>
        </g>
      </g>
    </svg>`;

  document.addEventListener("DOMContentLoaded", function () {
    const mount = document.getElementById("buddies-mount");
    if (!mount) return;
    mount.innerHTML = BUDDIES_SVG;

    const svg = mount.querySelector("svg");
    const hero = mount.closest(".auth-hero");
    const movers = [].slice.call(mount.querySelectorAll(".eye, .mouth"));
    const isRight = hero && hero.classList.contains("auth-hero--right");
    const dirToForm = isRight ? -1 : 1;

    let state = "idle";

    function follow(clientX, clientY) {
      if (state !== "idle") return;
      const r = svg.getBoundingClientRect();
      const vb = svg.viewBox.baseVal;
      const sx = vb.width / r.width, sy = vb.height / r.height;
      const mx = (clientX - r.left) * sx, my = (clientY - r.top) * sy;
      movers.forEach(function (el) {
        const ex = +el.dataset.cx, ey = +el.dataset.cy, mo = +el.dataset.r;
        const dx = mx - ex, dy = my - ey, d = Math.hypot(dx, dy) || 1;
        const ox = dx / d * Math.min(mo, d), oy = dy / d * Math.min(mo, d);
        el.setAttribute("transform", "translate(" + ox.toFixed(1) + "," + oy.toFixed(1) + ")");
      });
    }
    document.addEventListener("mousemove", function (e) { follow(e.clientX, e.clientY); });

    function setGaze(sign, up) {
      movers.forEach(function (el) {
        const mo = +el.dataset.r;
        el.setAttribute("transform", "translate(" + (dirToForm * sign * mo).toFixed(1) + "," + ((up || 0) * mo).toFixed(1) + ")");
      });
    }

    function apply(next) {
      state = next;
      hero.classList.remove("buddies-away", "buddies-looking");
      if (next === "away") { hero.classList.add("buddies-away"); setGaze(-1, 0.15); }
      else if (next === "looking") { hero.classList.add("buddies-looking"); setGaze(1, -0.45); }
    }

    window.adaptpyBuddiesPeek = function (show) { apply(show ? "looking" : "idle"); };

    function isPw(el) {
      return el && el.tagName === "INPUT" &&
        (el.type === "password" || el.type === "text") &&
        (el.id === "password" || el.id === "new_password" || el.id === "new_password_confirm" ||
         el.getAttribute("autocomplete") === "current-password" ||
         el.getAttribute("autocomplete") === "new-password");
    }
    function onPwActivity(e) {
      const el = e.target;
      if (!isPw(el)) return;
      if (el.type === "password") apply("away");
      else apply("looking");
    }
    document.addEventListener("focusin", onPwActivity);
    document.addEventListener("input", onPwActivity);
    document.addEventListener("focusout", function (e) { if (isPw(e.target)) apply("idle"); });
  });
})();
