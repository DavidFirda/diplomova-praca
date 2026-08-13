# Frontend — AdaptPy

Klientská časť aplikácie: čisté **HTML, CSS a vanilla JavaScript** (bez
frameworku). Súbory servíruje Flask backend; stránky sú namapované na URL
v `backend/app.py` (`PAGE_ROUTES`).

> Detailnú mapu súborov (ktorý súbor na čo slúži, kam ísť pri konkrétnej úprave)
> nájdeš v **[`STRUKTURA.md`](STRUKTURA.md)**.

---

## Štruktúra

```
frontend/
├── pages/        # HTML stránky (login, dashboard, test, admin, ...)
├── css/
│   ├── main.css  # hlavný CSS - iba spája časti cez @import
│   ├── parts/    # dizajn rozdelený na oblasti (01-tokens ... 08-auth)
│   └── legacy.css# starý štýl (len feedback_visualization + algorithm_comparison)
├── js/
│   ├── core/     # spoločné: i18n, navbar, sidebar, session-guard, topbar
│   ├── auth/     # prihlásenie/registrácia: script, buddies, pw-toggle
│   ├── pages/    # logika stránok: dashboard, profile, analyza, feedback, ...
│   └── admin/    # admin panel: admin_users, admin_feedback
├── assets/       # favicon, logo (SVG)
└── STRUKTURA.md  # podrobná mapa súborov
```

---

## Ako to funguje

- **Bez build kroku** — súbory sa servírujú priamo, netreba kompilovať ani
  inštalovať balíčky. Stačí upraviť súbor a obnoviť stránku (`Ctrl+Shift+R`).
- **CSS** je rozdelený do `css/parts/` a spojený cez `@import` v `main.css`.
  HTML linkujú iba `main.css`. Pri úprave otvor konkrétnu časť podľa oblasti
  (napr. postavičky = `css/parts/08-auth.css`).
- **JS** je roztriedený do priečinkov podľa oblasti (`core`, `auth`, `pages`,
  `admin`). Každá stránka linkuje len tie skripty, ktoré potrebuje.

---

## Viacjazyčnosť (SK / EN)

Preklady sú v **`js/core/i18n.js`** — dva bloky kľúčov (SK a EN). V HTML sa
používa atribút `data-i18n="kluc"`; text sa nastaví podľa zvoleného jazyka.
Voľba jazyka sa ukladá do `localStorage`.

> Pri pridávaní nového textu doplň kľúč do **oboch** jazykov. Tlačidlá
> generované cez JavaScript musia mať `data-i18n`, inak sa pri prepnutí jazyka
> nepreložia.

---

## Témy (svetlá / tmavá)

Farby sú CSS premenné v `css/parts/01-tokens.css` (blok `:root` pre svetlú,
`[data-theme="dark"]` pre tmavú). Prvky používajú premenné (napr.
`var(--text)`, `var(--surface)`), takže sa prispôsobia téme automaticky. Voľba
témy sa ukladá do `localStorage`.

---

## Cache

Cache-busting cez `?v=...` sa **nepoužíva** — backend posiela hlavičku
`Cache-Control: no-cache` na CSS a JS, takže prehliadač vždy načíta čerstvú
verziu. Po zmene stačí `Ctrl+Shift+R`.

---

## Časté úpravy — kam ísť

| Chcem zmeniť… | Súbor |
|---|---|
| Postavičky na login/register | `js/auth/buddies.js` + `css/parts/08-auth.css` |
| Farby, tlačidlá, fonty | `css/parts/01-tokens.css` |
| Rozloženie prihlásenia | `css/parts/08-auth.css` |
| Sidebar / navbar | `css/parts/02-app-shell.css` + `js/core/` |
| Admin panel vzhľad | `css/parts/07-admin.css` |
| Preklady (SK/EN) | `js/core/i18n.js` |

Úplná mapa je v **[`STRUKTURA.md`](STRUKTURA.md)**.
