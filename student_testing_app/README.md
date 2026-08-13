# AdaptPy — adaptívny testovací systém pre výučbu Pythonu

Diplomová práca (TUKE FEI). Webová aplikácia, ktorá študentom adaptívne
predkladá programátorské úlohy v Pythone podľa ich aktuálnej úrovne. Výber
ďalšej úlohy riadia algoritmy strojového učenia (Q-learning, POMDP), ktoré
vychádzajú z modelu študenta (popísaný v spodnej časti tohto dokumentu).

---

## Čo aplikácia robí

- Študent sa zaregistruje, absolvuje **predtest** (zistí sa jeho úroveň) a potom
  rieši **adaptívny test** — úlohy sa vyberajú podľa jeho výkonu.
- Riešenia (Python kód) sa spúšťajú na serveri a porovnávajú s očakávaným výstupom.
- Po teste vidí študent **štatistiky** a vypĺňa **dotazník** (spätná väzba).
- **Admin** spravuje používateľov, ich testy a otázky dotazníka.

Výber úloh zabezpečujú tri stratégie (`random`, `q_learning`, `pomdp`), ktoré sa
opierajú o model študenta popísaný nižšie.

---

## Rýchly štart (Docker)

Aplikácia beží v Docker kontajneri a pripája sa na Postgres databázu.

```bash
# 1. Priprav .env (v priečinku student_testing_app/)
cp student_testing_app/.env.example student_testing_app/.env
#    -> otvor .env a doplň vlastné hodnoty (DB, secret key, admin účet, SMTP...)

# 2. Spusti
cd student_testing_app
docker compose up --build

# 3. Otvor v prehliadači
#    http://localhost:5000
```

Pri štarte sa automaticky:
- načítajú otázky (`load_questions.py`),
- vytvoria/aktualizujú tabuľky a naplní sa dotazník,
- vytvorí admin účet (podľa `ADMIN_LOGIN` / `ADMIN_PASSWORD` v `.env`).

> **Databáza:** projekt je momentálne nastavený na cloudovú Postgres (Neon) cez
> `DATABASE_URL` v `.env`. Lokálna Postgres služba je v `docker-compose.yml`
> pripravená (zakomentovaná) — návod na prepnutie je priamo v tom súbore.

---

## Konfigurácia (`.env`)

Všetky citlivé údaje sú v `student_testing_app/.env` (necommituje sa do gitu).
Vzor so všetkými premennými je v **`student_testing_app/.env.example`**.
Najdôležitejšie:

| Premenná | Popis |
|---|---|
| `DATABASE_URL` | Pripojenie na Postgres (Neon alebo lokálna DB) |
| `FLASK_SECRET_KEY` | Tajný kľúč pre session (nutný) |
| `ADMIN_LOGIN`, `ADMIN_PASSWORD` | Prihlásenie admin účtu (vytvorí sa pri štarte) |
| `ADMIN_TOKEN` | Token pre servisné admin operácie |
| `APP_ACCESS_CODE` | Prístupový kód k aplikácii |
| `MAIL_*` | SMTP pre reset hesla (ak prázdne, linky sa vypíšu do konzoly) |
| `FLASK_DEBUG` | `true` len pre lokálny vývoj — nikdy nie v produkcii |

---

## Štruktúra projektu

```
diplomova-praca/
├── student_testing_app/       # webová aplikácia (Flask + vanilla JS)
│   ├── backend/               # server (Flask API, modely, algoritmy)
│   │   └── README.md          # dokumentácia backendu
│   ├── frontend/              # klient (HTML/CSS/JS)
│   │   └── README.md          # dokumentácia frontendu
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── .env.example
├── dataset_processing/        # spracovanie a analýza dát (výskumná časť)
├── PoužívateľskáPríručka_prílohaA.pdf
├── SystémováPríručka_prílohaB.pdf
└── README.md                  # tento súbor
```

Podrobná dokumentácia:
- **Backend** → `student_testing_app/backend/README.md`
- **Frontend** → `student_testing_app/frontend/README.md`
- **Používateľská príručka** → `PoužívateľskáPríručka_prílohaA.pdf`
- **Systémová príručka** → `SystémováPríručka_prílohaB.pdf`

