// Úlohy (samoštúdium) - POMDP priebežne vyberá úlohy z tém, ktoré študent nezvláda.
// Server drží stav úlohy: počet pokusov, nápovedy (max 3, každá ďalšia až po ďalšom
// nesprávnom pokuse) a kedy sa ukáže riešenie (po 5. nesprávnej). Klient nič z toho
// neurčuje, len zobrazuje to, čo vráti /api/ulohy/* a /api/assistant/*.
// AI asistent (voľný chat) je dostupný od začiatku úlohy, nikdy nedá celé riešenie.

let codeMirrorEditor = null;
let originality = null;   // kontrola originality editora (js/core/originality.js)
let task = null;          // aktuálna úloha (payload zo servera)
let busy = false;
const DRAFT_KEY = "ulohy_lang_draft";

const $ = (id) => document.getElementById(id);
const t = (key, fallback) => {
    const v = I18N.t(key);
    return v && v !== key ? v : fallback;
};

// ---------- API ----------
async function api(path, body) {
    const res = await fetch(`/api/ulohy/${path}`, {
        method: body ? "POST" : "GET",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify({ ...body, lang: I18N.lang }) : undefined,
    });
    if (res.status === 401) { window.location.href = "/login"; return null; }
    if (res.status === 403 && path !== "agent") { window.location.href = "/predtest"; return null; }
    let data = {};
    try { data = await res.json(); } catch (e) { /* prázdne telo */ }
    return { status: res.status, ok: res.ok, data };
}

// ---------- štart ----------
window.addEventListener("DOMContentLoaded", async () => {
    codeMirrorEditor = CodeMirror.fromTextArea($("student_code"), {
        mode: "python", theme: "default", lineNumbers: true,
        indentUnit: 4, tabSize: 4, lineWrapping: true, viewportMargin: 10,
    });
    originality = Originality.attach(codeMirrorEditor);
    await loadTask();
});

async function loadTask() {
    setBusy(true);
    const r = await api("next", {});
    setBusy(false);
    if (!r) return;
    if (r.status === 404) { showEmpty(r.data.error || t("ul.noTasks", "Zatiaľ nie sú ďalšie úlohy.")); return; }
    if (!r.ok) { showEmpty(t("ul.loadError", "Úlohu sa nepodarilo načítať.")); return; }
    renderStats(r.data.stats);
    showTask(r.data.assignment);
}

function showEmpty(message) {
    $("empty-message").innerText = message;
    $("empty-message").style.display = "block";
    ["instruction", "input", "category", "output-box", "attempts-bar"].forEach((id) => {
        const el = $(id); if (el) el.style.display = "none";
    });
    document.querySelector(".test-input-row").style.display = "none";
    document.querySelector(".test-card .CodeMirror").style.display = "none";
    $("submit-answer").style.display = "none";
    $("next-task").style.display = "none";
    setAgentAvailable(false);
}

// ---------- zobrazenie úlohy ----------
function renderQuestionText() {
    if (!task) return;
    $("instruction").innerText = I18N.questionText(task.question);
    $("category").innerHTML =
        `<strong>${I18N.t("test.category")}:</strong> ${I18N.category(task.question.category)}`;
}
// Zmena jazyka (SK/EN) obnoví celú stránku, aby sa všetko (aj spätná väzba zo servera)
// zobrazilo vo vybranom jazyku. Rozpísaný kód a stav okna asistenta sa pred tým uložia.
document.addEventListener("langchange", () => {
    try {
        if (task && task.status === "open") {
            sessionStorage.setItem(DRAFT_KEY, JSON.stringify({
                id: task.id, code: codeMirrorEditor.getValue(),
                panelOpen: $("agent-panel").classList.contains("is-open"),
                originality: originality.exportState(),
            }));
        }
    } catch (e) { /* sessionStorage nemusí byť dostupné */ }
    window.location.reload();
});

function takeDraft(assignmentId) {
    try {
        const raw = sessionStorage.getItem(DRAFT_KEY);
        sessionStorage.removeItem(DRAFT_KEY);
        const d = raw ? JSON.parse(raw) : null;
        return d && d.id === assignmentId ? d : null;
    } catch (e) { return null; }
}

function showTask(a) {
    task = a;
    renderQuestionText();
    $("input").innerText = a.question.input_data || "";
    const draft = takeDraft(a.id);
    const startCode = draft ? draft.code : (a.last_code != null ? a.last_code : (a.question.starter_code || ""));
    codeMirrorEditor.setValue(startCode);
    codeMirrorEditor.refresh();
    originality.reset({ clearHistory: true });
    if (draft && draft.originality) originality.importState(draft.originality);

    $("output-box").innerText = a.last_output || "";
    $("result-message").innerText = "";
    $("result-message").className = "test-result";
    if (a.attempts_used > 0 && a.status === "open") {
        setResult(t("ul.wrongRetry", "Nesprávne. Oprav kód a skús to znova."), "wrong");
    }
    $("solution-box").style.display = "none";
    showFeedback(a.last_feedback);

    $("submit-answer").style.display = "inline-block";
    $("submit-answer").disabled = false;
    $("next-task").style.display = "none";
    renderAttempts();

    // asistent: po obnovení stránky sa obnoví jeho história (z DB)
    renderAgentHints();
    loadAgentHistory(a.id, !!(draft && draft.panelOpen));
}

