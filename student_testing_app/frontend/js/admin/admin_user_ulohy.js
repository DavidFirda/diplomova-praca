/* ============================================================
   AdaptPy - admin: ÚLOHY konkrétneho používateľa.
   Pri každej úlohe: stav, na koľký pokus ju študent vyriešil, každý pokus
   (aj nesprávny) s kódom, výstupom a spätnou väzbou, a log interakcií
   (asistent, riešenie, odmena POMDP, zásahy admina).
   Pokusy a výsledok úlohy sa dajú upraviť / zmazať ako pri testoch.
   ============================================================ */
(function () {
  const root = document.getElementById("ul-content");
  if (!root) return;

  function tr(key, fb) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fb;
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, m => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]
    ));
  }
  function when(iso) {
    if (!iso) return "";
    const d = new Date(iso.endsWith("Z") || /[+-]\d\d:\d\d$/.test(iso) ? iso : iso + "Z");
    return isNaN(d) ? iso : d.toLocaleString();
  }

  const uid = new URLSearchParams(location.search).get("uid");
  let data = null;
  const openState = new Set();      // rozbalené detaily prežijú prekreslenie

  async function call(path, method, body) {
    const r = await fetch(`/api/admin/ulohy/${path}`, {
      method, credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (r.status === 401 || r.status === 403) { window.location.href = "/dashboard"; return null; }
    return r;
  }

  function statusBadge(a) {
    if (a.status === "solved") {
      const txt = tr("adminUL.solvedOn", "vyriešená na {n}. pokus").replace("{n}", a.solved_on_attempt);
      return `<span class="ex-badge ex-badge--done">✓ ${esc(txt)}</span>`;
    }
    if (a.status === "failed") return `<span class="ex-badge ex-badge--fail">✕ ${tr("adminUL.failed", "Nevyriešená")}</span>`;
    if (a.status === "void") return `<span class="ex-badge ex-badge--locked">${tr("adminUL.void", "Zrušená")}</span>`;
    return `<span class="ex-badge ex-badge--progress">${tr("adminUL.open", "Rozpracovaná")}</span>`;
  }

  function chip(label, value) {
    return `<span class="inv-chip">${esc(label)}: <b>${esc(value)}</b></span>`;
  }

  function summaryBlock(s) {
    const avg = s.avg_attempts_to_solve == null ? "–" : s.avg_attempts_to_solve;
    return `
      <div class="card ul-admin-summary">
        <div class="inv-stats">
          ${chip(tr("adminUL.sTotal", "Dokončené úlohy"), s.total)}
          ${chip(tr("adminUL.sSolved", "Vyriešené"), s.solved)}
          ${chip(tr("adminUL.sFailed", "Nevyriešené"), s.failed)}
          ${chip(tr("adminUL.sFirst", "Na 1. pokus"), s.solved_first_try)}
          ${chip(tr("adminUL.sAvg", "Priem. pokusov do vyriešenia"), avg)}
          ${chip(tr("adminUL.sAttempts", "Pokusov spolu"), s.total_attempts)}
          ${chip(tr("adminUL.sReward", "Súčet odmien POMDP"), s.total_reward)}
        </div>
        <p class="admin-muted" style="margin:10px 0 0;">${tr("adminUL.editHint", "Úprava správnosti nemení POMDP.")}</p>
      </div>`;
  }

  function attemptBlock(t, a) {
    const fb = t.feedback && t.feedback.message
      ? `<div class="ul-admin-fb"><b>${tr("adminUL.feedback", "Spätná väzba")}:</b> ${esc(t.feedback.message)}</div>` : "";
    const out = (t.student_output || "").trim()
      ? `<div class="ux-cell__answer-label">${tr("adminUL.output", "Výstup")}</div><pre class="ux-code">${esc(t.student_output)}</pre>` : "";
    return `
      <div class="admin-answer ul-attempt ${t.is_correct ? "ul-attempt--ok" : "ul-attempt--bad"}" data-attempt="${t.id}">
        <div class="admin-answer__head">
          <span><strong>${tr("adminUL.attempt", "Pokus")} ${t.attempt_no}/5</strong>
            <span class="admin-muted"> · ${esc(when(t.created_at))}</span></span>
          <label class="admin-check">
            <input type="checkbox" ${t.is_correct ? "checked" : ""} data-correct="${t.id}">
            <span>${tr("adminUL.correct", "Správne")}</span>
          </label>
        </div>
        <textarea class="admin-answer__code" data-code="${t.id}" rows="4">${esc(t.code)}</textarea>
        ${out}${fb}
        <div class="admin-answer__actions" style="margin-top:8px;">
          <button class="btn btn--secondary btn--sm" data-save="${t.id}">${tr("adminUL.save", "Uložiť")}</button>
        </div>
      </div>`;
  }

  function eventSummary(e) {
    const p = e.payload || {};
    switch (e.type) {
      case "agent_message": return `${p.role === "agent" ? "🤖" : "🧑"} ${p.text || ""}`;
      case "attempt_submitted":
        return `#${p.attempt_no}: ${p.is_correct ? "✓" : "✕"} ${p.feedback_kind || ""}`;
      case "submission_rejected": return p.reason || "";
      case "pomdp_update": return `reward ${p.reward} (${p.observation_correct ? "správne" : "nesprávne"}${p.failed_task ? ", 5 chýb" : ""})`;
      case "task_assigned": return `${p.category || ""} (${p.selection || ""})`;
      case "task_finished": return `${p.status}, pokusov ${p.attempts_used}`;
      default: return Object.keys(p).length ? JSON.stringify(p) : "";
    }
  }

  function eventsBlock(a) {
    if (!a.events.length) return "";
    const rows = a.events.map(e => `
      <tr><td class="admin-muted" style="white-space:nowrap">${esc(when(e.created_at))}</td>
          <td><code>${esc(e.type)}</code></td><td>${esc(eventSummary(e))}</td></tr>`).join("");
    const key = `ev-${a.id}`;
    return `
      <details class="ux-ex__answers" data-key="${key}" ${openState.has(key) ? "open" : ""}>
        <summary>${tr("adminUL.events", "Log interakcií")} (${a.events.length})</summary>
        <div class="admin-table-wrap"><table class="admin-table ul-admin-events"><tbody>${rows}</tbody></table></div>
      </details>`;
  }

  function assignmentCard(a, idx) {
    const title = `Q#${a.question_id} · ${esc(a.category)}`;
    const meta = [
      chip(tr("adminUL.attemptsUsed", "pokusov"), `${a.attempts_used}/5`),
      chip(tr("adminUL.hints", "nápovedy"), `${a.hints_used}/3`),
      a.agent_opened ? `<span class="inv-chip">💡 ${tr("adminUL.agentOpened", "asistent otvorený")}</span>` : "",
      a.solution_shown ? `<span class="inv-chip">${tr("adminUL.solutionShown", "riešenie ukázané")}</span>` : "",
      a.reward != null ? chip(tr("adminUL.reward", "odmena POMDP"), a.reward) : "",
    ].join("");
    const attempts = a.attempts.length
      ? a.attempts.map(t => attemptBlock(t, a)).join("")
      : `<p class="admin-muted">${tr("adminUL.noAttempts", "Zatiaľ žiadne pokusy.")}</p>`;
    const closed = a.status === "solved" || a.status === "failed";
    const key = `as-${a.id}`;

    return `
      <div class="ux-ex" data-assignment="${a.id}">
        <div class="ux-ex__top">
          <div class="ux-ex__num">${idx + 1}</div>
          <div class="ux-ex__main">
            <div class="ux-ex__title">${title}</div>
            <div class="inv-stats" style="margin:0;">${meta}</div>
          </div>
          <div class="ux-ex__badge">${statusBadge(a)}</div>
        </div>
        <details class="ux-ex__answers" data-key="${key}" ${openState.has(key) ? "open" : ""}>
          <summary>${tr("adminUL.attempt", "Pokus")} (${a.attempts.length})</summary>
          <details class="ux-cell__prompt" style="margin:6px 0 10px;">
            <summary>${tr("adminUL.instruction", "Zadanie a riešenie")}</summary>
            <pre class="ux-code ux-code--muted">${esc(a.instruction)}\n\nInput: ${esc(a.input_data)}</pre>
            <div class="ux-cell__answer-label">${tr("adminUL.solution", "Správne riešenie")}</div>
            <pre class="ux-code">${esc(a.solution_code)}</pre>
          </details>
          <div class="ux-cells">${attempts}</div>
          <div class="admin-answer__actions" style="margin-top:12px; flex-wrap:wrap;">
            ${closed ? `<label class="admin-check"><input type="checkbox" ${a.is_correct ? "checked" : ""} data-task-correct="${a.id}">
              <span>${tr("adminUL.taskCorrect", "Úloha vyriešená")}</span></label>` : ""}
            <button class="btn btn--danger-outline btn--sm" data-del-task="${a.id}">${tr("adminUL.delTask", "Vymazať úlohu")}</button>
          </div>
        </details>
        ${eventsBlock(a)}
      </div>`;
  }

  function render() {
    if (!data) return;
    const s = data.student || {};
    const name = `${s.name || ""} ${s.surname || ""}`.trim() || s.login || ("#" + s.id);
    const list = data.assignments || [];

    const head = `
      <div class="card ux-student" style="justify-content:space-between; flex-wrap:wrap;">
        <div style="display:flex; align-items:center; gap:14px;">
          <div class="ux-student__avatar">${esc((name[0] || "?").toUpperCase())}</div>
          <div>
            <div class="ux-student__name">${esc(name)}</div>
            <div class="ux-student__sub">${esc(s.login || "")}${s.email ? " · " + esc(s.email) : ""}</div>
          </div>
        </div>
        ${list.length ? `<button class="btn btn--danger-outline btn--sm" id="del-all">${tr("adminUL.delAll", "Vymazať všetky úlohy")}</button>` : ""}
      </div>`;

    const body = list.length
      ? `<div class="ux-list">${list.map(assignmentCard).join("")}</div>`
      : `<div class="ex-empty">${tr("adminUL.empty", "Používateľ zatiaľ nemá žiadne úlohy.")}</div>`;

    root.innerHTML = head + summaryBlock(data.summary) + body;
    if (typeof I18N !== "undefined") I18N.apply();
    attach();
  }

  function attach() {
    root.querySelectorAll("details[data-key]").forEach(d => {
      d.addEventListener("toggle", () => {
        const k = d.getAttribute("data-key");
        if (d.open) openState.add(k); else openState.delete(k);
      });
    });

    // uložiť pokus (kód + správnosť)
    root.querySelectorAll("[data-save]").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-save");
        const code = root.querySelector(`[data-code="${id}"]`).value;
        const correct = root.querySelector(`[data-correct="${id}"]`).checked;
        const r = await call(`attempts/${id}`, "PATCH", { code, is_correct: correct });
        btn.textContent = r && r.ok ? "✓" : "✕";
        setTimeout(() => { btn.textContent = tr("adminUL.save", "Uložiť"); if (r && r.ok) load(); }, 900);
      });
    });

    // výsledok úlohy
    root.querySelectorAll("[data-task-correct]").forEach(cb => {
      cb.addEventListener("change", async () => {
        const r = await call(`assignments/${cb.getAttribute("data-task-correct")}`, "PATCH", { is_correct: cb.checked });
        if (r && r.ok) load();
      });
    });

    // zmazať úlohu / všetky úlohy
    root.querySelectorAll("[data-del-task]").forEach(btn => {
      btn.addEventListener("click", async () => {
        if (!confirm(tr("adminUL.confirmDelTask", "Vymazať túto úlohu a jej pokusy?"))) return;
        const r = await call(`assignments/${btn.getAttribute("data-del-task")}`, "DELETE");
        if (r && r.ok) load();
      });
    });
    const delAll = document.getElementById("del-all");
    if (delAll) delAll.addEventListener("click", async () => {
      if (!confirm(tr("adminUL.confirmDelAll", "Vymazať všetky úlohy používateľa?"))) return;
      const r = await call(`user/${uid}`, "DELETE");
      if (r && r.ok) load();
    });
  }

  async function load() {
    if (!uid) { root.innerHTML = `<div class="ex-empty">${tr("adminUL.noUser", "Chýba používateľ.")}</div>`; return; }
    try {
      const r = await call(`user/${encodeURIComponent(uid)}`, "GET");
      if (!r) return;
      if (!r.ok) { root.innerHTML = `<div class="ex-empty">${tr("adminUL.error", "Načítanie zlyhalo.")}</div>`; return; }
      data = await r.json();
      render();
    } catch (e) {
      root.innerHTML = `<div class="ex-empty">${tr("adminUL.error", "Načítanie zlyhalo.")}</div>`;
    }
  }

  document.addEventListener("langchange", render);
  load();
})();