---

## Technológie

- **Backend:** Python 3.12, Flask, SQLAlchemy, Postgres
- **Frontend:** HTML, CSS, vanilla JavaScript (bez frameworku)
- **Algoritmy:** Q-learning, POMDP (výber úloh)
- **Nasadenie:** Docker, docker-compose

---

# Výskumná časť — model študenta a algoritmy

Nasledujúca časť popisuje jadro adaptívneho výberu úloh (pôvodná dokumentácia).


postup pri dátach: 
1. rawdata_analysis
2. data_categorization
3. data_analysis
4. generation_incorrect_output

Postupnosť práce:
1. Model študenta
2. Q-learning
3. POMDP
4. POMDP-v2
5. POMDP-v3

# Student Model:

## **Použitá stratégia**
Model využíva **Leitnerov systém**, váženú históriu odpovedí a penalizáciu pri nesprávnych odpovediach na výpočet pravdepodobnosti správnej odpovede.

| **Parameter** | **Popis** |
|--------------|--------------------------------|
| **Leitnerova úroveň** | Stupeň učenia študenta – správne odpovede ju zvyšujú, nesprávne odpovede ju znižujú. |
| **Počet pokusov** | Počet otázok, ktoré študent danej kategórie odpovedal. |
| **FIFO buffer (n posledných odpovedí)** | Ukladá posledné odpovede, pričom novšie odpovede majú väčší vplyv na pravdepodobnosť správnej odpovede. |
| **Váhovanie odpovedí** | Staršie odpovede majú menší vplyv na pravdepodobnosť správnej odpovede. |
| **Decay faktor** | Určuje, ako rýchlo sa staršie odpovede stávajú menej dôležité (hodnota 0.9 znamená, že každá staršia odpoveď má menší vplyv). |
| **Slabé kategórie** | Kategórie, v ktorých má študent nižšiu základnú pravdepodobnosť správnych odpovedí. |

## **Princíp fungovania**
1. **Odpovedanie na otázky:**
   - Študent odpovedá na otázky s pravdepodobnosťou založenou na jeho predchádzajúcich odpovediach.
   - Ak je študent v **slabej kategórii**, jeho základná pravdepodobnosť je nižšia (30 %).
   - Ak je kategória **silná**, základná pravdepodobnosť je vyššia (95 %).

2. **Aktualizácia pamäte:**
   - Po každej odpovedi sa **Leitnerova úroveň** upraví:
     - **Správna odpoveď**: Leitnerova úroveň sa zvýši o +2.
     - **Nesprávna odpoveď**: Leitnerova úroveň sa zníži na polovicu alebo tretinu (ak boli dve po sebe nesprávne odpovede).
   - Posledné odpovede sa ukladajú do **FIFO bufferu**, ktorý váži ich dôležitosť podľa veku.

3. **Výpočet pravdepodobnosti správnej odpovede:**
   - Používa sa kombinácia:
     - **Histórie odpovedí (vážená suma posledných n odpovedí).**
     - **Leitnerovej úrovne (čím vyššia, tým vyššia pravdepodobnosť správnej odpovede).**
     - **Chybovosti v posledných odpovediach (čím viac nesprávnych odpovedí, tým nižšia pravdepodobnosť správnej odpovede).**
   - Maximálna pravdepodobnosť správnej odpovede je **1.0**, minimálna je **0.2**.

# Q-Learning Tutor: 

## **Použitá stratégia**
Model využíva **epsilon-greedy prístup** na výber otázok a **Q-Learning** na aktualizáciu hodnôt jednotlivých kategórií.

| **Parameter** | **Popis** |
|--------------|--------------------------------|
| **Alpha (α)** | Learning rate – určuje, ako rýchlo sa Q-hodnoty prispôsobujú (zvyčajne medzi 0 a 1). |
| **Gamma (γ)** | Discount factor – váha budúcich odmien (čím bližšie k 1, tým viac sa učíme z budúcich odmien). |
| **Epsilon (ε)** | Pravdepodobnosť, s akou tutor náhodne vyberie kategóriu na preskúmanie (exploration vs. exploitation). |
| **Epsilon decay** | Faktor znižovania ε – čím nižší, tým rýchlejšie tutor prestane náhodne skúmať nové kategórie. |
| **Q-Table** | Udržiava Q-hodnoty pre jednotlivé kategórie na základe skúseností tutora. |
| **Weak categories** | Kategórie s úspešnosťou pod 60 %, ktoré tutor uprednostňuje na zlepšenie študenta. |

