/* ============================================================
   AdaptPy - KONTROLA ORIGINALITY v editore odpovede (CodeMirror 5).
   Použité v Úlohách, predteste a hlavnom teste.

   1. Zakáže vkladanie textu zvonku (Ctrl+V, pravé tlačidlo, drag&drop).
      Vložiť sa dá len to, čo si študent skopíroval/vystrihol v tom istom editore
      (presun vlastného kódu), nie text z webu, AI ani zo zadania.
   2. Počíta, ako študent píše v úseku od posledného započítaného odoslania:
      napísané znaky, opravy (mazanie, undo, prepísanie výberu), zablokované
      vloženia, rytmus kláves. Metriky idú na server spolu s kódom.
   3. Ak server vyhodnotí písanie ako podozrivé (needs_confirmation), vyskočí okno,
      v ktorom študent potvrdí, ako kód vznikol. Až potom sa odpoveď odošle.

   O podozrivosti rozhoduje server (backend/services/integrity.py), nie tento súbor.
   ============================================================ */
(function () {
  const PAUSE_MS = 5000;          // dlhšia prestávka sa nepočíta do času písania
  const RHYTHM_MAX_GAP = 2000;    // do rytmu idú len intervaly kratšie ako toto (bez premýšľania)
  const SAME_KEY_MS = 8;          // zmeny do 8 ms po sebe sú jeden úder (Enter + odsadenie)
  const BULK_INPUT = 30;          // "+input" s viac nemedzerovými znakmi naraz = vloženie obídené
  const MAX_INTERVALS = 3000;

  function tr(key, fb) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  }

  const REASON_TEXT = {
    no_corrections: ["orig.reason.no_corrections", "kód bol napísaný súvisle, bez jedinej opravy či zmazania"],
    unexplained_insert: ["orig.reason.unexplained_insert", "v kóde je viac textu, než bolo napísané na klávesnici (vloženie cez terminál)"],
    uniform_rhythm: ["orig.reason.uniform_rhythm", "písanie má strojovo pravidelný rytmus"],
    too_fast: ["orig.reason.too_fast", "kód bol napísaný nezvyčajne rýchlo"],
    no_telemetry: ["orig.reason.no_telemetry", "chýbajú údaje o písaní z editora"],
  };
  function reasonText(r) {
    const d = REASON_TEXT[r];
    return d ? tr(d[0], d[1]) : r;
  }

  const norm = (s) => String(s || "").replace(/\r\n?/g, "\n").trim();

  // ---------- krátke upozornenie pri zablokovanom vložení ----------
  let toastEl = null, toastTimer = null;
  function toast(text) {
    if (!toastEl) {
      toastEl = document.createElement("div");
      toastEl.className = "orig-toast";
      toastEl.setAttribute("role", "status");
      toastEl.setAttribute("aria-live", "polite");
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = text;
    toastEl.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove("is-visible"), 2600);
  }

  // Čo študent skopíroval/vystrihol v editoroch NA TEJTO STRÁNKE (smie vložiť späť,
  // aj do inej bunky cvičenia). Text zvonku tu nikdy nie je.
  let recentCopies = [];

  // ---------- strážca jedného editora ----------
  function attach(cm) {
    let m;                       // metriky aktuálneho úseku
    let intervals = [];
    let lastKeyAt = 0;
    let allowPaste = false;

    function fresh() {
      m = {
        typed_chars: 0, keystrokes: 0, corrections: 0, deleted_chars: 0,
        paste_blocked: 0, internal_chars: 0, active_ms: 0,
        baseline_len: cm.getValue().length,
      };
      intervals = [];
      lastKeyAt = 0;
    }

    function blocked() {
      m.paste_blocked += 1;
      toast(tr("orig.pasteBlocked", "Vkladanie textu do odpovede nie je povolené. Napíš kód sám."));
    }

    // kopírovanie / vystrihnutie v editore: zapamätaj si text (CodeMirror bez výberu kopíruje celý riadok)
    function rememberCopy() {
      let text = cm.getSelection();
      if (!text) {
        text = cm.listSelections().map(s => cm.getLine(s.head.line)).join("\n");
      }
      if (!norm(text)) return;
      recentCopies = [norm(text), ...recentCopies.filter(t => t !== norm(text))].slice(0, 10);
    }
    cm.on("copy", rememberCopy);
    cm.on("cut", rememberCopy);

    cm.on("paste", (_cm, e) => {
      let text = "";
      try { text = (e.clipboardData || window.clipboardData).getData("text"); } catch (err) {}
      if (text && recentCopies.includes(norm(text))) { allowPaste = true; return; }
      e.preventDefault();
      blocked();
    });
    cm.on("drop", (_cm, e) => { e.preventDefault(); blocked(); });

    cm.on("beforeChange", (_cm, change) => {
      const origin = change.origin || "";
      if (origin === "paste" || origin === "drop") {
        if (origin === "paste" && allowPaste) { allowPaste = false; return; }
        change.cancel();
        if (origin === "paste") blocked();     // vloženie, ktoré obišlo udalosť "paste"
        return;
      }
      if (origin === "+input") {
        const text = (change.text || []).join("\n");
        if (text.replace(/\s/g, "").length > BULK_INPUT) {   // celý blok naraz = nie písanie
          change.cancel();
          blocked();
        }
      }
    });

    cm.on("change", (_cm, change) => {
      const origin = change.origin || "";
      if (origin === "setValue") return;
      const inserted = (change.text || []).join("\n").length;
      const removed = (change.removed || []).join("\n").length;

      if (origin === "+input" || origin === "*compose") {
        m.typed_chars += inserted;
        if (removed > 0) { m.corrections += 1; m.deleted_chars += removed; }  // prepísanie výberu
        const now = performance.now();
        if (lastKeyAt && now - lastKeyAt < SAME_KEY_MS) return;   // ten istý úder (odsadenie)
        m.keystrokes += 1;
        if (lastKeyAt) {
          const gap = now - lastKeyAt;
          m.active_ms += Math.min(gap, PAUSE_MS);
          if (gap <= RHYTHM_MAX_GAP && intervals.length < MAX_INTERVALS) intervals.push(gap);
        }
        lastKeyAt = now;
        return;
      }
      if (origin === "+delete" || origin === "cut") {
        m.corrections += 1;
        m.deleted_chars += removed;
        return;
      }
      if (origin === "undo" || origin === "redo") {
        m.corrections += 1;
        m.internal_chars += inserted;
        m.deleted_chars += removed;
        return;
      }
      // vložený vlastný kód, odsadenie (Tab), presun riadkov a pod. - vysvetľuje nárast kódu
      m.internal_chars += inserted;
      if (removed > 0) m.deleted_chars += removed;
    });

    function intervalCv() {
      if (intervals.length < 10) return null;
      const mean = intervals.reduce((a, b) => a + b, 0) / intervals.length;
      if (!mean) return null;
      const variance = intervals.reduce((a, b) => a + (b - mean) * (b - mean), 0) / intervals.length;
      return Math.round((Math.sqrt(variance) / mean) * 1000) / 1000;
    }

    fresh();

    return {
      /** Nový úsek (po načítaní otázky/úlohy alebo po započítanom odoslaní).
          clearHistory: po programovom setValue, aby Ctrl+Z nevrátilo kód inej úlohy. */
      reset({ clearHistory = false } = {}) {
        if (clearHistory) { cm.clearHistory(); recentCopies = []; }
        fresh();
      },
      /** Objekt `integrity` do tela požiadavky. */
      payload(confirmation) {
        const out = {
          ...m, active_ms: Math.round(m.active_ms), interval_cv: intervalCv(),
        };
        if (confirmation) out.confirmation = confirmation;
        return out;
      },
      /** Uloženie/obnovenie stavu (Úlohy pri zmene jazyka obnovia stránku). */
      exportState() { return { m: { ...m }, intervals: intervals.slice() }; },
      importState(s) {
        if (!s || !s.m) return;
        m = { ...m, ...s.m };
        intervals = Array.isArray(s.intervals) ? s.intervals.slice(0, MAX_INTERVALS) : [];
      },
    };
  }

  // ---------- potvrdzovacie okno ----------
  function confirmDialog(reasons) {
    return new Promise((resolve) => {
      const prevFocus = document.activeElement;
      const wrap = document.createElement("div");
      wrap.className = "orig-modal";
      wrap.innerHTML = `
        <div class="orig-modal__box" role="dialog" aria-modal="true" aria-labelledby="orig-title">
          <div class="orig-modal__icon" aria-hidden="true">⚑</div>
          <h2 id="orig-title">${tr("orig.title", "Potvrď, že je to tvoja práca")}</h2>
          <p class="orig-modal__lead">${tr("orig.lead", "Systém si pri tejto odpovedi všimol nezvyčajný spôsob písania:")}</p>
          <ul class="orig-modal__reasons"></ul>
          <fieldset class="orig-modal__choices">
            <legend>${tr("orig.question", "Ako vznikol tento kód?")}</legend>
            <label class="orig-choice">
              <input type="radio" name="orig-choice" value="own_work">
              <span>${tr("orig.ownWork", "Napísal/a som ho sám/sama")}</span>
            </label>
            <label class="orig-choice">
              <input type="radio" name="orig-choice" value="outside_source">
              <span>${tr("orig.outsideSource", "Prepisoval/a som ho z iného zdroja (web, AI, spolužiak, poznámky)")}</span>
            </label>
          </fieldset>
          <p class="orig-modal__note">${tr("orig.note", "Tvoju voľbu uvidí vyučujúci pri tejto odpovedi.")}</p>
          <div class="orig-modal__actions">
            <button type="button" data-orig="ok" disabled>${tr("orig.submit", "Potvrdiť a odoslať")}</button>
          </div>
        </div>`;
      const list = wrap.querySelector(".orig-modal__reasons");
      (reasons || []).forEach((r) => {
        const li = document.createElement("li");
        li.textContent = reasonText(r);
        list.appendChild(li);
      });
      const ok = wrap.querySelector('[data-orig="ok"]');
      wrap.querySelectorAll('input[name="orig-choice"]').forEach((inp) =>
        inp.addEventListener("change", () => { ok.disabled = false; }));

      function close(value) {
        document.removeEventListener("keydown", onKey, true);
        wrap.remove();
        document.body.classList.remove("orig-modal-open");
        try { if (prevFocus && prevFocus.focus) prevFocus.focus(); } catch (e) {}
        resolve(value);
      }
      function onKey(e) {
        if (e.key === "Escape") { e.preventDefault()}
        if (e.key === "Tab") {           // fokus ostáva v okne
          const f = Array.from(wrap.querySelectorAll("input, button:not([disabled])"));
          const i = f.indexOf(document.activeElement);
          if (e.shiftKey && i <= 0) { e.preventDefault(); f[f.length - 1].focus(); }
          else if (!e.shiftKey && i === f.length - 1) { e.preventDefault(); f[0].focus(); }
        }
      }
      ok.addEventListener("click", () => {
        const sel = wrap.querySelector('input[name="orig-choice"]:checked');
        if (sel) close(sel.value);
      });
      document.addEventListener("keydown", onKey, true);

      document.body.appendChild(wrap);
      document.body.classList.add("orig-modal-open");
      const first = wrap.querySelector('input[name="orig-choice"]');
      if (first) first.focus();
    });
  }

  /**
   * Odošle odpoveď s metrikami; ak server chce potvrdenie, ukáže okno a odošle znova.
   *   send(integrity) -> Promise<čokoľvek>   (volanie API stránky)
   *   bodyOf(výsledok) -> telo odpovede (JSON) alebo null
   * Vráti výsledok posledného send(), alebo { cancelled: true }, ak študent okno zavrel.
   */
  async function submit(guard, send, bodyOf) {
    let res = await send(guard.payload());
    let body = bodyOf(res);
    if (body && body.needs_confirmation) {
      const choice = await confirmDialog(body.integrity_reasons);
      if (!choice) return { cancelled: true };
      res = await send(guard.payload(choice));
      body = bodyOf(res);
    }
    if (body && body.counted) guard.reset();
    return res;
  }

  window.Originality = { attach, submit, confirm: confirmDialog, reasonText };
})();
