# Backend — AdaptPy

Flask API, ktorý obsluhuje adaptívny testovací systém: autentifikáciu,
spúšťanie a vyhodnocovanie kódu študenta, adaptívny výber úloh (algoritmy),
štatistiky, dotazník a admin operácie.

> Spúšťanie a konfigurácia (Docker, `.env`) sú v hlavnom README v koreni projektu.

---

## Štruktúra

```
backend/
├── app.py                  # továreň aplikácie create_app(): konfigurácia, rozšírenia,
│                           #   blueprinty, routing stránok
├── extensions.py           # Flask-Migrate, Flask-Login (current_user), admin_required
├── bootstrap.py            # `flask bootstrap`: otázky, dotazník, admin účet, cvičenia
├── models.py               # databázové modely (SQLAlchemy)
├── migrations/             # verzionované migrácie DB (Alembic / Flask-Migrate)
│
├── routes/                 # API endpointy (Flask blueprinty)
│   ├── auth_routes.py      # registrácia, login, logout, reset hesla, dashboard
│   ├── api_routes.py       # predtest, hlavný test, odpovede, dotazník
│   ├── admin_routes.py     # servisné admin operácie (cez ADMIN_TOKEN)
│   └── admin_api_routes.py # admin panel API (cez session + rola "admin")
│
├── services/               # pomocné služby
│   ├── test_flow.py        # logika testov: kto je na rade, progres, stavový automat otázky
│   ├── capture_output.py   # spúšťa kód v sandboxe (runner) a porovnáva výstup
│   ├── code_runner.py      # HTTP klient pre izolovaný kontajner `runner`
│   ├── extract_starter_code.py
│   └── mail_utils.py       # odosielanie emailov (reset hesla)
│
└── algorithms/             # adaptívny výber úloh
    ├── random_selector.py  # náhodný výber (baseline)
    ├── q_learning.py       # Q-learning
    ├── q_selector.py       #   + selektor
    ├── pomdp.py            # POMDP
    ├── pomdp_selector.py   #   + selektor
    └── storage.py          # atomický zápis stavu selektorov do JSON
```

---

## Databázové modely (`models.py`)

| Model | Popis |
|---|---|
| `Student` | Používateľ (login, email, heslo, **rola** user/admin) |
| `Question` | Programátorská úloha (zadanie, kategória, očakávaný výstup) |
| `StudentAnswer` | Odpoveď študenta na úlohu |
| `TestSummary` | Súhrn absolvovaného testu |
| `TestProgress` | Rozpracovaný/dokončený hlavný test a otázka, na ktorej študent skončil |
| `AnswerAttempt` | Počet použitých opráv na otázku (perzistentne, nie v pamäti procesu) |
| `StudentFeedback` | Vyplnený dotazník študenta |
| `FeedbackQuestion` | Otázka dotazníka (spravovateľná adminom) |
| `FeedbackResponse` | Odpoveď na otázku dotazníka |
| `AppSetting` | Nastavenia aplikácie (kľúč-hodnota), napr. `questionnaire_published` |
| `FeedbackMessage` | Správa z feedback formulára (dostupný vždy) |

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

## Schéma DB a štart (`entrypoint.sh`)

Schému spravuje **Flask-Migrate (Alembic)**, nie `db.create_all()`. Pri štarte
kontajnera (`entrypoint.sh`) bežia **raz**, ešte pred workermi:

1. `flask db upgrade` — aplikuje migrácie z `migrations/versions/`. Prvá
   (`0001_baseline`) je idempotentná: na prázdnej DB vytvorí tabuľky, na DB
   z predošlých verzií len doplní chýbajúce stĺpce a dáta nechá.
2. `flask bootstrap` — naplní otázky (z `final_dataset.csv`), otázky dotazníka,
   admin účet (`ADMIN_LOGIN` / `ADMIN_PASSWORD`) a cvičenia. Idempotentné.
3. `gunicorn` — workery už nič nemenia v schéme ani nenapĺňajú DB.

Zmena modelu = nová migrácia (v priečinku `backend/`):

```bash
flask --app app db migrate -m "popis zmeny"   # vygeneruje súbor v migrations/versions
flask --app app db upgrade                    # aplikuje ho
```

Vygenerovaný súbor vždy skontroluj (Alembic nepozná premenovania stĺpcov).

---

## Prihlásenie (Flask-Login)

Prihlásený študent je `current_user`; chránené endpointy majú `@login_required`
(401 s JSON chybou) alebo `@admin_required` z `extensions.py` (401/403).
`student_id` sa **nikdy** neberie z tela požiadavky. Session je server-side
v DB (Flask-Session), cookie nesie len podpísané ID.

---

## Predtest a hlavný test (`services/test_flow.py`)

- **Predtest** má pevný zoznam 12 otázok na serveri. Progres sa odvodzuje zo
  `StudentAnswer`: `GET /api/pretest/state` vráti prvú nezodpovedanú otázku, takže
  po návrate pokračuje tam, kde študent skončil. Predtest je hotový až po všetkých
  otázkach (odomkne hlavný test).
- **Hlavný test** (30 otázok) má progres v `test_progress` (session `main-N` +
  rozpracovaná otázka). Stratégia výberu sa určuje podľa ID študenta:
  `id % 3` = 1 Random, 2 Q-learning, 0 POMDP.
- **Odpoveď** (`POST /api/test/answer`): server overí, že ide o otázku, ktorá je
  na rade, spustí kód v sandboxe a výsledok vyhodnotí stavovým automatom
  `QuestionFlow` (knižnica `transitions`): `open → retry → closed` — jedna oprava
  po nesprávnej odpovedi, potom je výsledok konečný.
- **Súbežnosť:** zápisy jedného študenta sú serializované riadkovým zámkom
  (`lock_student`), rôzni študenti sa neblokujú. Počas behu kódu sa DB spojenie
  uvoľňuje do poolu. Stav selektorov (Q-learning, POMDP) je v súboroch pod
  `data/` a zapisuje sa atomicky.

---

## Spúšťanie kódu študenta (`services/capture_output.py`)

Kód študenta aj referenčné riešenie sa spúšťajú v izolovanom kontajneri
`runner` (časový limit, limity CPU/pamäte, bez siete) — **nie** v procese
backendu. Výstup sa porovnáva s očakávaným bez `eval` (`ast.literal_eval`,
čísla s toleranciou 0,01). Ak je `runner` nedostupný, odpoveď sa nezapíše
(HTTP 503) a študent to môže skúsiť znova.

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

Zoznam v `requirements.txt`. Kľúčové: Flask, Flask-SQLAlchemy, Flask-Migrate,
Flask-Login, Flask-Session, Flask-CORS, transitions, python-dotenv, psycopg2
(Postgres), gunicorn.
