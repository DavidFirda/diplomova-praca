let studentId = null;
let categories = null;
let codeMirrorEditor = null;
let currentCount = 0;
let totalQuestions = 30;
let usedQuestionIds = [];

window.onload = async () => {
    studentId = localStorage.getItem("student_id");
    categories = JSON.parse(localStorage.getItem("test_categories")) || ["Data Structures", "Syntax", "Sorting", "Scientific Computing"];
    localStorage.removeItem("main_test_session")

    if (!studentId) {
        alert("Najprv sa prihlás.");
        window.location.href = "/login.html";
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
    if (currentCount >= totalQuestions) {
        alert("✅ Hlavný test hotový!");
        const sessionId = localStorage.getItem("main_test_session");
        window.location.href = `/analyza.html`;
        return;
    }
    const testSession = localStorage.getItem("main_test_session");

    const body = {
        student_id: studentId,
        categories,
        excluded_ids: usedQuestionIds,
        };

    if (testSession) {
        body.test_session = testSession;
    }

    console.log("TEST SESSION FROM STORAGE:", testSession);
    console.log("Sending body:", body);

    const response = await fetch("/api/main_test/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });

    if (!response.ok) {
        alert("Nepodarilo sa načítať otázku.");
        return;
    }

    const question = await response.json();

    if (!localStorage.getItem("main_test_session") && question.test_session) {
        localStorage.setItem("main_test_session", question.test_session);
    }

    if (usedQuestionIds.includes(question.id)) {
        return await fetchNextQuestion();  
    }

    usedQuestionIds.push(question.id);
    displayQuestion(question);
}

function displayQuestion(q) {
    document.getElementById("instruction").innerText = q.instruction;
    document.getElementById("input").innerText = q.input_data;
    document.getElementById("category").innerText = "Kategória: " + q.category;
    document.getElementById("question_id").value = q.id;
    document.getElementById("question-counter").innerText = `${currentCount + 1}/${totalQuestions}`;
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
    const testSession = localStorage.getItem("main_test_session");

    const response = await fetch("/api/test/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            student_id: studentId,
            question_id,
            code,
            test_type: "main",
            test_session: testSession
        })
    });

    const result = await response.json();
    resultBox.innerText = result.student_output || "";
    resultMessage.innerText = result.message || (result.correct ? "✔️ Správne!" : "❌ Nesprávne!");

    const isFinal = result.correct || (!result.message && result.correct === false);

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
    currentCount++;
    await fetchNextQuestion();
});