/* AdaptPy - Štatistiky: úlohy (samoštúdium) + predtest po kategóriách.
   Hlavné testy sa prerábajú, preto tu zatiaľ nie sú. */
document.addEventListener("DOMContentLoaded", async () => {
  const loading = document.getElementById("stats-loading");

  function tr(key, fallback) {
    try { if (typeof I18N !== "undefined") { const v = I18N.t(key); if (v && v !== key) return v; } } catch (e) {}
    return fallback;
  }
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (m) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
  const catName = (c) => (typeof I18N !== "undefined" && I18N.category) ? I18N.category(c) : c;

  function catRow(name, value, percent) {
    return `
      <div class="cat-row">
        <div class="cat-row__head">
          <span class="cat-row__name">${esc(name)}</span>
          <span class="cat-row__val">${value}</span>
        </div>
        <div class="cat-bar"><div class="cat-bar__fill" style="width:${Math.max(0, Math.min(100, percent))}%"></div></div>
      </div>`;
  }

  let stats = null;
  try {
    const r = await fetch("/api/auth/stats", { credentials: "include" });
    if (r.ok) stats = await r.json();
  } catch (e) { /* ticho */ }

  // --- 1) Úlohy ---
  const t = stats && stats.tasks;
  if (t && t.total > 0) {
    document.getElementById("tasks-solved").textContent = `${t.solved}/${t.total}`;
    const kpi = (v, l) => `<div class="stats-kpi"><div class="stats-kpi__v">${v}</div><div class="stats-kpi__l">${esc(l)}</div></div>`;
    document.getElementById("tasks-kpis").innerHTML =
      kpi(t.score_percent != null ? `${t.score_percent} %` : "–", tr("stats.tasksScore", "hodnotenie úloh")) +
      kpi(t.solved_first_try, tr("stats.tasksFirstTry", "na prvý pokus")) +
      kpi(t.hints_used, tr("stats.tasksHints", "použitých nápoved"));
    document.getElementById("tasks-card").style.display = "block";
    renderDonut("tasksChart", [t.solved, t.failed],
      [tr("stats.solved", "Vyriešené"), tr("stats.failed", "Nevyriešené")]);

    if (t.categories && t.categories.length) {
      document.getElementById("tasks-cats").innerHTML = t.categories.map((c) => catRow(
        catName(c.category),
        `${c.solved}/${c.total} · ${tr("stats.score", "hodnotenie")} ${c.score_percent} %`,
        c.score_percent,
      )).join("");
      document.getElementById("tasks-cats-card").style.display = "block";
    }
  }

  // --- 2) Predtest podľa kategórií ---
  if (stats && stats.pretest && stats.pretest.done && stats.pretest.categories.length) {
    document.getElementById("pretest-cats").innerHTML = stats.pretest.categories.map((c) =>
      catRow(catName(c.category), `${c.correct}/${c.total} · ${c.accuracy}%`, c.accuracy)).join("");
    document.getElementById("pretest-cats-card").style.display = "block";
  }

  if (loading) loading.style.display = "none";

  // nič na zobrazenie -> prázdny stav
  const shown = ["tasks-card", "pretest-cats-card"].some((id) => document.getElementById(id).style.display === "block");
  if (!shown) {
    const empty = document.getElementById("stats-empty");
    if (empty) empty.style.display = "block";
  }
});

function renderDonut(canvasId, values, labels) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === "undefined") return;
  const styles = getComputedStyle(document.documentElement);
  const textColor = styles.getPropertyValue("--text").trim() || "#333";
  new Chart(canvas.getContext("2d"), {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: [
          styles.getPropertyValue("--primary").trim() || "#0066cc",
          styles.getPropertyValue("--danger").trim() || "#c4000f",
        ],
        borderWidth: 0,
        borderRadius: 4,
        spacing: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: "68%",
      plugins: {
        legend: { position: "bottom", labels: { color: textColor, usePointStyle: true, pointStyle: "circle", boxWidth: 8, boxHeight: 8, padding: 14, font: { size: 13, family: styles.getPropertyValue("--font").trim() || undefined } } },
      },
    },
  });
}