## **Princíp fungovania**
1. **Výber otázky:** Tutor vyberá kategóriu podľa epsilon-greedy stratégie:
   - S pravdepodobnosťou **ε** vyberie **náhodnú kategóriu** (exploration).
   - Inak vyberie **kategóriu s najvyššou Q-hodnotou** (exploitation).
   - Ak študent odpovie **3-krát po sebe nesprávne v rovnakej kategórii**, tutor prepne na **silnú kategóriu**.

2. **Aktualizácia Q-hodnoty:**
   - Po každej odpovedi sa Q-hodnota aktualizuje podľa vzorca:
     
     \[ Q(s, a) \leftarrow Q(s, a) + \alpha (r + \gamma \max Q(s', a') - Q(s, a)) \]
     
   - Tutor ukladá históriu odpovedí a zaznamenáva vývoj úspešnosti.

3. **Odmeňovanie:**
   - **Správna odpoveď:** Zníženie odmeny (-10 pre silnú kategóriu, -5 pre slabú kategóriu).
   - **Nesprávna odpoveď:** Zvýšenie odmeny (+20 pre slabú kategóriu, +10 pre silnú kategóriu).

4. **Postupné učenie:**
   - Tutor **postupne znižuje epsilon**, čím sa znižuje náhodnosť a viac sa využíva naučená stratégia.
   - Neustále aktualizuje **weak categories** na základe študentskej úspešnosti.

# **Porovnanie Politík v TutorPOMDP**

Tri rôzne politiky použité v modeloch **TutorPOMDP**.

| **Parameter** | **Prvý model (ε-greedy + streak correction)** | **Druhý model (softmax-based)** | **Tretí model (Bayesovský Thompson Sampling)** |
|--------------|--------------------------------|---------------------------------|--------------------------------------|
| **Výber akcie** | ε-greedy, pričom preferuje slabé kategórie | Softmax na základe neistoty a slabých kategórií | Thompson Sampling na základe Beta distribúcie |
| **Slabé kategórie** | Preferuje, ale pri sérii chýb prepne na silnú kategóriu | Extra váha pri výbere na základe neistoty | Automaticky deteguje slabé kategórie a preferuje ich |
| **Náhodnosť** | Riadená **ε-greedy** stratégiou | Ovládaná **softmaxom** s teplotným parameterom | Thompson Sampling prirodzene vyvažuje prieskum a využitie |
| **Dynamické učenie** | Áno, cez prepínanie medzi slabými a silnými kategóriami | Áno, cez zmenu váh a entropiu | Áno, neustále aktualizuje pravdepodobnosti úspešnosti v kategóriách |
| **Reakcia na sériu nesprávnych odpovedí** |  Prepína na silnú kategóriu pri 3 nesprávnych odpovediach | Nezohľadňuje explicitne streaky | Ak sa zistí slabá kategória, automaticky dostane vyššiu prioritu |
| **Matematická sofistikovanosť** | Nižšia (pravidlá + ε-greedy) | Vyššia (softmax, entropia) | Najvyššia (Bayesovská inferencia, Thompson Sampling) |

---

## **Zhrnutie**

- **Prvý model (ε-greedy + streak correction)** je jednoduchý a efektívny, ak chceme rýchlo reagovať na slabé kategórie, no obsahuje manuálne pravidlá.
- **Druhý model (softmax-based)** používa entropiu a neistotu na dynamickejšiu adaptáciu, ale môže sa zameriavať na široké spektrum oblastí bez priameho preferovania slabých kategórií.
- **Tretí model (Bayesovský Thompson Sampling)** automaticky **učí pravdepodobnosti úspešnosti pre každú kategóriu** a zameriava sa na slabé oblasti **bez potreby manuálneho nastavovania**. Je najsofistikovanejší a najlepšie kombinuje **prieskum a využitie**.



