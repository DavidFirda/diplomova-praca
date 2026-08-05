document.addEventListener("DOMContentLoaded", () => {
  const backButton = document.querySelector(".btn[href='/']");
  if (backButton) {
    backButton.addEventListener("click", () => {
      localStorage.removeItem("main_test_session");
    });
  }

  const studentId = localStorage.getItem("student_id");
  const session = localStorage.getItem("main_test_session");

  if (!studentId || !session) {
    document.getElementById("analysis-content").innerHTML = `
      <p>❌ Missing test data</p>
      <p>Prosím, absolvuj najprv test.</p>
    `;
    return;
  }

  fetch("/api/test/analysis", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      student_id: studentId,
      test_session: session,
    }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.error) {
        document.getElementById("analysis-content").innerHTML = `<p>❌ ${data.error}</p>`;
        return;
      }

      const { correct_answers, total_questions, student_accuracy, percentile_rank } = data;
      
      document.getElementById("analysis-content").innerHTML = `
        <div class="center-wrapper">
          <div class="result-block">
            <div class="text-info">
              <p>Správne odpovede: <strong>${correct_answers} z ${total_questions}</strong></p>
            </div>
            <div class="chart-wrapper">
              <canvas id="circleChart"></canvas>
            </div>
          </div>
        </div>
      
        <div class="metrics">
          <div class="metric-content">
            <p>Správnosť odpovede: <strong>${student_accuracy}%</strong></p>
            <p>Percentil: <strong>${percentile_rank}%</strong> študentov malo horší výsledok</p>
          </div>
        </div>
      `;

      renderCircleChart(correct_answers, total_questions - correct_answers);
    });
});

function renderCircleChart(correct, incorrect) {
  const canvas = document.getElementById("circleChart");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");

  new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Správne", "Chybné"],
      datasets: [{
        data: [correct, incorrect],
        backgroundColor: ["#4caf50", "#e57373"],
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: "bottom"
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              return `${context.label}: ${context.raw}`;
            }
          }
        }
      }
    }
  });
}