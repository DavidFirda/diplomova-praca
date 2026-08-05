let questionQueue = [];
let currentIndex = 0;
let studentId = null;
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

// Načítaj ID študenta z localStorage
window.onload = async () => {
    studentId = localStorage.getItem("student_id");
    if (!studentId) {
        alert("Najprv sa prihlás.");
        window.location.href = "/login.html";
        return;
    }

    const res = await fetch("/admin/students/summary?token="+ token);
    const data = await res.json();
    const student = data.find(s => s.id === parseInt(studentId));

    if (student && student.predtest.total_answers > 0) {
        localStorage.setItem("test_categories", JSON.stringify(["Data Structures", "Syntax", "Sorting", "Scientific Computing"]));
        window.location.href = "/hlavnytest.html";
        return;
    }

    await startTest([1, 4, 11, 7, 47, 50, 2, 5, 20, 2635, 15, 23]);  // pevne definované ID otázok
};

async function startTest(questionIds) {
    const response = await fetch("/api/test/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student_id: studentId, question_ids: questionIds })
    });

    if (response.ok) {
        questionQueue = await response.json();
        currentIndex = 0;
        showQuestion();
    } else {
        alert("Nepodarilo sa načítať test.");
    }
}
// Zobraz aktuálnu otázku
function showQuestion() {
    if (currentIndex >= questionQueue.length) {
        const selectedCategories = ["Data Structures", "Syntax", "Sorting", "Scientific Computing"];
        localStorage.setItem("test_categories", JSON.stringify(selectedCategories));
        window.location.href = "/hlavnytest.html";
        return;
    }

    const question = questionQueue[currentIndex];

    document.getElementById("instruction").innerText = question.instruction;
    document.getElementById("input").innerText = question.input_data;
    document.getElementById("category").innerHTML = `<strong>Kategória:</strong> ${question.category}`;
    document.getElementById("question_id").value = question.id;
    if (codeMirrorEditor) {
        codeMirrorEditor.setValue(question.starter_code || "");
    }
    document.getElementById("result-message").innerText = "";
    document.getElementById("output-box").innerText = "";
    document.getElementById("question-counter").innerText = `${currentIndex + 1}/${questionQueue.length}`;
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
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            student_id: studentId,
            question_id,
            code,
            test_type: "predtest"
        })
    });

    const result = await response.json();

    outputBox.innerText = result.student_output || "";
    resultMsg.innerText = result.message || (result.correct ? "✔️ Správne!" : "❌ Nesprávne!");

    const isFinal = result.correct || (!result.message && result.correct === false);

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

document.getElementById("next-question").addEventListener("click", () => {
    currentIndex++;
    showQuestion();

    document.getElementById("submit-answer").style.display = "inline-block";
    document.getElementById("submit-answer").disabled = false;
    document.getElementById("next-question").style.display = "none";
    document.getElementById("output-box").innerText = "";
    document.getElementById("result-message").innerText = "";

    const solutionBox = document.getElementById("solution-box");
    const solutionCode = document.getElementById("solution-code");
    solutionBox.style.display = "none";
    solutionCode.innerText = "";
});