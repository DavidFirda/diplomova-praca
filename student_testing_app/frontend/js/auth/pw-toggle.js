/* AdaptPy - zobrazenie/skrytie hesla (oko) + naklonenie postavičiek. */
(function () {
  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".pw-toggle");
    if (!btn) return;
    const input = document.getElementById(btn.getAttribute("data-target"));
    if (!input) return;
    const willShow = input.type === "password";
    input.type = willShow ? "text" : "password";
    const eye = btn.querySelector(".pw-eye");
    const eyeOff = btn.querySelector(".pw-eye-off");
    if (eye) eye.style.display = willShow ? "none" : "block";
    if (eyeOff) eyeOff.style.display = willShow ? "block" : "none";
    btn.setAttribute("aria-label", willShow ? "Skryť heslo" : "Zobraziť heslo");

    // postavičky sa naklonia smerom k formuláru, keď je heslo odkryté
    if (window.adaptpyBuddiesPeek) window.adaptpyBuddiesPeek(willShow);
  });
})();
