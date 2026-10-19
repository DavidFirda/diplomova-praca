// Úlohy (samoštúdium) - POMDP priebežne vyberá úlohy z tém, ktoré študent nezvláda.
// Server drží stav úlohy: počet pokusov, kedy sa sprístupní asistent (po 2. nesprávnej
// odpovedi) a kedy sa ukáže riešenie (po 5. nesprávnej). Klient nič z toho neurčuje,
// len zobrazuje to, čo vráti /api/ulohy/*.

let codeMirrorEditor = null;
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

    // asistent: po obnovení stránky sa obnoví jeho história
    $("agent-messages").innerHTML = "";
    (a.agent_history || []).forEach((m) => addAgentMessage(m.role === "agent" ? "agent" : "user", m.text, false));
    renderAgentHints();
    updateAgentAvailability(a.agent_available, !a.agent_opened, !!(draft && draft.panelOpen));
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
    const r = await api("submit", { assignment_id: task.id, code: codeMirrorEditor.getValue() });
    setBusy(false);
    if (!r) return;
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
    if (d.agent_unlocked_now) updateAgentAvailability(true, true);
});

function applyState(d) {
    if (!task || d.attempts_used === undefined) return;
    Object.assign(task, {
        status: d.status, attempts_used: d.attempts_used, wrong_attempts: d.wrong_attempts,
        agent_available: d.agent_available, hints_used: d.hints_used,
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
// Okno asistenta sa otvára z ikony robota a minimalizuje späť do nej (animované cez CSS triedy).
const timeNow = () => new Date().toLocaleTimeString(I18N.lang === "sk" ? "sk-SK" : "en-GB", { hour: "2-digit", minute: "2-digit" });
const ROBOT = '<svg class="ul-icon" aria-hidden="true"><use href="#ul-robot"/></svg>';

function scrollMessages() {
    const box = $("agent-messages");
    box.scrollTop = box.scrollHeight;
}

function addAgentMessage(who, text, withTime = true) {
    const row = document.createElement("div");
    row.className = `ul-row ul-row--${who}`;
    if (who === "agent") {
        const av = document.createElement("div");
        av.className = "ul-avatar";
        av.innerHTML = ROBOT;
        row.appendChild(av);
    }
    const wrap = document.createElement("div");
    wrap.className = "ul-bubble-wrap";
    const bubble = document.createElement("div");
    bubble.className = `ul-msg ul-msg--${who}`;
    bubble.textContent = text;
    wrap.appendChild(bubble);
    if (withTime) {
        const time = document.createElement("span");
        time.className = "ul-time";
        time.textContent = timeNow();
        wrap.appendChild(time);
    }
    row.appendChild(wrap);
    $("agent-messages").appendChild(row);
    scrollMessages();
}

function showTyping() {
    const row = document.createElement("div");
    row.className = "ul-row ul-row--agent";
    row.id = "agent-typing";
    row.innerHTML = `<div class="ul-avatar">${ROBOT}</div>
        <div class="ul-bubble-wrap"><div class="ul-msg ul-msg--agent ul-typing"><i></i><i></i><i></i></div></div>`;
    $("agent-messages").appendChild(row);
    scrollMessages();
}
function hideTyping() {
    const el = $("agent-typing");
    if (el) el.remove();
}

function renderAgentHints() {
    if (!task) return;
    $("agent-hints").innerText = `${t("ul.hints", "Nápovedy")}: ${task.hints_used}/${task.max_hints}`;
    $("agent-hint").disabled = task.hints_used >= task.max_hints;
}

function setFab(visible, pulsing = false) {
    const fab = $("agent-fab");
    fab.classList.toggle("is-visible", visible);
    fab.classList.toggle("is-pulsing", visible && pulsing);
    document.body.classList.toggle("ul-has-fab", visible || $("agent-panel").classList.contains("is-open"));
}

function openAgent() {
    const panel = $("agent-panel");
    panel.classList.add("is-open");
    panel.setAttribute("aria-hidden", "false");
    $("agent-fab").setAttribute("aria-expanded", "true");
    setFab(false);
    document.body.classList.add("ul-has-fab");
    scrollMessages();
    setTimeout(() => $("agent-input").focus({ preventScroll: true }), 300);
}

// minimalizovanie = okno sa zmenší späť do ikony robota (správy ostávajú)
function minimizeAgent() {
    const panel = $("agent-panel");
    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    $("agent-fab").setAttribute("aria-expanded", "false");
    setFab(!!(task && task.agent_available));
}

// Asistent nie je dostupný (úloha je uzavretá / ešte nie je odomknutý): skry okno aj ikonu.
function setAgentAvailable(on) {
    if (task) task.agent_available = on;
    if (!on) {
        $("agent-panel").classList.remove("is-open");
        $("agent-panel").setAttribute("aria-hidden", "true");
        setFab(false);
        document.body.classList.remove("ul-has-fab");
    }
}

// Sprístupní asistenta; keď ho študent ešte neotvoril, vyskočí sám (pozdrav).
async function updateAgentAvailability(available, popUp, reopen = false) {
    if (!task) return;
    if (!available) { setAgentAvailable(false); return; }
    task.agent_available = true;
    if (popUp) {
        setFab(true);
        showTyping();
        const r = await api("agent", { assignment_id: task.id, intent: "open", code: codeMirrorEditor.getValue() });
        hideTyping();
        if (r && r.ok) {
            addAgentMessage("agent", r.data.reply);
            task.agent_opened = true;
        }
        openAgent();
    } else if (reopen) {
        openAgent();
    } else {
        setFab(true, false);
    }
}

async function askAgent(intent, message) {
    if (!task || !task.agent_available) return;
    if (message) addAgentMessage("user", message);
    showTyping();
    const r = await api("agent", {
        assignment_id: task.id, intent, message: message || "", code: codeMirrorEditor.getValue(),
    });
    hideTyping();
    if (!r) return;
    if (!r.ok) { addAgentMessage("agent", r.data.error || t("ul.loadError", "Chyba.")); return; }
    addAgentMessage("agent", r.data.reply);
    applyState(r.data);
}

$("agent-fab").addEventListener("click", openAgent);
$("agent-minimize").addEventListener("click", minimizeAgent);
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && $("agent-panel").classList.contains("is-open")) minimizeAgent();
});
$("agent-explain").addEventListener("click", () => askAgent("explain", ""));
$("agent-hint").addEventListener("click", () => askAgent("hint", ""));
$("agent-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = $("agent-input").value.trim();
    if (!text) return;
    $("agent-input").value = "";
    askAgent(null, text);
});
