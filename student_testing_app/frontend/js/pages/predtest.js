// Predtest - progres sa ukladá na serveri (po každej odpovedi).
// Otázky aj ich poradie určuje server (/api/pretest/state), takže po návrate
// sa zobrazí tá istá otázka, na ktorej študent skončil; späť sa vrátiť nedá.
let codeMirrorEditor;

window.addEventListener("DOMContentLoaded", () => {
    const textarea = document.getElementById("student_code");
    codeMirrorEditor = CodeMirror.fromTextArea(textarea, {
        mode: "python",
        theme: "default",
        lineNumbers: true,
        indentUnit: 4,
        tabSize: 4,
        lineWrapping: true,
        viewportMargin: 10
    });
});

function goToDashboard() {
    localStorage.setItem("test_categories", JSON.stringify(["Data Structures", "Syntax", "Sorting", "Scientific Computing"]));
    window.location.href = "/dashboard";
}

function resetQuestionUi() {
    document.getElementById("submit-answer").style.display = "inline-block";
    document.getElementById("submit-answer").disabled = false;
    document.getElementById("next-question").style.display = "none";
    document.getElementById("output-box").innerText = "";

    const resultMsg = document.getElementById("result-message");
    resultMsg.innerText = "";
    resultMsg.classList.remove("test-result--correct", "test-result--wrong", "test-result--info");

    document.getElementById("solution-box").style.display = "none";
    document.getElementById("solution-code").innerText = "";
}

// Načíta stav predtestu zo servera a zobrazí aktuálnu (nezodpovedanú) otázku.
async function loadState() {
    const res = await fetch("/api/pretest/state", { credentials: "include" });
    if (res.status === 401) {
        window.location.href = "/login";
        return;
    }
    if (!res.ok) {
        alert("Nepodarilo sa načítať test.");
        return;
    }

    const state = await res.json();
    if (state.done || !state.question) {
        goToDashboard();
        return;
    }

    resetQuestionUi();
    showQuestion(state.question, state.answered + 1, state.total);
}

window.onload = () => {
    loadState();
};

function showQuestion(question, number, total) {
    document.getElementById("instruction").innerText = question.instruction;
    document.getElementById("input").innerText = question.input_data;
    document.getElementById("category").innerHTML = `<strong>Kategória:</strong> ${question.category}`;
    document.getElementById("question_id").value = question.id;
    if (codeMirrorEditor) {
        codeMirrorEditor.setValue(question.starter_code || "");
    }
    document.getElementById("question-counter").innerText = `${number}/${total}`;
}

// Odoslanie odpovede na server
document.getElementById("submit-answer").addEventListener("click", async () => {
    const submitBtn = document.getElementById("submit-answer");
    const nextBtn = document.getElementById("next-question");
    const resultMsg = document.getElementById("result-message");
    const outputBox = document.getElementById("output-box");
    const solutionBox = document.getElementById("solution-box");
    const solutionCode = document.getElementById("solution-code");

    submitBtn.disabled = true;

    const code = codeMirrorEditor.getValue();
    const question_id = document.getElementById("question_id").value;

    const response = await fetch("/api/test/answer", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question_id, code, test_type: "predtest" })
    });

    if (response.status === 401) {
        window.location.href = "/login";
        return;
    }
    if (response.status === 409) {
        // server je o krok inde (napr. iná karta) - zosúlaď sa s ním
        await loadState();
        return;
    }

    const result = await response.json();

    outputBox.innerText = result.student_output || "";
    resultMsg.innerText = result.message || (result.correct ? "Správne!" : "Nesprávne!");

    // Zafarbi hlášku podľa výsledku (zladené s témou)
    resultMsg.classList.remove("test-result--correct", "test-result--wrong", "test-result--info");
    if (result.correct) {
        resultMsg.classList.add("test-result--correct");
    } else if (result.message && !result.student_output) {
        resultMsg.classList.add("test-result--info");
    } else {
        resultMsg.classList.add("test-result--wrong");
    }

    // "final" = odpoveď je uložená na serveri a otázka je uzavretá
    const isFinal = result.correct || result.final || (!result.message && result.correct === false);

    if (result.show_solution && result.solution_code) {
        solutionCode.innerText = result.solution_code;
        solutionBox.style.display = "block";
        submitBtn.style.display = "none";
        nextBtn.style.display = "inline-block";
    } else if (isFinal) {
        submitBtn.style.display = "none";
        nextBtn.style.display = "inline-block";
    } else {
        submitBtn.disabled = false;
    }
});

document.getElementById("next-question").addEventListener("click", async () => {
    await loadState();
});
