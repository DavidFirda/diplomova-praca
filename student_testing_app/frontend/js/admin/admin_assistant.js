/* ============================================================
   AdaptPy - Admin: AI asistent.
     Prehľad      počty otázok podľa režimu, časy odpovedí, nápovedy, zásahy strážcu,
                  najčastejšie zdroje RAG
     Konverzácie  zoznam (filter študent / režim / text / len so zásahom strážcu),
                  detail so zdrojmi RAG pri každej odpovedi, export do CSV
     Model        model, uvažovanie (think), teplota, zapnutie; stav Ollamy, test
   ============================================================ */
(function () {
  const $ = (id) => document.getElementById(id);
  const tr = (key, fb) => {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (m) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
  const when = (iso) => iso ? new Date(iso).toLocaleString("sk-SK", { dateStyle: "short", timeStyle: "short" }) : "–";
  const ms = (v) => v == null ? "–" : (v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${v} ms`);
  const MODE = { dashboard: "Dashboard", exercise: "Cvičenie", task: "Úloha" };

  const params = new URLSearchParams(location.search);
  const filters = {
    student_id: params.get("student_id") || "", mode: params.get("mode") || "",
    q: "", days: "", guard: "",
  };

  async function api(path, opts) {
    const r = await fetch(`/api/admin/assistant${path}`, { credentials: "include", ...(opts || {}) });
    if (r.status === 401) { location.href = "/login"; throw new Error("401"); }
    if (r.status === 403) { location.href = "/dashboard"; throw new Error("403"); }
    let d = {};
    try { d = await r.json(); } catch (e) { /* prázdne */ }
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
    return d;
  }
  const qs = () => new URLSearchParams(Object.fromEntries(Object.entries(filters).filter(([, v]) => v))).toString();

  // ---------- záložky ----------
  document.querySelectorAll(".ai-admin-tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.tab)));
  function show(tab) {
    document.querySelectorAll(".ai-admin-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    ["overview", "conversations", "settings"].forEach((t) => { $(`tab-${t}`).hidden = t !== tab; });
    if (tab === "overview") loadOverview();
    if (tab === "conversations") loadConversations();
    if (tab === "settings") loadSettings();
  }

  // ---------- prehľad ----------
  async function loadOverview() {
    const el = $("tab-overview");
    el.innerHTML = `<p class="ai-muted">${tr("aiA.loading", "Načítavam…")}</p>`;
    let d;
    try { d = await api(`/stats?${qs()}`); } catch (e) { el.innerHTML = `<p>${esc(e.message)}</p>`; return; }
    const q = (m) => (d.by_mode[m] || {}).student || 0;
    const kpi = (v, l) => `<div class="ai-kpi"><div class="ai-kpi__v">${esc(v)}</div><div class="ai-kpi__l">${esc(l)}</div></div>`;
    const hints = d.hints_by_level || {};
    el.innerHTML = `
      ${filterNote()}
      <div class="ai-admin-card">
        <h3>${tr("aiA.ovTitle", "Používanie")}</h3>
        <div class="ai-kpis">
          ${kpi(q("dashboard"), tr("aiA.qDashboard", "otázok – dashboard"))}
          ${kpi(q("exercise"), tr("aiA.qExercise", "otázok – cvičenia"))}
          ${kpi(q("task"), tr("aiA.qTask", "otázok/nápoved – úlohy"))}
          ${kpi(d.answers, tr("aiA.answers", "odpovedí spolu"))}
          ${kpi(ms(d.avg_first_token_ms), tr("aiA.firstToken", "priemer do prvého slova"))}
          ${kpi(ms(d.avg_latency_ms), tr("aiA.latency", "priemer celej odpovede"))}
          ${kpi(d.avg_tokens_out ?? "–", tr("aiA.tokens", "priem. tokenov odpovede"))}
          ${kpi(d.inserts, tr("aiA.inserts", "vložení kódu do bunky"))}
        </div>
        <p class="ai-muted" style="margin-top:10px">${tr("aiA.statuses", "Stav odpovedí")}: ${
          Object.entries(d.statuses || {}).map(([k, v]) => `${esc(k)} ${esc(v)}`).join(" · ") || "–"}
          · ${tr("aiA.hints", "Nápovedy podľa úrovne")}: 1 → ${hints["1"] || 0}, 2 → ${hints["2"] || 0}, 3 → ${hints["3"] || 0}</p>
      </div>
      <div class="ai-admin-card">
        <h3>${tr("aiA.topSources", "Najčastejšie zdroje RAG")}</h3>
        ${d.top_sources.length ? `<table class="ai-table"><thead><tr><th>${tr("aiA.type", "Typ")}</th><th>${tr("aiA.material", "Materiál")}</th><th>${tr("aiA.count", "Použité")}</th></tr></thead><tbody>${
          d.top_sources.map((s) => `<tr><td>${s.type === "prednaska" ? tr("mat.lecture", "Prednáška") + (s.lecture_no != null ? " " + s.lecture_no : "") : tr("mat.book", "Kniha")}</td><td>${esc(s.title)}</td><td>${s.count}×</td></tr>`).join("")
        }</tbody></table>` : `<p class="ai-muted">${tr("aiA.none", "Zatiaľ žiadne.")}</p>`}
      </div>`;
    bindFilterNote();
  }

  function filterNote() {
    if (!filters.student_id) return "";
    return `<p class="ai-muted">${tr("aiA.filteredStudent", "Filtrované na študenta")} #${esc(filters.student_id)} ·
      <a href="#" id="ai-clear-student">${tr("aiA.clearFilter", "zrušiť filter")}</a></p>`;
  }
  function bindFilterNote() {
    const a = $("ai-clear-student");
    if (a) a.addEventListener("click", (e) => {
      e.preventDefault();
      filters.student_id = "";
      history.replaceState(null, "", location.pathname);
      const active = document.querySelector(".ai-admin-tabs button.active");
      show(active ? active.dataset.tab : "overview");
    });
  }

  // ---------- konverzácie ----------
  let offset = 0;
  async function loadConversations() {
    const el = $("tab-conversations");
    if (!el.dataset.ready) {
      el.innerHTML = `
        <div class="ai-admin-card">
          ${filterNote()}
          <div class="ai-filters">
            <input type="search" id="f-q" placeholder="${esc(tr("aiA.search", "Hľadať text alebo študenta…"))}">
            <select id="f-mode">
              <option value="">${tr("aiA.allModes", "Všetky režimy")}</option>
              <option value="dashboard">Dashboard</option>
              <option value="exercise">${tr("aiA.exercise", "Cvičenia")}</option>
              <option value="task">${tr("aiA.task", "Úlohy")}</option>
            </select>
            <select id="f-days">
              <option value="">${tr("aiA.allTime", "Celé obdobie")}</option>
              <option value="1">${tr("aiA.day", "Posledný deň")}</option>
              <option value="7">${tr("aiA.week", "Posledný týždeň")}</option>
              <option value="30">${tr("aiA.month", "Posledných 30 dní")}</option>
            </select>
            <label class="ai-muted"><input type="checkbox" id="f-guard" class="ai-toggle"> ${tr("aiA.onlyGuard", "len so zásahom strážcu")}</label>
            <button type="button" id="f-apply">${tr("aiA.filter", "Filtrovať")}</button>
            <button type="button" id="f-export" class="btn--secondary">${tr("aiA.export", "Export CSV")}</button>
          </div>
          <div id="conv-list"></div>
        </div>
        <div id="conv-detail"></div>`;
      el.dataset.ready = "1";
      $("f-mode").value = filters.mode;
      $("f-apply").addEventListener("click", () => { readFilters(); offset = 0; refreshList(); });
      $("f-q").addEventListener("keydown", (e) => { if (e.key === "Enter") { readFilters(); offset = 0; refreshList(); } });
      $("f-export").addEventListener("click", () => { readFilters(); location.href = `/api/admin/assistant/export.csv?${qs()}`; });
      bindFilterNote();
    }
    refreshList();
  }

  function readFilters() {
    filters.q = $("f-q").value.trim();
    filters.mode = $("f-mode").value;
    filters.days = $("f-days").value;
    filters.guard = $("f-guard").checked ? "1" : "";
  }

  async function refreshList() {
    const el = $("conv-list");
    el.innerHTML = `<p class="ai-muted">${tr("aiA.loading", "Načítavam…")}</p>`;
    let d;
    try { d = await api(`/conversations?${qs()}&limit=50&offset=${offset}`); }
    catch (e) { el.innerHTML = `<p>${esc(e.message)}</p>`; return; }
    if (!d.conversations.length) { el.innerHTML = `<p class="ai-muted">${tr("aiA.noConv", "Žiadne konverzácie.")}</p>`; return; }
    el.innerHTML = `
      <div class="ai-table-wrap"><table class="ai-table">
        <thead><tr><th>${tr("aiA.student", "Študent")}</th><th>${tr("aiA.context", "Kde")}</th><th>${tr("aiA.questions", "Otázky")}</th>
          <th>${tr("aiA.hintsShort", "Nápovedy")}</th><th>${tr("aiA.guardShort", "Strážca")}</th><th>${tr("aiA.insertsShort", "Vložené")}</th><th>${tr("aiA.last", "Posledná aktivita")}</th></tr></thead>
        <tbody>${d.conversations.map((c) => `
          <tr class="is-clickable" data-id="${c.id}">
            <td><strong>${esc(c.student_name)}</strong><br><span class="ai-muted">${esc(c.student_login)}</span></td>
            <td><span class="ai-badge ai-badge--info">${esc(MODE[c.mode] || c.mode)}</span><br><span class="ai-muted">${esc(c.context)}</span></td>
            <td>${c.questions}</td><td>${c.hints || "–"}</td>
            <td>${c.guard_hits ? `<span class="ai-badge ai-badge--warn">${c.guard_hits}</span>` : "–"}</td>
            <td>${c.inserts || "–"}</td><td>${when(c.updated_at)}</td>
          </tr>`).join("")}</tbody></table></div>
      <div class="ai-filters" style="margin-top:10px">
        <span class="ai-muted">${offset + 1}–${offset + d.conversations.length} / ${d.total}</span>
        ${offset > 0 ? `<button type="button" id="p-prev" class="btn--secondary">←</button>` : ""}
        ${offset + d.conversations.length < d.total ? `<button type="button" id="p-next" class="btn--secondary">→</button>` : ""}
      </div>`;
    el.querySelectorAll("tr[data-id]").forEach((tr_) => tr_.addEventListener("click", () => openConversation(tr_.dataset.id)));
    const prev = $("p-prev"), next = $("p-next");
    if (prev) prev.addEventListener("click", () => { offset = Math.max(0, offset - 50); refreshList(); });
    if (next) next.addEventListener("click", () => { offset += 50; refreshList(); });
  }

  function guardText(g) {
    const RULE = {
      similar_to_solution: tr("aiA.rule.similar", "kód podobný riešeniu"),
      solves_task: tr("aiA.rule.solves", "kód po spustení vyrieši úlohu"),
      solution_line_in_text: tr("aiA.rule.line", "riadok riešenia v texte"),
      solution_in_answer: tr("aiA.rule.answer", "riešenie v odpovedi"),
      full_exercise_solution: tr("aiA.rule.fullEx", "celá implementácia funkcie zo cvičenia"),
      long_code: tr("aiA.rule.long", "príliš dlhý kód"),
      code_in_dashboard: tr("aiA.rule.dashCode", "kód na dashboarde"),
      dashboard_forbidden: tr("aiA.rule.forbidden", "interné informácie aplikácie"),
      link_not_allowed: tr("aiA.rule.link", "nepovolený odkaz"),
      run_check_unavailable: tr("aiA.rule.runner", "overenie spustením nedostupné"),
    };
    return g.map((h) => `${RULE[h.rule] || h.rule} → ${h.action}${h.detail ? ` (${h.detail})` : ""}`).join("; ");
  }

  async function openConversation(id) {
    const el = $("conv-detail");
    el.innerHTML = `<div class="ai-admin-card"><p class="ai-muted">${tr("aiA.loading", "Načítavam…")}</p></div>`;
    let d;
    try { d = await api(`/conversations/${id}`); } catch (e) { el.innerHTML = `<p>${esc(e.message)}</p>`; return; }
    const c = d.conversation;
    el.innerHTML = `
      <div class="ai-admin-card">
        <h3>${esc(c.student_name)} (${esc(c.student_login)}) · ${esc(MODE[c.mode] || c.mode)} · ${esc(c.context)}</h3>
        <div class="ai-filters">
          <span class="ai-muted">${tr("aiA.started", "Začiatok")}: ${when(c.created_at)} · ${tr("aiA.last", "Posledná aktivita")}: ${when(c.updated_at)}</span>
          <button type="button" class="btn--secondary" id="conv-export">${tr("aiA.exportOne", "Export tejto konverzácie")}</button>
          <button type="button" class="danger" id="conv-delete">${tr("aiA.delete", "Zmazať konverzáciu")}</button>
        </div>
        <div class="ai-conv">${d.messages.map(messageHtml).join("")}</div>
      </div>`;
    el.querySelectorAll(".ai-conv__text[data-md]").forEach((t) => {
      t.innerHTML = AiChat.toHtml(t.textContent);
    });
    $("conv-export").addEventListener("click", () => {
      location.href = `/api/admin/assistant/export.csv?student_id=${c.student_id}&mode=${c.mode}`;
    });
    $("conv-delete").addEventListener("click", async () => {
      if (!confirm(tr("aiA.deleteConfirm", "Naozaj zmazať celú konverzáciu? Nedá sa to vrátiť."))) return;
      try { await api(`/conversations/${id}`, { method: "DELETE" }); el.innerHTML = ""; refreshList(); }
      catch (e) { alert(e.message); }
    });
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function messageHtml(m) {
    const who = m.role === "student" ? tr("aiA.roleStudent", "Študent") : m.role === "assistant" ? tr("aiA.roleAssistant", "Asistent") : tr("aiA.roleEvent", "Udalosť");
    const badges = [];
    if (m.hint_level) badges.push(`<span class="ai-badge ai-badge--info">${tr("aiA.hint", "nápoveda")} ${m.hint_level}/3</span>`);
    if (m.role === "assistant") {
      badges.push(`<span class="ai-badge ${m.status === "ok" ? "ai-badge--ok" : m.status === "fallback" ? "ai-badge--warn" : "ai-badge--err"}">${esc(m.status)}</span>`);
      badges.push(`<span>${esc(m.model || "")}${m.think ? ` (think ${esc(m.think)})` : ""} · ${esc(m.prompt_version || "")}</span>`);
      badges.push(`<span>${tr("aiA.firstWord", "1. slovo")} ${ms(m.first_token_ms)} · ${tr("aiA.total", "spolu")} ${ms(m.latency_ms)} · ${m.tokens_in ?? "–"}→${m.tokens_out ?? "–"} tok.</span>`);
      const r = m.context && m.context.retrieval;
      if (r) badges.push(`<span title="${esc((r.extra_queries || []).join(" | "))}">RAG: ${r.vectors ? tr("aiA.vectorsBm25", "vektory + BM25") : "BM25"}${r.error ? " ⚠" : ""}</span>`);
    }
    if (m.role === "event" && m.kind === "insert") {
      badges.push(`<span class="ai-badge ai-badge--ok">${tr("aiA.inserted", "vložené do")} ${esc((m.context || {}).target || "")} (${esc((m.context || {}).how || "")})</span>`);
    }
    const sources = (m.sources || []).length ? `
      <details class="ai-sources"><summary>${tr("aiA.ragSources", "Zdroje RAG")} (${m.sources.length})</summary>
      <table class="ai-table ai-src-table"><thead><tr><th>#</th><th>${tr("aiA.source", "Zdroj")}</th><th>${tr("aiA.location", "Poloha")}</th><th>${tr("aiA.score", "Skóre")}</th><th>${tr("aiA.signals", "Signály")}</th><th>${tr("aiA.snippet", "Úryvok")}</th></tr></thead>
      <tbody>${m.sources.map((s) => `<tr><td>[${s.rank}]</td>
        <td>${s.type === "prednaska" ? tr("mat.lecture", "Prednáška") + (s.lecture_no != null ? " " + s.lecture_no : "") : tr("mat.book", "Kniha")}<br><span class="ai-muted">${esc(s.title)}</span></td>
        <td>${esc(s.location)}</td><td>${s.score ?? "–"}</td><td class="ai-muted">${esc(s.signals || "")}</td>
        <td class="snip">${esc((s.snippet || "").slice(0, 260))}${(s.snippet || "").length > 260 ? "…" : ""}</td></tr>`).join("")}</tbody></table></details>` : "";
    const guard = (m.guard || []).length ? `<div class="ai-guard">⚑ ${tr("aiA.guard", "Strážca")}: ${esc(guardText(m.guard))}</div>` : "";
    const body = m.role === "event" ? `<pre>${esc(m.text)}</pre>` : esc(m.text);
    return `
      <div class="ai-conv__msg ai-conv__msg--${m.role}">
        <div class="ai-conv__meta"><strong>${who}</strong> · ${when(m.created_at)} ${badges.join(" ")}</div>
        <div class="ai-conv__text" ${m.role === "event" ? "" : "data-md"}>${body}</div>
        ${guard}${sources}
      </div>`;
  }

  // ---------- model ----------
  async function loadSettings() {
    const el = $("tab-settings");
    el.innerHTML = `<p class="ai-muted">${tr("aiA.loading", "Načítavam…")}</p>`;
    let d;
    try { d = await api("/settings"); } catch (e) { el.innerHTML = `<p>${esc(e.message)}</p>`; return; }
    renderSettings(d);
  }

  function renderSettings(d) {
    const c = d.config, h = d.health;
    const el = $("tab-settings");
    const yes = (b) => b ? "✓" : "✗";
    el.innerHTML = `
      <div class="ai-admin-card">
        <h3>${tr("aiA.ollama", "Stav Ollamy")}</h3>
        <div class="ai-health">
          ${h.ok ? `<span class="ai-badge ai-badge--ok">${tr("aiA.running", "beží")}</span>` : `<span class="ai-badge ai-badge--err">${tr("aiA.notRunning", "nedostupná")}</span>`}
          <span class="ai-muted">${esc(c.ollama_url)}</span><br>
          ${tr("aiA.chatModel", "Jazykový model")}: <strong>${esc(c.chat_model)}</strong> ${h.ok ? yes(h.chat_model_present) : ""}
          · ${tr("aiA.embedModel", "Embedding model")}: <strong>${esc(c.embed_model)}</strong> ${h.ok ? yes(h.embed_model_present) : ""}
          ${h.error ? `<br><span style="color:var(--danger)">${esc(h.error)}</span>` : ""}
          ${h.ok && !h.chat_model_present ? `<br><span style="color:var(--warning)">${tr("aiA.pullHint", "Model nie je stiahnutý: ollama pull")} ${esc(c.chat_model)}</span>` : ""}
          ${h.ok && h.models.length ? `<br><span class="ai-muted">${tr("aiA.installed", "Stiahnuté")}: ${h.models.map(esc).join(", ")}</span>` : ""}
        </div>
      </div>
      <div class="ai-admin-card">
        <h3>${tr("aiA.modelSettings", "Nastavenie modelu")}</h3>
        <div class="ai-settings">
          <label>${tr("aiA.chatModel", "Jazykový model")}
            <input id="s-model" value="${esc(c.chat_model)}" list="s-models">
            <datalist id="s-models">${(h.models || []).map((m) => `<option value="${esc(m)}">`).join("")}</datalist>
          </label>
          <label>${tr("aiA.think", "Uvažovanie (think)")}
            <select id="s-think">
              ${["false", "true", "low", "medium", "high"].map((v) => `<option value="${v}" ${String(c.think) === v ? "selected" : ""}>${v}</option>`).join("")}
            </select>
          </label>
          <label>${tr("aiA.temperature", "Teplota")}
            <input id="s-temp" type="number" step="0.05" min="0" max="1.5" value="${esc(c.temperature)}">
          </label>
          <label>${tr("aiA.enabled", "Asistent pre študentov")}
            <select id="s-enabled"><option value="true" ${c.enabled ? "selected" : ""}>${tr("aiA.on", "zapnutý")}</option><option value="false" ${!c.enabled ? "selected" : ""}>${tr("aiA.off", "vypnutý")}</option></select>
          </label>
        </div>
        <p class="ai-muted">${tr("aiA.envNote", "Predvolené hodnoty sú v .env")} (AI_CHAT_MODEL=${esc(c.env_model)}, AI_THINK=${esc(c.env_think)}).
          ${tr("aiA.thinkNote", "qwen3.8 s think=true odpovedá presnejšie, ale ~10× pomalšie (podľa prieskumu ~40 s).")}
          ${tr("aiA.limits", "Limit")}: ${esc(c.rate_limit)} ${tr("aiA.msgsPer", "správ /")} ${Math.round(c.rate_window / 60)} min ${tr("aiA.perStudent", "na študenta")}, ${esc(c.max_concurrent)} ${tr("aiA.concurrent", "odpovede naraz na worker")}, RAG k=${esc(c.rag_k)}.</p>
        <div class="ai-filters">
          <button type="button" id="s-save">${tr("aiA.save", "Uložiť")}</button>
          <button type="button" id="s-test" class="btn--secondary">${tr("aiA.test", "Otestovať model")}</button>
          <span id="s-msg" class="ai-muted"></span>
        </div>
      </div>`;
    $("s-save").addEventListener("click", async () => {
      $("s-msg").textContent = "…";
      try {
        const nd = await api("/settings", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat_model: $("s-model").value.trim(), think: $("s-think").value,
                                 temperature: $("s-temp").value, enabled: $("s-enabled").value === "true" }),
        });
        renderSettings(nd);
        $("s-msg").textContent = "✓ " + tr("aiA.saved", "Uložené");
      } catch (e) { $("s-msg").textContent = e.message; }
    });
    $("s-test").addEventListener("click", async () => {
      $("s-msg").textContent = tr("aiA.testing", "Čakám na odpoveď modelu…");
      try {
        const r = await fetch("/api/admin/assistant/test", { method: "POST", credentials: "include" });
        const t = await r.json();
        $("s-msg").textContent = t.ok ? `✓ „${t.text}“ (${ms(t.stats.latency_ms)}, ${t.stats.tok_s ?? "–"} tok/s)` : `✗ ${t.error}`;
      } catch (e) { $("s-msg").textContent = e.message; }
    });
  }

  show(filters.student_id ? "conversations" : "overview");
})();
