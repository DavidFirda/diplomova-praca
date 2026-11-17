/* ============================================================
   AdaptPy - AI asistent: spoločná logika chatu (dashboard, cvičenia, úlohy).

   - AiChat.stream(body, handlers)   POST /api/assistant/stream a čítanie SSE udalostí
   - AiChat.history(params)          história konverzácie z DB (obnovenie po návrate)
   - AiChat.view(box, opts)          bubliny správ: markdown, plynulé písanie, zdroje,
                                     tlačidlo "Vložiť do bunky…" pri bloku kódu (len
                                     po potvrdení študentom - samotné vloženie robí stránka)

   Odpoveď kontroluje server (strážca) ešte pred odoslaním; tu sa navyše HTML
   vždy čistí (DOMPurify) a odkazy mimo aplikácie sa zrušia.
   ============================================================ */
window.AiChat = (function () {
  const ROBOT = '<svg class="ul-icon" aria-hidden="true"><use href="#ul-robot"/></svg>';

  function tr(key, fb) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  }
  function lang() { return (typeof I18N !== "undefined" && I18N.lang) || "sk"; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (m) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
  }
  function timeNow() {
    return new Date().toLocaleTimeString(lang() === "sk" ? "sk-SK" : "en-GB", { hour: "2-digit", minute: "2-digit" });
  }

  // ---------------------------------------------------------
  // Markdown -> bezpečné HTML
  // ---------------------------------------------------------
  function fallbackMarkdown(md) {
    // bez knižnice marked: bloky kódu + odseky, všetko escapované
    const parts = String(md || "").split(/```[a-zA-Z0-9_-]*\n?/);
    return parts.map((p, i) => (i % 2 === 1)
      ? `<pre><code>${esc(p.replace(/\n$/, ""))}</code></pre>`
      : esc(p).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
          .split(/\n{2,}/).map((x) => x.trim() ? `<p>${x.replace(/\n/g, "<br>")}</p>` : "").join("")).join("");
  }

  function toHtml(md) {
    let html;
    try {
      html = window.marked ? marked.parse(String(md || ""), { breaks: true, gfm: true }) : fallbackMarkdown(md);
    } catch (e) { html = fallbackMarkdown(md); }
    if (window.DOMPurify) {
      html = DOMPurify.sanitize(html, {
        ALLOWED_TAGS: ["p", "br", "strong", "em", "b", "i", "code", "pre", "ul", "ol", "li", "a",
                       "blockquote", "h3", "h4", "h5", "table", "thead", "tbody", "tr", "th", "td", "hr", "sup", "span"],
        ALLOWED_ATTR: ["href", "title", "class"],
      });
    } else if (window.marked) {
      return fallbackMarkdown(md);        // bez sanitizéra radšej nič z HTML modelu
    }
    return html;
  }

  function linkAllowed(href) {
    return typeof href === "string" && href.startsWith("/") && !href.startsWith("//");
  }

  // [1], [2][3] v texte -> malé čísla zdrojov (nie v kóde)
  function markCitations(root, sources) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (n.parentElement && n.parentElement.closest("pre, code, a")) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
    });
    const nodes = [];
    while (walker.nextNode()) if (/\[\d{1,2}\]/.test(walker.currentNode.nodeValue)) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      const frag = document.createDocumentFragment();
      node.nodeValue.split(/(\[\d{1,2}\])/).forEach((part) => {
        const m = part.match(/^\[(\d{1,2})\]$/);
        if (!m) { frag.appendChild(document.createTextNode(part)); return; }
        const src = (sources || []).find((s) => s.rank === Number(m[1]));
        const sup = document.createElement("sup");
        sup.className = "ai-cite";
        sup.textContent = m[1];
        if (src) sup.title = src.label;
        frag.appendChild(sup);
      });
      node.parentNode.replaceChild(frag, node);
    });
  }

  function renderInto(el, md, sources) {
    el.innerHTML = toHtml(md);
    el.querySelectorAll("a").forEach((a) => {
      const href = a.getAttribute("href");
      if (!linkAllowed(href)) { a.replaceWith(document.createTextNode(a.textContent)); return; }
      a.removeAttribute("target");
    });
    markCitations(el, sources);
  }

  // ---------------------------------------------------------
  // SSE cez fetch (EventSource nevie POST)
  // ---------------------------------------------------------
  async function stream(body, handlers) {
    const h = handlers || {};
    let res;
    try {
      res = await fetch("/api/assistant/stream", {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "Accept": "text/event-stream" },
        body: JSON.stringify({ ...body, lang: lang() }),
      });
    } catch (e) {
      h.onError && h.onError({ error: tr("ai.netError", "Spojenie so serverom zlyhalo.") });
      return;
    }
    if (res.status === 401) { window.location.href = "/login"; return; }
    const ctype = res.headers.get("Content-Type") || "";
    if (!res.ok || !ctype.includes("text/event-stream")) {
      let data = {};
      try { data = await res.json(); } catch (e) { /* prázdne */ }
      h.onError && h.onError({ status: res.status, ...data, error: data.error || tr("ai.error", "Asistent teraz neodpovedá.") });
      return;
    }
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "", finished = false;
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf("\n\n")) !== -1) {
          const raw = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          let event = "message", data = "";
          raw.split("\n").forEach((line) => {
            if (line.startsWith("event:")) event = line.slice(6).trim();
            else if (line.startsWith("data:")) data += line.slice(5).trim();
          });
          let payload = {};
          try { payload = data ? JSON.parse(data) : {}; } catch (e) { continue; }
          if (event === "done" || event === "error") finished = true;
          if (event === "error") h.onError && h.onError(payload);
          else h.onEvent && h.onEvent(event, payload);
        }
      }
    } catch (e) { /* spojenie prerušené */ }
    if (!finished) h.onError && h.onError({ error: tr("ai.interrupted", "Odpoveď sa prerušila. Skús to znova."), interrupted: true });
  }

  async function history(params) {
    const q = new URLSearchParams({ ...params, lang: lang() });
    try {
      const r = await fetch(`/api/assistant/history?${q}`, { credentials: "include" });
      if (!r.ok) return [];
      const d = await r.json();
      return d.messages || [];
    } catch (e) { return []; }
  }

  async function logInsert(messageId, code, target, how) {
    try {
      await fetch("/api/assistant/insert", {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message_id: messageId, code, target, how }),
      });
    } catch (e) { /* log nesmie zablokovať študenta */ }
  }

  // ---------------------------------------------------------
  // Zobrazenie správ
  // ---------------------------------------------------------
  /**
   * @param {HTMLElement} box       kontajner správ
   * @param {Object}      opts
   *   insert: { targets(): [{value,label,selected}], apply(code, target, how): bool, fixedTarget?: string }
   */
  function view(box, opts) {
    const o = opts || {};
    const scrollDown = () => { box.scrollTop = box.scrollHeight; };

    function row(who) {
      const r = document.createElement("div");
      r.className = `ul-row ul-row--${who === "user" ? "user" : "agent"}`;
      if (who !== "user") {
        const av = document.createElement("div");
        av.className = "ul-avatar";
        av.innerHTML = ROBOT;
        r.appendChild(av);
      }
      const wrap = document.createElement("div");
      wrap.className = "ul-bubble-wrap" + (who === "user" ? "" : " ai-wrap");
      r.appendChild(wrap);
      box.appendChild(r);
      return { r, wrap };
    }

    function stamp(wrap, when) {
      const t = document.createElement("span");
      t.className = "ul-time";
      t.textContent = when ? new Date(when).toLocaleTimeString(lang() === "sk" ? "sk-SK" : "en-GB",
        { hour: "2-digit", minute: "2-digit" }) : timeNow();
      wrap.appendChild(t);
    }

    function user(text, when) {
      const { wrap } = row("user");
      const b = document.createElement("div");
      b.className = "ul-msg ul-msg--user";
      b.textContent = text;
      wrap.appendChild(b);
      stamp(wrap, when);
      scrollDown();
    }

    function note(text) {
      const n = document.createElement("div");
      n.className = "ai-note";
      n.textContent = text;
      box.appendChild(n);
      scrollDown();
    }

    function plain(text, withTime = false) {
      const m = assistant();
      m.set(text);
      m.finish({ withTime });
      return m;
    }

    function assistant() {
      const { r, wrap } = row("agent");
      const bubble = document.createElement("div");
      bubble.className = "ul-msg ul-msg--agent ai-msg";
      const statusEl = document.createElement("div");
      statusEl.className = "ai-status";
      statusEl.innerHTML = `<span class="ul-typing"><i></i><i></i><i></i></span><span class="ai-status__text"></span>`;
      const body = document.createElement("div");
      body.className = "ai-body";
      bubble.appendChild(statusEl);
      bubble.appendChild(body);
      wrap.appendChild(bubble);
      scrollDown();

      let text = "", sources = [], raf = 0, messageId = null;
      const atBottom = () => box.scrollHeight - box.scrollTop - box.clientHeight < 60;
      function paint() {
        raf = 0;
        const stick = atBottom();
        renderInto(body, text, sources);
        if (stick) scrollDown();
      }
      function schedule() { if (!raf) raf = requestAnimationFrame(paint); }

      const ctl = {
        el: r,
        status(state) {
          const label = { searching: tr("ai.searching", "Hľadám v prednáškach…"),
                          thinking: tr("ai.thinking", "Premýšľam…"),
                          writing: "" }[state] || "";
          statusEl.querySelector(".ai-status__text").textContent = label;
          statusEl.style.display = state === "writing" && text ? "none" : "";
        },
        append(delta) {
          if (!delta) return;
          text += delta;
          statusEl.style.display = "none";
          bubble.classList.add("is-streaming");
          schedule();
        },
        set(md) { text = md || ""; statusEl.style.display = "none"; paint(); },
        sources(list) { sources = list || []; },
        error(msg) {
          statusEl.style.display = "none";
          bubble.classList.remove("is-streaming");
          bubble.classList.add("ai-msg--error");
          if (!text) body.textContent = msg; else { text += `\n\n_${msg}_`; paint(); }
        },
        finish(info) {
          const i = info || {};
          messageId = i.messageId || messageId;
          if (raf) { cancelAnimationFrame(raf); raf = 0; }
          statusEl.style.display = "none";
          bubble.classList.remove("is-streaming");
          if (text) paint();
          if (sources.length) wrap.appendChild(sourcesEl(sources));
          if (i.allowInsert && o.insert && messageId) addInsertButtons(body, messageId);
          if (i.withTime !== false) stamp(wrap, i.when);
          scrollDown();
        },
        get text() { return text; },
      };
      return ctl;
    }

    function sourcesEl(list) {
      const d = document.createElement("details");
      d.className = "ai-sources";
      const s = document.createElement("summary");
      s.textContent = `${tr("ai.sources", "Zdroje")} (${list.length})`;
      d.appendChild(s);
      const ul = document.createElement("ol");
      list.forEach((src) => {
        const li = document.createElement("li");
        li.value = src.rank;
        if (src.link && linkAllowed(src.link)) {
          const a = document.createElement("a");
          a.href = src.link;
          a.textContent = src.label;
          li.appendChild(a);
        } else li.textContent = src.label;
        ul.appendChild(li);
      });
      d.appendChild(ul);
      return d;
    }

    function addInsertButtons(body, messageId) {
      body.querySelectorAll("pre").forEach((pre) => {
        const code = pre.innerText.replace(/\n$/, "");
        if (!code.trim()) return;
        const bar = document.createElement("div");
        bar.className = "ai-insert";
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "ai-insert__btn";
        btn.textContent = o.insert.fixedTarget ? tr("ai.insertEditor", "Vložiť do editora…") : tr("ai.insertCell", "Vložiť do bunky…");
        bar.appendChild(btn);
        pre.after(bar);
        btn.addEventListener("click", () => openInsert(bar, code, messageId));
      });
    }

    // potvrdenie: do ktorej bunky a ako (nahradiť / pridať na koniec)
    function openInsert(bar, code, messageId) {
      if (bar.querySelector(".ai-confirm")) return;
      const targets = o.insert.fixedTarget ? [] : (o.insert.targets() || []);
      const group = `how-${messageId}-${Math.random().toString(36).slice(2, 8)}`;
      const form = document.createElement("div");
      form.className = "ai-confirm";
      form.innerHTML = `
        <div class="ai-confirm__q">${esc(o.insert.fixedTarget
          ? tr("ai.confirmEditor", "Vložiť tento kód do editora?")
          : tr("ai.confirmCell", "Do ktorej bunky mám kód vložiť?"))}</div>
        ${targets.length ? `<select class="ai-confirm__target">${targets.map((t) =>
          `<option value="${esc(t.value)}" ${t.selected ? "selected" : ""}>${esc(t.label)}</option>`).join("")}</select>` : ""}
        <div class="ai-confirm__how">
          <label><input type="radio" name="${group}" value="append" checked> ${esc(tr("ai.howAppend", "pridať na koniec"))}</label>
          <label><input type="radio" name="${group}" value="replace"> ${esc(tr("ai.howReplace", "nahradiť obsah"))}</label>
        </div>
        <div class="ai-confirm__actions">
          <button type="button" class="ai-confirm__ok">${esc(tr("ai.insertOk", "Vložiť"))}</button>
          <button type="button" class="ai-confirm__cancel">${esc(tr("ai.insertCancel", "Zrušiť"))}</button>
        </div>`;
      bar.appendChild(form);
      scrollDown();
      form.querySelector(".ai-confirm__cancel").addEventListener("click", () => form.remove());
      form.querySelector(".ai-confirm__ok").addEventListener("click", () => {
        const sel = form.querySelector(".ai-confirm__target");
        const target = o.insert.fixedTarget || (sel && sel.value);
        const how = (form.querySelector('.ai-confirm__how input:checked') || {}).value || "append";
        if (!target) return;
        const ok = o.insert.apply(code, target, how);
        form.remove();
        if (ok) {
          const done = document.createElement("span");
          done.className = "ai-insert__done";
          const t = targets.find((x) => x.value === target) || {};
          const label = o.insert.fixedTarget ? tr("ai.insertedEditor", "vložené do editora")
            : `${tr("ai.insertedCell", "vložené do bunky")} ${t.label || target}`;
          done.textContent = "✓ " + label;
          bar.appendChild(done);
          // do logu ide čitateľný názov cieľa (napr. "Bunka 3"), admin ho vidí v konverzácii
          logInsert(messageId, code, t.short || target, how);
        }
      });
    }

    function restore(messages) {
      (messages || []).forEach((m) => {
        if (m.role === "student") user(m.text, m.created_at);
        else if (m.role === "assistant") {
          const c = assistant();
          c.sources(m.sources || []);
          if (m.status === "error") c.error(m.text);
          else c.set(m.text);
          c.finish({ messageId: m.id, allowInsert: !!m.allow_insert, when: m.created_at });
        } else if (m.role === "event" && m.kind === "insert") {
          const target = (m.context && m.context.target) || "";
          note(`✓ ${tr("ai.insertLog", "Kód z odpovede vložený")}${target ? " → " + target : ""}`);
        }
      });
      scrollDown();
    }

    return { user, assistant, plain, note, restore, scrollDown, clear: () => { box.innerHTML = ""; } };
  }

  /**
   * Jedna otázka: bublina študenta + streamovaná odpoveď. Vráti Promise s info o konci.
   * opts: { showUser: bool, userText, onDone(data), onError(data), onMeta(data) }
   */
  function ask(v, body, opts) {
    const o = opts || {};
    if (o.showUser !== false && o.userText) v.user(o.userText);
    const m = v.assistant();
    m.status(body.mode === "dashboard" ? "writing" : "searching");
    return new Promise((resolve) => {
      stream(body, {
        onEvent(ev, d) {
          if (ev === "meta") o.onMeta && o.onMeta(d);
          else if (ev === "status") m.status(d.state);
          else if (ev === "sources") m.sources(d.sources);
          else if (ev === "delta") m.append(d.text);
          else if (ev === "replace") m.set(d.text);
          else if (ev === "done") {
            m.finish({ messageId: d.message_id, allowInsert: d.allow_insert });
            o.onDone && o.onDone(d);
            resolve({ ok: true, data: d });
          }
        },
        onError(d) {
          m.error(d.error || tr("ai.error", "Asistent teraz neodpovedá."));
          m.finish({ withTime: false });
          o.onError && o.onError(d);
          resolve({ ok: false, data: d });
        },
      });
    });
  }

  return { stream, history, view, ask, toHtml, logInsert };
})();