function renderAttempts() {
    if (!task) return;
    const used = task.attempts_used, max = task.max_attempts;
    $("attempts-label").innerText = `${t("ul.attempt", "Pokus")} ${Math.min(used + 1, max)}/${max}`;
    if (task.status !== "open") $("attempts-label").innerText = `${t("ul.attempts", "Pokusov")}: ${used}/${max}`;
    const dots = [];
    for (let i = 1; i <= max; i++) {
        let cls = "ul-dot";
        if (i <= used) {
            const solvedHere = task.status === "solved" && i === task.solved_on_attempt;
            cls += solvedHere ? " ul-dot--ok" : " ul-dot--bad";
        } else if (i === used + 1 && task.status === "open") {
            cls += " ul-dot--now";
        }
        dots.push(`<span class="${cls}"></span>`);
    }
    $("attempts-dots").innerHTML = dots.join("");
}

function renderStats(stats) {
    if (!stats) return;
    $("task-stats").innerText =
        `${t("ul.solved", "Vyriešené")}: ${stats.solved}/${stats.total}`;
}

function showFeedback(fb) {
    const box = $("feedback-box");
    if (!fb || !fb.message) { box.style.display = "none"; box.innerText = ""; return; }
    box.innerText = fb.message;
    box.style.display = "block";
}

function setResult(text, kind) {
    const el = $("result-message");
    el.innerText = text || "";
    el.classList.remove("test-result--correct", "test-result--wrong", "test-result--info");
    if (kind) el.classList.add(`test-result--${kind}`);
}

function setBusy(on) {
    busy = on;
    const btn = $("submit-answer");
    if (btn) btn.disabled = on;
}

// ---------- odoslanie pokusu ----------
$("submit-answer").addEventListener("click", async () => {
    if (!task || busy) return;
    setBusy(true);
    const assignmentId = task.id, code = codeMirrorEditor.getValue();
    // podozrivé písanie -> server chce potvrdenie, Originality ukáže okno a odošle znova
    const r = await Originality.submit(
        originality,
        (integrity) => api("submit", { assignment_id: assignmentId, code, integrity }),
        (res) => res && res.data,
    );
    setBusy(false);
    if (!r || r.cancelled) return;
    const d = r.data;

    if (r.status === 404 || r.status === 400) { setResult(d.error || t("ul.loadError", "Chyba."), "info"); return; }

    // odoslanie sa nezapočítalo (prázdny kód, rovnaký kód, runner nedostupný)
    if (d.counted === false && !d.final) {
        applyState(d);
        setResult(d.message || "", "info");
        return;
    }

    applyState(d);
    $("output-box").innerText = d.student_output || "";

    if (d.already_finished) {   // úloha je už uzavretá (napr. odoslané z druhej karty)
        showFeedback(d.feedback);
        setResult(d.correct ? t("ul.correct", "Správne!") : t("ul.failed", "Nesprávne. Využil si všetkých 5 pokusov."),
                  d.correct ? "correct" : "wrong");
        if (d.solution_code) {
            $("solution-code").innerText = d.solution_code;
            $("solution-box").style.display = "block";
        }
        finishTask();
        return;
    }
    if (d.void) {
        setResult(d.message, "info");
        finishTask();
        return;
    }
    if (d.correct) {
        showFeedback(null);
        const n = d.attempt_no || task.solved_on_attempt;
        setResult(`${t("ul.correct", "Správne!")} ${t("ul.solvedOn", "Vyriešené na")} ${n}. ${t("ul.attemptWord", "pokus")}.`, "correct");
        finishTask();
        return;
    }
    if (d.final) {          // 5. nesprávny pokus: úloha je nesprávna, ukáže sa riešenie
        showFeedback(d.feedback);
        setResult(t("ul.failed", "Nesprávne. Využil si všetkých 5 pokusov."), "wrong");
        if (d.solution_code) {
            $("solution-code").innerText = d.solution_code;
            $("solution-box").style.display = "block";
        }
        finishTask();
        return;
    }
    // nesprávny pokus, ďalší je možný: spätná väzba, kód musí opraviť sám
    showFeedback(d.feedback);
    setResult(t("ul.wrongRetry", "Nesprávne. Oprav kód a skús to znova."), "wrong");
    // odomkla sa ďalšia nápoveda -> ikona asistenta zapulzuje (ak je okno zatvorené)
    if (d.hint_available && !assistant.isOpen()) setFab(true, true);
});

function applyState(d) {
    if (!task || d.attempts_used === undefined) return;
    Object.assign(task, {
        status: d.status, attempts_used: d.attempts_used, wrong_attempts: d.wrong_attempts,
        agent_available: d.agent_available, hints_used: d.hints_used,
        hint_available: d.hint_available, hint_reason: d.hint_reason,
        credit_now: d.credit_now, credit_after_hint: d.credit_after_hint, max_hints: d.max_hints,
    });
    if (d.correct && d.attempt_no) task.solved_on_attempt = d.attempt_no;
    renderAttempts();
    renderAgentHints();
}

