# Backend — AdaptPy

Flask API, ktorý obsluhuje adaptívny testovací systém: autentifikáciu,
spúšťanie a vyhodnocovanie kódu študenta, adaptívny výber úloh (algoritmy),
štatistiky, dotazník a admin operácie.

> Spúšťanie a konfigurácia (Docker, `.env`) sú v hlavnom README v koreni projektu.

---

## Štruktúra

```
backend/
├── app.py                  # vstupný bod: konfigurácia, routing stránok,
│                           #   registrácia blueprintov, migrácie + seed pri štarte
├── config.py               # konfiguračné konštanty
├── models.py               # databázové modely (SQLAlchemy)
│
├── routes/                 # API endpointy (Flask blueprinty)
│   ├── auth_routes.py      # registrácia, login, logout, reset hesla, dashboard
│   ├── api_routes.py       # test, predtest, odpovede, dotazník (verejné API)
│   ├── admin_routes.py     # servisné admin operácie (cez ADMIN_TOKEN)
│   └── admin_api_routes.py # admin panel API (cez session + rola "admin")
│
├── services/               # pomocné služby
│   ├── capture_output.py   # spúšťa kód študenta (exec) a porovnáva výstup
│   ├── extract_starter_code.py
│   └── mail_utils.py       # odosielanie emailov (reset hesla)
│
└── algorithms/             # adaptívny výber úloh
    ├── random_selector.py  # náhodný výber (baseline)
    ├── q_learning.py       # Q-learning
    ├── q_selector.py       #   + selektor
    ├── pomdp.py            # POMDP
    └── pomdp_selector.py   #   + selektor
```

---

## Databázové modely (`models.py`)

| Model | Popis |
|---|---|
| `Student` | Používateľ (login, email, heslo, **rola** user/admin) |
| `Question` | Programátorská úloha (zadanie, kategória, očakávaný výstup) |
| `StudentAnswer` | Odpoveď študenta na úlohu |
| `TestSummary` | Súhrn absolvovaného testu |
| `StudentFeedback` | Vyplnený dotazník študenta |
| `FeedbackQuestion` | Otázka dotazníka (spravovateľná adminom) |
| `FeedbackResponse` | Odpoveď na otázku dotazníka |

---

## API blueprinty

| Blueprint | Prefix | Autentifikácia | Obsah |
|---|---|---|---|
| `auth_bp` | `/api/auth` | session | registrácia, login, logout, reset hesla, dashboard |
| `api_bp` | `/api` | session / prístupový kód | predtest, test, odpovede, dotazník |
| `admin_bp` | `/api/admin` (servis) | `ADMIN_TOKEN` | servisné operácie |
| `admin_api_bp`| `/api/admin` | session + rola `admin` | správa používateľov a otázok dotazníka |

Zoznam namapovaných stránok (URL → HTML) je v `app.py` v `PAGE_ROUTES`.

---

## Čo sa deje pri štarte (`app.py`)

1. Načíta `.env` (`load_dotenv`).
2. Vytvorí/aktualizuje databázové tabuľky (jednoduché migrácie — napr. pridanie
   stĺpca `role`, ak chýba).
3. Naplní tabuľku otázok dotazníka, ak je prázdna.
4. Vytvorí **admin účet** podľa `ADMIN_LOGIN` / `ADMIN_PASSWORD` z `.env`
   (ak niektorá premenná chýba, admin sa nevytvorí).

---

## Spúšťanie kódu študenta (`services/capture_output.py`)

Kód študenta sa spúšťa cez `exec()` a jeho výstup sa porovnáva s očakávaným.

> ⚠️ **Bezpečnostná poznámka.** Aktuálne sa kód spúšťa bez izolácie a časového
> limitu. V nasadení mimo dôveryhodného prostredia je vhodné doplniť:
> - **timeout** (napr. samostatný proces s časovým limitom), aby nekonečný
>   cyklus nezablokoval server,
> - **obmedzené `__builtins__`** (whitelist bezpečných funkcií, bez `open`,
>   `__import__`, `eval`, `exec`),
> - prípadne spúšťanie v izolovanom prostredí (sandbox / samostatný kontajner).
>
> Pre kontrolované testovanie v rámci diplomovej práce je to vedomý kompromis.

---

## Rate limiting (`auth_routes.py`)

Login a reset hesla majú jednoduchý **in-memory** rate limiter (obmedzenie
počtu pokusov za časové okno).

Implementácia je v **`services/rate_limiter.py`** a používa **Redis** (zdieľané
počítadlo cez sliding-window sorted set), takže limit platí **naprieč všetkými
gunicorn workermi**. Redis službu poskytuje `docker-compose.yml` a prepája sa
cez premennú `REDIS_URL`.

> Ak `REDIS_URL` nie je nastavený alebo je Redis nedostupný, limiter automaticky
> prepne na **in-memory** režim (fallback) — aplikácia funguje aj bez Redisu
> (napr. pri lokálnom vývoji), ale limit vtedy platí len v rámci jedného procesu.

---

## Závislosti

Zoznam v `requirements.txt`. Kľúčové: Flask, Flask-SQLAlchemy, Flask-CORS,
python-dotenv, psycopg2 (Postgres), Flask-Mail.

---

## Poznámka k spusteniu

V `Dockerfile` sa aplikácia spúšťa cez `python backend/app.py`. Pre produkčné
nasadenie s viacerými workermi je pripravený (zakomentovaný) príkaz s
**gunicorn** — odporúčaný pre reálnu prevádzku.
