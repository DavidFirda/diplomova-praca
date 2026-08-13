//const token = "AdaptiveLearningBC";

document.addEventListener("DOMContentLoaded", () => {
  loadSummaryCharts();
});

async function loadSummaryCharts() {
    const res = await fetch("/admin/feedback/summary?token=" + token);
    const { summary, total_responses } = await res.json();
  
    const chartContainer = document.getElementById("charts-section");
    chartContainer.innerHTML = "";
  
    Object.entries(summary).forEach(([question, answers]) => {
      const canvasId = `chart-${question}`;
      console.log(`Drawing chart for: ${question}`, answers);
  
      const wrapper = document.createElement("div");
      wrapper.style.marginBottom = "30px";
      wrapper.style.background = "#fafafa";
      wrapper.style.border = "1px solid #e0e0e0";
      wrapper.style.borderRadius = "8px";
      wrapper.style.padding = "15px";
      wrapper.style.boxShadow = "0 2px 6px rgba(0,0,0,0.05)";
  
      const heading = document.createElement("h3");
      heading.textContent = formatQuestionLabel(question);
      heading.style.marginBottom = "10px";
      heading.style.fontSize = "1.1em";
      heading.style.color = "#333";
  
      const canvas = document.createElement("canvas");
      canvas.id = canvasId;
      canvas.classList.add("feedback-chart");
      canvas.style.maxHeight = "200px"; 
      canvas.style.width = "100%";
  
      wrapper.appendChild(heading);
      wrapper.appendChild(canvas);
      chartContainer.appendChild(wrapper);
  
      const ctx = canvas.getContext("2d");
  
      new Chart(ctx, {
        type: "bar",
        data: {
          labels: Object.keys(answers),
          datasets: [{
            label: "Odpovede (%)",
            data: Object.values(answers),
            backgroundColor: "#4caf50",
            borderRadius: 4,
            barThickness: 22
          }]
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (context) => `${context.label}: ${context.raw}%`
              }
            }
          },
          scales: {
            x: {
              ticks: { callback: val => `${val}%` },
              max: 100,
              grid: { display: false }
            },
            y: {
              ticks: {
                font: { size: 13 }
              },
              grid: { display: false }
            }
          }
        }
      });
    });
  
    renderSummaryInsights(summary, total_responses);
  }

function formatQuestionLabel(key) {
  return {
    gender: "Aké je tvoje pohlavie?",
    age: "Aký je tvoj vek?",
    experience: "Akú máš skúsenosť s programovaním?",
    field_of_study: "Aký je tvoj študijný odbor?",
    understand_questions: "Rozumel/a si úlohám?",
    easy_navigation: "Bolo používanie aplikácie pre teba intuitívne?",
    motivation_level: "Ako by si ohodnotil/a svoju motiváciu počas riešenia testu?",
    helpful_feedback: "Pomohla ti spätná väzba k odpovediam?",
    overall_usefulness: "Bol pre teba test užitočný?",
    difficulty_match: "Myslíš si, že úlohy boli primerané tvojej úrovni?",
    improved_skills: "Myslíš si, že si sa zlepšil/a v programovaní?",
    time_spent: "Koľko času si približne venoval/a riešeniu testu?",
    future_interest: "Chcel/a by si v budúcnosti riešiť viac takýchto úloh?",
    ui_satisfaction: "Bola pre teba vizuálna stránka a dizajn aplikácie vyhovujúca?",
    improvement_suggestion: "Máš návrhy na zlepšenie?"
  }[key] || key;
}

function renderSummaryInsights(summary, total) {
    const container = document.getElementById("feedback-summary");
  
    const helper = (key, label, all = false) => {
        const obj = summary[key];
        if (!obj) return "";
        
        if (all) {
          return `<li><strong>${label}:</strong><ul style="margin-top: 4px;">
            ${Object.entries(obj).map(([k, v]) => `<li>${k}: ${v}%</li>`).join("")}
          </ul></li>`;
        } else {
          const maxEntry = Object.entries(obj).sort((a, b) => b[1] - a[1])[0];
          if (maxEntry) {
            return `<li><strong>${label}:</strong> ${maxEntry[0]} (${maxEntry[1]}%)</li>`;
          }
        }
        return "";
      };
    
      let avgAge = "N/A";
      if (summary.age) {
        let totalAgeSum = 0;
        let totalCount = 0;
        for (const [ageStr, percent] of Object.entries(summary.age)) {
          const age = parseInt(ageStr);
          if (!isNaN(age)) {
            totalAgeSum += age * (percent / 100);
            totalCount += 1;
          }
        }
        if (totalCount > 0) {
          avgAge = Math.round(totalAgeSum); 
        }
      }
  
    container.innerHTML = `
      <ul>
        ${helper("gender", "Rozloženie pohlavia", true)}
        <li><strong>Priemerný vek:</strong> ${avgAge}</li>
        ${helper("experience", "Úroveň skúseností")}
        ${helper("understand_questions", "Rozumenie úlohám")}
        ${helper("easy_navigation", "Používanie aplikácie")}
        ${helper("motivation_level", "Úroveň motivácie")}
        ${helper("helpful_feedback", "Spätná väzba k odpovediam bola užitočná")}
        ${helper("overall_usefulness", "Celková užitočnosť aplikácie")}
        ${helper("improved_skills", "Zlepšenie v programovaní")}
        ${helper("time_spent", "Čas venovaný riešeniu testu")}
        ${helper("future_interest", "Záujem o ďalšie využívanie aplikácie")}
      </ul>
      <p><strong>Celkový počet respondentov:</strong> ${total}</p>
    `;
  }