function finishTask() {
    $("submit-answer").style.display = "none";
    $("next-task").style.display = "inline-block";
    setAgentAvailable(false);
    refreshStats();
}

async function refreshStats() {
    const r = await api("current");
    if (r && r.ok) renderStats(r.data.stats);
}

$("next-task").addEventListener("click", loadTask);

// ---------- asistent ----------
// Okno a ikonu robota rieši spoločný komponent (js/core/assistant.js), bubliny a streamovanie
// odpovedí js/core/ai_chat.js. Tu je to, čo je špecifické pre úlohy: voľný chat od začiatku,
// postupné nápovedy (server ich odomyká po nesprávnych pokusoch) a vloženie kódu do editora
// len na výslovnú žiadosť a po potvrdení.
let agentBusy = false;
const assistant = AdaptAssistant.create({
    onSubmit: (text) => askAgent(text),
    canShowFab: () => !!(task && task.status === "open"),
});
const openAgent = () => assistant.open();
const setFab = (visible, pulsing = false) => assistant.setFab(visible, pulsing);

const agentChat = AiChat.view($("agent-messages"), {
    insert: {
        fixedTarget: "editor",
        apply(code, _target, how) {
            if (!task || task.status !== "open") return false;
            const cm = codeMirrorEditor;
            const last = cm.lastLine();
            if (how === "replace") {
                cm.replaceRange(code, { line: 0, ch: 0 }, { line: last, ch: cm.getLine(last).length }, "assistant");
            } else {
                const end = { line: last, ch: cm.getLine(last).length };
                cm.replaceRange((cm.getValue().trim() ? "\n" : "") + code, end, end, "assistant");
            }
            cm.focus();
            return true;
        },
    },
});

function pct(x) { return x == null ? "" : `${Math.round(x * 100)} %`; }

function renderAgentHints() {
    if (!task) return;
    const max = task.max_hints || 3;
    const parts = [`${t("ul.hints", "Nápovedy")}: ${task.hints_used}/${max}`];
    if (task.status === "open") {
        const reason = task.hint_reason;
        if (task.hint_available) {
            parts.push(`${t("ul.hintCost", "ďalšia zníži hodnotenie na")} ${pct(task.credit_after_hint)}`);
        } else if (reason === "no_wrong_attempt") {
            parts.push(t("ul.hintAfterWrong", "nápoveda po prvom nesprávnom pokuse"));
        } else if (reason === "need_new_wrong") {
            parts.push(t("ul.hintAfterNextWrong", "ďalšia po ďalšom nesprávnom pokuse"));
        }
        if (task.hints_used > 0) parts.push(`${t("ul.taskScore", "hodnotenie úlohy")} ${pct(task.credit_now)}`);
    }
    $("agent-hints").innerText = parts.join(" · ");
    $("agent-hint").disabled = agentBusy || !task.hint_available;
    $("agent-explain").disabled = agentBusy;
}

// Asistent nie je dostupný (úloha je uzavretá): skry okno aj ikonu.
function setAgentAvailable(on) {
    if (task) task.agent_available = on;
    if (!on) assistant.hide();
}

function agentGreeting() {
    agentChat.plain(t("ul.agentGreeting",
        "Ahoj! Som tvoj AI asistent k tejto úlohe. Pýtaj sa ma kedykoľvek – vysvetlím ti pojmy aj chyby, ale riešenie ti neprezradím. Po nesprávnom pokuse si môžeš vypýtať nápovedu."));
}

async function loadAgentHistory(assignmentId, reopen) {
    agentChat.clear();
    const messages = await AiChat.history({ mode: "task", assignment_id: assignmentId });
    if (!task || task.id !== assignmentId) return;
    if (messages.length) agentChat.restore(messages);
    else agentGreeting();
    if (task.status !== "open") { setAgentAvailable(false); return; }
    if (reopen) openAgent(); else setFab(true, false);
}

function setAgentBusy(on) {
    agentBusy = on;
    const input = $("agent-input");
    if (input) input.disabled = on;
    renderAgentHints();
}

async function askAgent(message, action = "chat", shownText = null) {
    if (!task || task.status !== "open" || agentBusy) return;
    setAgentBusy(true);
    await AiChat.ask(agentChat, {
        mode: "task", action, assignment_id: task.id, message: message || "",
        code: codeMirrorEditor.getValue(),
    }, {
        userText: shownText || message,
        onMeta: (d) => { if (d.task_state) { applyState(d.task_state); } },
        onDone: (d) => { if (d.task_state) applyState(d.task_state); },
        onError: (d) => { if (d.task_state) applyState(d.task_state); },
    });
    setAgentBusy(false);
}

$("agent-explain").addEventListener("click", () =>
    askAgent(t("ul.agentExplainMsg", "Vysvetli mi, čo mám v kóde zle (bez riešenia)."), "chat"));
$("agent-hint").addEventListener("click", () =>
    askAgent("", "hint", t("ul.agentHintMsg", "Daj mi nápovedu.")));
