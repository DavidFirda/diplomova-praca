/* ============================================================
   AdaptPy - admin: TESTY konkrétneho používateľa (predtest + hlavné testy).
   Rovnaké rozhranie ako Úlohy/Cvičenia používateľa: súhrn, potom karta
   pre predtest a pre každý hlavný test. Pri každej odpovedi zadanie,
   správne riešenie, kód študenta, správnosť, red flag (kontrola originality);
   odpoveď sa dá upraviť / vymazať, predtest aj test vymazať celý.
   ============================================================ */
(function () {
  const root = document.getElementById("ut-content");
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
  function category(c) {
    try { if (typeof I18N !== "undefined" && I18N.category) return I18N.category(c); } catch (e) {}
    return c;
  }
  const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);

  const uid = new URLSearchParams(location.search).get("uid");
  let data = null;
  const openState = new Set(["sec-pretest"]);     // rozbalené sekcie prežijú prekreslenie

  async function call(path, method, body) {
    const r = await fetch(`/api/admin/${path}`, {
      method, credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (r.status === 401 || r.status === 403) { window.location.href = "/dashboard"; return null; }
    return r;
  }

  function chip(label, value) {
    return `<span class="inv-chip">${esc(label)}: <b>${esc(value)}</b></span>`;
  }

  function summaryBlock() {
    const pre = data.pretest_summary || {};
    const mains = data.main_tests || [];
    const all = [...(data.pretest || []), ...mains.flatMap(t => t.answers)];
    const correct = all.filter(a => a.is_correct).length;
    const flags = all.filter(a => a.integrity && a.integrity.active).length;
    return `
      <div class="card ul-admin-summary">
        <div class="inv-stats">
          ${chip(tr("adminUT.sPretest", "Predtest"), `${pre.answered || 0}/${pre.total || 0}${pre.done ? " ✓" : ""}`)}
          ${chip(tr("adminUT.sPretestCorrect", "Predtest správne"), `${pre.correct || 0}/${pre.answered || 0}`)}
          ${chip(tr("adminUT.sMain", "Hlavné testy"), mains.length)}
          ${chip(tr("adminUT.sAnswers", "Odpovedí spolu"), all.length)}
          ${chip(tr("adminUT.sAccuracy", "Úspešnosť"), `${pct(correct, all.length)} %`)}
          ${flags ? `<span class="orig-chip">⚑ ${flags} ${esc(tr("orig.activeFlags", "red flag"))}</span>` : ""}
        </div>
      </div>`;
  }

  function answerBlock(a, idx) {
    const cls = a.is_correct ? "ul-attempt--ok" : "ul-attempt--bad";
    return `
      <div class="admin-answer ul-attempt ${cls} ${a.integrity && a.integrity.active ? "orig-has-flag" : ""}" data-answer="${a.id}">
        <div class="admin-answer__head">
          <span><strong>${idx + 1}. Q#${a.question_id}</strong>
            <span class="admin-muted"> · ${esc(category(a.category))}</span></span>
          <label class="admin-check">
            <input type="checkbox" ${a.is_correct ? "checked" : ""} data-correct="${a.id}">
            <span>${tr("adminU.correct", "Správne")}</span>
          </label>
        </div>
        <details class="ux-cell__prompt" style="margin:6px 0 8px;">
          <summary>${tr("adminUL.instruction", "Zadanie a riešenie")}</summary>
          <pre class="ux-code ux-code--muted">${esc(a.instruction)}\n\nInput: ${esc(a.input_data)}</pre>
          <div class="ux-cell__answer-label">${tr("adminUL.solution", "Správne riešenie")}</div>
          <pre class="ux-code">${esc(a.solution_code)}</pre>
        </details>
        ${OrigFlag.html(a.integrity, a.id)}
        <div class="ux-cell__answer-label">${tr("adminUX.studentCode", "Odpoveď študenta")}</div>
        <textarea class="admin-answer__code" data-code="${a.id}" rows="4">${esc(a.answer_code)}</textarea>
        <div class="admin-answer__actions" style="margin-top:8px;">
          <button class="btn btn--secondary btn--sm" data-save="${a.id}">${tr("adminU.saveAnswer", "Uložiť")}</button>
          <button class="btn btn--danger-outline btn--sm" data-del-answer="${a.id}">${tr("adminU.delAnswer", "Vymazať odpoveď")}</button>
        </div>
      </div>`;
  }

  function badge(answered, correct, total, done) {
    if (!answered) return `<span class="ex-badge ex-badge--locked">${tr("adminUX.notStarted", "Nezačaté")}</span>`;
    const txt = `${correct}/${answered} ${tr("adminUT.correctShort", "správne")}`;
    if (done) return `<span class="ex-badge ex-badge--done">✓ ${esc(txt)}</span>`;
    return `<span class="ex-badge ex-badge--progress">${esc(txt)}${total ? ` · ${answered}/${total}` : ""}</span>`;
  }

  // jedna karta = predtest alebo jeden hlavný test
  function sectionCard({ key, num, title, answers, answered, correct, total, done, flags, delAttr, emptyText }) {
    const list = answers.length
      ? answers.map(answerBlock).join("")
      : `<p class="admin-muted">${esc(emptyText)}</p>`;
    const progress = total ? pct(answered, total) : (answered ? 100 : 0);
    return `
      <div class="ux-ex">
        <div class="ux-ex__top">
          <div class="ux-ex__num">${esc(num)}</div>
          <div class="ux-ex__main">
            <div class="ux-ex__title">${esc(title)} ${OrigFlag.chip(flags)}</div>
            <div class="ex-progress">
              <div class="ex-progress__top">
                <span class="ex-progress__pct">${pct(correct, answered)}%</span>
                <span class="ex-progress__label">${tr("adminUT.accuracy", "úspešnosť")} · ${answered}${total ? "/" + total : ""} ${tr("adminUX.answered", "odpovedí")}</span>
              </div>
              <div class="ex-progress__track"><div class="ex-progress__fill" style="width:${progress}%"></div></div>
            </div>
          </div>
          <div class="ux-ex__badge">${badge(answered, correct, total, done)}</div>
        </div>
        <details class="ux-ex__answers" data-key="${key}" ${openState.has(key) ? "open" : ""}>
          <summary>${tr("adminUX.showAnswers", "Zobraziť odpovede")} (${answers.length})</summary>
          <div class="ux-cells">${list}</div>
          ${answers.length ? `<div class="admin-answer__actions" style="margin-top:12px;">
            <button class="btn btn--danger-outline btn--sm" ${delAttr}>${key === "sec-pretest"
              ? tr("adminU.delPretest", "Vymazať celý predtest") : tr("adminU.delTest", "Vymazať test")}</button>
          </div>` : ""}
        </details>
      </div>`;
  }

  function render() {
    if (!data) return;
    const s = data.user || {};
    const name = `${s.name || ""} ${s.surname || ""}`.trim() || s.login || ("#" + s.id);
    const pre = data.pretest_summary || {};

    const head = `
      <div class="card ux-student">
        <div class="ux-student__avatar">${esc((name[0] || "?").toUpperCase())}</div>
        <div>
          <div class="ux-student__name">${esc(name)}</div>
          <div class="ux-student__sub">${esc(s.login || "")}${s.email ? " · " + esc(s.email) : ""}</div>
        </div>
      </div>`;

    const cards = [sectionCard({
      key: "sec-pretest", num: "P", title: tr("adminU.pretestSection", "Predtest"),
      answers: data.pretest || [], answered: pre.answered || 0, correct: pre.correct || 0,
      total: pre.total, done: pre.done, flags: pre.active_flags || 0,
      delAttr: `data-del-pretest="1"`, emptyText: tr("adminU.noPretest", "Žiadny predtest."),
    })];
    (data.main_tests || []).forEach((t, i) => {
      cards.push(sectionCard({
        key: `sec-${t.test_session}`, num: String(i + 1),
        title: `${tr("adminUT.mainTest", "Hlavný test")} ${i + 1}`,
        answers: t.answers, answered: t.answered, correct: t.correct, total: t.total,
        done: t.status === "done", flags: t.active_flags,
        delAttr: `data-del-session="${esc(t.test_session)}"`, emptyText: "",
      }));
    });
    const noMain = (data.main_tests || []).length ? "" :
      `<div class="ex-empty">${tr("adminU.noMain", "Žiadne hlavné testy.")}</div>`;

    root.innerHTML = head + summaryBlock() + `<div class="ux-list">${cards.join("")}</div>` + noMain;
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

    // red flag zrušiť / obnoviť
    OrigFlag.bind(root, async (id, dismissed) => {
      const r = await call(`answers/${id}`, "PATCH", { flag_dismissed: dismissed });
      return !!(r && r.ok);
    }, load);

    // uložiť odpoveď (kód + správnosť)
    root.querySelectorAll("[data-save]").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-save");
        const r = await call(`answers/${id}`, "PATCH", {
          answer_code: root.querySelector(`[data-code="${id}"]`).value,
          is_correct: root.querySelector(`[data-correct="${id}"]`).checked,
        });
        btn.textContent = r && r.ok ? "✓" : "✕";
        setTimeout(() => { btn.textContent = tr("adminU.saveAnswer", "Uložiť"); if (r && r.ok) load(); }, 900);
      });
    });

    root.querySelectorAll("[data-del-answer]").forEach(btn => {
      btn.addEventListener("click", async () => {
        if (!confirm(tr("adminU.confirmDelAnswer", "Vymazať túto odpoveď?"))) return;
        const r = await call(`answers/${btn.getAttribute("data-del-answer")}`, "DELETE");
        if (r && r.ok) load();
      });
    });

    const delPre = root.querySelector("[data-del-pretest]");
    if (delPre) delPre.addEventListener("click", async () => {
      if (!confirm(tr("adminU.confirmDelPretest", "Vymazať celý predtest tohto používateľa?"))) return;
      const r = await call(`users/${encodeURIComponent(uid)}/pretest`, "DELETE");
      if (r && r.ok) load();
    });

    root.querySelectorAll("[data-del-session]").forEach(btn => {
      btn.addEventListener("click", async () => {
        if (!confirm(tr("adminU.confirmDelTest", "Vymazať tento test?"))) return;
        const sess = btn.getAttribute("data-del-session");
        const r = await call(`users/${encodeURIComponent(uid)}/tests/${encodeURIComponent(sess)}`, "DELETE");
        if (r && r.ok) load();
      });
    });
  }

  async function load() {
    if (!uid) { root.innerHTML = `<div class="ex-empty">${tr("adminUL.noUser", "Chýba používateľ.")}</div>`; return; }
    try {
      const r = await call(`users/${encodeURIComponent(uid)}/tests`, "GET");
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
