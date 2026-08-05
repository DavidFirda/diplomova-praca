document.addEventListener("DOMContentLoaded", () => {
    const studentId = localStorage.getItem("student_id");
  
    if (!studentId) {
      alert("Chýbajú informácie o študentovi.");
      window.location.href = "/";
      return;
    }
  
    fetch("/api/feedback/check", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ student_id: studentId })
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.submitted) {
          alert("Dotazník si už raz vyplnil. Ďakujeme!");
          window.location.href = "/";
        }
      });
  });
  
  document.getElementById("feedback-form").addEventListener("submit", function (e) {
    e.preventDefault();
  
    const formData = new FormData(this);
    const data = Object.fromEntries(formData.entries());
    data.student_id = localStorage.getItem("student_id");
  
    fetch("/api/feedback", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(res => {
      alert(res.message || "Dotazník odoslaný!");
      window.location.href = "/";
    });
  });