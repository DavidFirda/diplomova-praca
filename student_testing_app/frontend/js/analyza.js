/* AdaptPy - Štatistiky: výsledky posledného testu + predtest po kategóriách */
document.addEventListener("DOMContentLoaded", async () => {
  const studentId = localStorage.getItem("student_id");
  const session = localStorage.getItem("main_test_session");
  const loading = document.getElementById("stats-loading");

  function tr(key, fallback) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fallback;
  }

  // --- 1) Výsledky posledného testu (ak existuje session) ---
  if (studentId && session) {
    try {
      const res = await fetch("/api/test/analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student_id: studentId, test_session: session }),
      });
      const data = await res.json();
      if (!data.error) {
        const { correct_answers, total_questions, student_accuracy, percentile_rank } = data;
        document.getElementById("test-correct").textContent = `${correct_answers}/${total_questions}`;
        document.getElementById("test-metrics").innerHTML =
          `${tr("stats.accuracy", "Správnosť")}: <strong>${student_accuracy}%</strong> · ` +
          `${tr("stats.percentile", "Percentil")}: <strong>${percentile_rank}%</strong>`;
        document.getElementById("test-result-card").style.display = "block";
        renderDonut(correct_answers, total_questions - correct_answers);
      }
    } catch (e) { /* ticho - test nemusel byť spravený */ }
  }

  // --- 2) Predtest podľa kategórií (vždy, cez server session) ---
  try {
    const r = await fetch("/api/auth/stats", { credentials: "include" });
    if (r.ok) {
      const stats = await r.json();
      if (stats.pretest && stats.pretest.done && stats.pretest.categories.length) {
        const wrap = document.getElementById("pretest-cats");
        wrap.innerHTML = stats.pretest.categories.map(c => `
          <div class="cat-row">
            <div class="cat-row__head">
              <span class="cat-row__name">${c.category}</span>
              <span class="cat-row__val">${c.correct}/${c.total} · ${c.accuracy}%</span>
            </div>
            <div class="cat-bar"><div class="cat-bar__fill" style="width:${c.accuracy}%"></div></div>
          </div>
        `).join("");
        document.getElementById("pretest-cats-card").style.display = "block";
      }
    }
  } catch (e) { /* ticho */ }

  if (loading) loading.style.display = "none";

  // Ak sa nezobrazil ani test ani predtest → prázdny stav
  const hasTestCard = document.getElementById("test-result-card").style.display === "block";
  const hasPretestCard = document.getElementById("pretest-cats-card").style.display === "block";
  if (!hasTestCard && !hasPretestCard) {
    const empty = document.getElementById("stats-empty");
    if (empty) empty.style.display = "block";
  }
});

function renderDonut(correct, incorrect) {
  const canvas = document.getElementById("circleChart");
  if (!canvas || typeof Chart === "undefined") return;
  const styles = getComputedStyle(document.documentElement);
  const textColor = styles.getPropertyValue("--text").trim() || "#333";
  new Chart(canvas.getContext("2d"), {
    type: "doughnut",
    data: {
      labels: [tr2("Správne"), tr2("Chybné")],
      datasets: [{
        data: [correct, incorrect],
        backgroundColor: ["#6b8afd", "#f87171"],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: "68%",
      plugins: {
        legend: { position: "bottom", labels: { color: textColor, font: { size: 12 } } },
      },
    },
  });
}
function tr2(s) { return s; }
