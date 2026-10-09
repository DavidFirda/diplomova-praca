// Hlavný test - progres sa ukladá na serveri. Server drží session testu,
// počet zodpovedaných otázok aj otázku, ktorá bola zobrazená, ale ešte nie je
// zodpovedaná (po návrate sa zobrazí tá istá). Klient nič z toho neurčuje.
let codeMirrorEditor = null;

window.onload = async () => {
    // Hlavný test je prístupný len po dokončení predtestu.
    // Overíme to cez server (dashboard endpoint) - neobchádzateľné cez URL.
    try {
        const r = await fetch("/api/auth/dashboard", { credentials: "include" });
        if (r.status === 401) { window.location.href = "/login"; return; }
        const dash = await r.json();
        if (!dash.pretest || !dash.pretest.done) {
            alert("Najprv musíš dokončiť predtest.");
            window.location.href = "/predtest";
            return;
        }
    } catch (e) {
        window.location.href = "/dashboard";
        return;
    }

    // Inicializuj CodeMirror
    const textarea = document.getElementById("student_code");
    codeMirrorEditor = CodeMirror.fromTextArea(textarea, {
        mode: "python",
        theme: "default",
        lineNumbers: true,
        indentUnit: 4,
        tabSize: 4,
        lineWrapping: true
    });

    await fetchNextQuestion();
};

async function fetchNextQuestion() {
    const response = await fetch("/api/main_test/start", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: "{}"
    });

    if (response.status === 401) { window.location.href = "/login"; return; }
    if (response.status === 403) { window.location.href = "/predtest"; return; }
    if (!response.ok) {
        alert("Nepodarilo sa načítať otázku.");
        return;
    }

    const question = await response.json();

    // session testu si pamätá server; v localStorage ju držíme len pre stránku s analýzou
    if (question.test_session) {
        localStorage.setItem("main_test_session", question.test_session);
    }

    if (question.finished) {
        alert("✅ Hlavný test hotový!");
        window.location.href = `/analyza`;
        return;
    }

    displayQuestion(question);
}

function displayQuestion(q) {
    document.getElementById("instruction").innerText = q.instruction;
    document.getElementById("input").innerText = q.input_data;
    document.getElementById("category").innerText = "Kategória: " + q.category;
    document.getElementById("question_id").value = q.id;
    document.getElementById("question-counter").innerText = `${q.answered + 1}/${q.total}`;
    codeMirrorEditor.setValue(q.starter_code || "");

    document.getElementById("submit-answer").style.display = "inline-block";
    document.getElementById("next-question").style.display = "none";
    document.getElementById("result-message").innerText = "";
    document.getElementById("output-box").innerText = "";
    document.getElementById("solution-box").style.display = "none";
}

document.getElementById("submit-answer").addEventListener("click", async () => {
    const code = codeMirrorEditor.getValue();
    const question_id = document.getElementById("question_id").value;
    const resultBox = document.getElementById("output-box");
    const resultMessage = document.getElementById("result-message");

    const response = await fetch("/api/test/answer", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question_id, code, test_type: "main" })
    });

    if (response.status === 401) { window.location.href = "/login"; return; }
    if (response.status === 409) {
        // server je o krok inde (napr. iná karta) - zosúlaď sa s ním
        await fetchNextQuestion();
        return;
    }

    const result = await response.json();
    resultBox.innerText = result.student_output || "";
    resultMessage.innerText = result.message || (result.correct ? "Správne!" : "Nesprávne!");

    // Zafarbi hlášku podľa výsledku (zladené s témou)
    resultMessage.classList.remove("test-result--correct", "test-result--wrong", "test-result--info");
    if (result.correct) {
        resultMessage.classList.add("test-result--correct");
    } else if (result.message && !result.student_output) {
        resultMessage.classList.add("test-result--info");
    } else {
        resultMessage.classList.add("test-result--wrong");
    }

    // "final" = odpoveď je uložená na serveri a otázka je uzavretá
    const isFinal = result.correct || result.final || (!result.message && result.correct === false);

    if (result.show_solution) {
        document.getElementById("solution-box").style.display = "block";
        document.getElementById("solution-code").innerText = result.solution_code || "";
    }

    if (isFinal) {
        document.getElementById("submit-answer").style.display = "none";
        document.getElementById("next-question").style.display = "inline-block";
    }
});

document.getElementById("next-question").addEventListener("click", async () => {
    await fetchNextQuestion();
});
