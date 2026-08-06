/* ============================================================
   AdaptPy - session guard
   Vynúti odhlásenie po zatvorení karty prehliadača.

   Princíp: pri prihlásení sa nastaví značka do sessionStorage
   (platí LEN pre danú kartu, zmaže sa pri jej zatvorení).
   Pri načítaní chránenej stránky:
     - ak je serverová session aktívna (/api/auth/me = 200),
       ale sessionStorage značka chýba => karta bola zatvorená
       a otvorená nanovo => odhlásime a presmerujeme na login.
   Navigácia medzi stránkami v tej istej karte značku zachová,
   takže tam k odhláseniu nedôjde.
   ============================================================ */
(function () {
  const KEY = "adaptpy_tab_session";

  // Zavolá sa po úspešnom prihlásení (z login logiky).
  window.adaptpyMarkTabSession = function () {
    try { sessionStorage.setItem(KEY, "1"); } catch (e) {}
  };

  // Guard pre chránené stránky. Vráti Promise<boolean> = či môže pokračovať.
  window.adaptpySessionGuard = async function () {
    let loggedIn = false;
    try {
      const r = await fetch("/api/auth/me", { credentials: "include" });
      loggedIn = r.ok;
    } catch (e) { loggedIn = false; }

    const hasTabMark = (() => { try { return sessionStorage.getItem(KEY) === "1"; } catch (e) { return false; } })();

    if (!loggedIn) {
      // Server session neexistuje - na chránenej stránke presmeruj na login.
      return false;
    }

    if (loggedIn && !hasTabMark) {
      // Server session žije, ale táto karta bola otvorená nanovo
      // (napr. po zatvorení karty) => odhlás a nech sa prihlási znova.
      try { await fetch("/api/auth/logout", { method: "POST", credentials: "include" }); } catch (e) {}
      try { localStorage.removeItem("student_id"); } catch (e) {}
      window.location.href = "/login";
      return false;
    }

    return true;
  };
})();
