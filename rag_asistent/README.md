# rag_asistent – lokálne jazykové modely a RAG pre AI asistenta

Experimentálna časť diplomovej práce. Priečinok obsahuje dve veci:

1. **RAG (vyhľadávanie v materiáloch predmetu):** prednášky a knihy sa rozsekajú na kúsky,
   prevedú na vektory a asistent pri otázke študenta najprv nájde súvisiace slajdy alebo strany
   kníh a odpovie podľa nich so zdrojmi.
2. **Vyhodnotenie lokálnych modelov na skutočných domácich úlohách:** model dostane odovzdané
   riešenie študenta a má povedať, či je správne, alebo čo je zle. Jeho odpoveď sa porovná
   s hodnotením vyučujúceho (body a komentár).

Všetko beží lokálne cez [Ollama](https://ollama.com), žiadne cloudové modely. Priečinok
nezasahuje do `student_testing_app`, iba z neho číta `final_dataset.csv` (len `smoke_test.py`).

---

## Obsah

1. [Štruktúra priečinka](#1-štruktúra-priečinka)
2. [Inštalácia](#2-inštalácia-windows-powershell)
3. [Dáta a čo nesmie na git](#3-dáta-a-čo-nesmie-na-git)
4. [RAG: od materiálov po odpoveď](#4-rag-od-materiálov-po-odpoveď)
5. [Glosár a anglické otázky](#5-glosár-a-anglické-otázky)
6. [Vyhodnotenie vyhľadávania](#6-vyhodnotenie-vyhľadávania)
7. [Dataset domácich úloh](#7-dataset-domácich-úloh)
8. [Zadania úloh](#8-zadania-úloh-homeworkxxmd)
9. [Vyhodnotenie modelov na domácich úlohách](#9-vyhodnotenie-modelov-na-domácich-úlohách)
10. [Porovnanie viacerých behov a grafy](#10-porovnanie-viacerých-behov-a-grafy)
11. [Výsledky](#11-výsledky)
12. [Otázky študenta k jeho kódu](#12-otázky-študenta-k-jeho-kódu-qa_evalpy)
13. [Generovanie úloh na precvičovanie](#13-generovanie-úloh-na-precvičovanie-gen_evalpy)
14. [Prvý test na umelom datasete](#14-prvý-test-na-umelom-datasete-smoke_testpy)
15. [Obmedzenia](#15-obmedzenia)

---

## 1. Štruktúra priečinka

```
rag_asistent/
├── data/                    # NEJDE NA GIT
│   ├── prednasky/           # Lecture-XX.pptx + priečinok "lecture codes" (.py, .ipynb)
│   ├── knihy/               # PDF knihy
│   ├── domace_ulohy/        # <rok>/<študent>/hXX.py, len na vyhodnocovanie
│   ├── zadania/             # <rok>/homeworkXX.md, vytvorí ziskaj_zadania.py
│   └── eval/
│       ├── domace_ulohy.csv # vytvorí hw_dataset.py
│       ├── vysledky/        # výsledky hw_eval.py (obsahujú kód študentov)
│       ├── rag/             # výsledky rag_eval.py
│       ├── qa/              # výsledky qa_eval.py
│       ├── gen/             # výsledky gen_eval.py (aj úlohy vo formáte datasetu)
│       └── grafy/           # tabuľky a grafy z hw_grafy.py
├── index/                   # NEJDE NA GIT, vytvorí ingest.py a build_index.py
│   ├── chunks.jsonl         # kúsky textu s metadátami
│   └── bge-m3/              # vektory pre daný embedding model
├── results/                 # výsledky smoke_test.py
├── prompts/
│   ├── rules_krysanova.md   # pravidlá asistenta z práce Krysanovej
│   ├── rules_verdikt.md     # nový prompt s verdiktom v JSON
│   ├── glosar.md            # anglické pojmy -> pojmy zo slovenských prednášok
│   └── otazky_vyhladavanie.csv  # testovacie otázky na vyhľadávanie
├── config.py                # priečinky, váhy zdrojov, embedding model, roky úloh
├── ingest.py                # RAG krok 1: materiály -> kúsky
├── build_index.py           # RAG krok 2: kúsky -> vektory
├── retrieval.py             # vyhľadávanie: vektory + BM25 + RRF + váhy
├── ask.py                   # RAG krok 3: otázka -> nájdené kúsky (-> odpoveď)
├── eval_retrieval.py        # hit@k a MRR vyhľadávania
├── rag_eval.py              # odpovede viacerých modelov na otázky + tabuľka na hodnotenie
├── hw_dataset.py            # domáce úlohy 2024, 2025 -> data/eval/domace_ulohy.csv
├── ziskaj_zadania.py        # stiahne homeworkXX.md za 2024 a 2025
├── hw_eval.py               # porovnanie odpovedí modelu s hodnotením vyučujúceho
├── hw_grafy.py              # súhrn behov, párové testy, grafy
├── spusti_porovnanie.ps1    # všetky nastavenia x seedy pre zvolené modely
├── spusti_3_modely.ps1      # qa_eval a gen_eval na 3 nastaveniach naraz
├── sandbox.py               # spustenie kódu v samostatnom procese s časovým limitom
├── chyby.py                 # typy chýb študenta: vloženie chyby do kódu, určenie typu chyby
├── spolocne.py              # spoločné funkcie pre qa_eval.py a gen_eval.py
├── qa_eval.py               # odpovede na otázky študenta k jeho kódu
├── gen_eval.py              # generovanie úloh (podľa kategórie, aj personalizovane)
└── smoke_test.py            # prvý test modelov na final_dataset.csv
```

---

## 2. Inštalácia (Windows, PowerShell)

```powershell
cd rag_asistent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

ollama pull bge-m3          # embedding model pre RAG
ollama pull gpt-oss:20b     # jazykový model
ollama pull qwen3.8:27b     # voliteľne, druhý porovnávaný model
```

Ak PowerShell nedovolí spustiť `.ps1` skript, spusti ho takto:

```powershell
powershell -ExecutionPolicy Bypass -File .\spusti_porovnanie.ps1
```

Testované na PC s grafickou kartou 16 GB VRAM a 64 GB RAM. gpt-oss:20b (14 GB) sa zmestí
celý do VRAM, qwen3.8:27b (18 GB) len asi zo 73 %, zvyšok beží z RAM, preto je pomalší.

---

## 3. Dáta a čo nesmie na git

Repozitár je verejný. `data/` a `index/` sú v `.gitignore`, lebo obsahujú:

- **domáce úlohy študentov:** osobné údaje (niektoré súbory majú v názve meno),
- **knihy:** autorské práva,
- **výsledky vyhodnotenia** (`data/eval/vysledky/`): obsahujú kód študentov.

Domáce úlohy sa **nikdy nedávajú do RAG indexu**: obsahujú hotové riešenia, ktoré by asistent
mohol prezradiť ďalším študentom. Používajú sa len na vyhodnotenie modelov.

Na git môžu ísť len súhrnné tabuľky a grafy z `data/eval/grafy/` (bez kódu študentov), ak ich
skopíruješ inam.

---

## 4. RAG: od materiálov po odpoveď

```powershell
python ingest.py                 # 1. rozseká materiály (knihy trvajú ~1 min)
python build_index.py            # 2. vektory cez bge-m3 (~1 min); ďalší beh prepočíta len zmeny
python ask.py "čo je list comprehension"
```

### 4.1 `ingest.py` – materiály na kúsky

Prejde priečinky zo `SOURCES` v `config.py` (`data/prednasky`, `data/knihy`) a podľa prípony:

| Formát | Ako sa delí |
| --- | --- |
| `.pptx` | jeden kúsok = jeden slajd (nadpis, text, tabuľky, poznámky prednášajúceho); titulné a prázdne slajdy sa vynechajú |
| `.ipynb` | bunky notebooku (markdown aj kód) spojené do kúskov |
| `.py` | kód rozdelený podľa prázdnych riadkov |
| `.md`, `.txt` | text rozdelený podľa nadpisov |
| `.pdf` | strany spojené do kúskov s prekryvom; obsah a register sa vynechajú |

- Veľkosť kúska je približne `CHUNK_CHARS = 1500` znakov, prekryv pri knihách `OVERLAP_CHARS = 200`
  (rezané na hranici slova).
- Kúsky kratšie ako 60 znakov a duplikáty (napr. `.ipynb_checkpoints`) sa vynechajú.
- Každý kúsok má metadáta: `typ` (prednaska/kniha), `subor`, `nazov`, `poloha` (slajd/strana),
  `prednaska` (číslo z názvu `Lecture-04`), `jazyk`, `text`.
- Výstup: `index/chunks.jsonl`. Na mojom PC 3 964 kúskov (3 550 z kníh, 342 slajdov,
  47 kúskov kódu, 25 z notebookov).

**Pridanie materiálov:** skopíruj súbor do správneho priečinka v `data/` a spusti znova
`ingest.py` a `build_index.py`.

**Nový typ zdroja:** pridaj riadok do `SOURCES` v `config.py` a rovnomenný priečinok v `data/`.

### 4.2 `build_index.py` – vektory

- Každý kúsok sa pošle do Ollamy (`/api/embed`, model `bge-m3`) ako
  `"<názov> (<poloha>)\n<text>"`, takže vektor vie, odkiaľ kúsok je.
- Vektory sa uložia normalizované do `index/<model>/vectors.npy` a `ids.json`.
- Pri ďalšom behu sa prepočítajú len nové alebo zmenené kúsky.
- Iný embedding model: `python build_index.py --model qwen3-embedding:0.6b`; každý model
  má vlastný priečinok v `index/`.

### 4.3 `retrieval.py` – vyhľadávanie

Kombinuje dva spôsoby hľadania:

- **vektory (význam):** kosínusová podobnosť otázky a kúskov; nájde súvisiaci text aj pri
  iných slovách a naprieč jazykmi (slovenská otázka -> anglická kniha),
- **BM25 (presné slová):** vlastná implementácia (k1 = 1,5, b = 0,75), bez diakritiky, slová
  orezané na 6 znakov ako jednoduché stemovanie (funkcia/funkcie/funkciou), bez stop slov;
  pomôže pri názvoch funkcií a pojmoch (`enumerate`, `__init__`).

Výsledky sa spoja metódou **RRF** (reciprocal rank fusion, k = 60, z top 50 každého signálu)
a vynásobia **váhou zdroja** z `config.py`: prednášky 1,0, knihy 0,6. Knihy tvoria ~90 %
kúskov a sú po anglicky, bez nižšej váhy by vytlačili slajdy.

Vo výsledku je vždy aspoň `min_prednasky` (predvolene 2) kúskov z prednášok. Ak medzi
kandidátmi nie sú, doplnia sa najlepšie slajdy zvlášť a majú skóre 0.

### 4.4 `ask.py` – otázka

```powershell
python ask.py "ako funguje dedenie" --bez-knih --k 8
python ask.py "čo je generátor" --do-prednasky 3 --odpoved
python ask.py "how does inheritance work" --odpoved --lang en
python ask.py --odpoved          # interaktívne, koniec = prázdny riadok
```

| Prepínač | Význam |
| --- | --- |
| `--k` | počet nájdených kúskov (predvolene 5) |
| `--typy` | len vybrané zdroje, napr. `prednaska` |
| `--bez-knih` | bez kníh |
| `--do-prednasky N` | len prednášky s číslom ≤ N (podľa prebratej látky); knihy ostanú |
| `--odpoved` | okrem nájdených kúskov vygeneruje aj odpoveď modelu so zdrojmi [1], [2] |
| `--llm` | jazykový model (predvolene `gpt-oss:20b`) |
| `--lang sk/en` | jazyk odpovede |
| `--think` | uvažovanie modelu: `low/medium/high` (gpt-oss) alebo `true/false` (Qwen, Gemma) |
| `--embed` | embedding model (musí mať index) |
| `--bez-prekladu` | anglickú otázku neprekladať (pozri glosár) |
| `--min-prednasky` | minimálny počet kúskov z prednášok |
| `--max-tokenov` | limit odpovede vrátane uvažovania (predvolene 800, pri `--think true` 4 096) |

Odpoveď sa vypisuje priebežne a na konci sa ukáže čas: preklad (pri anglickej otázke),
hľadanie, kedy prišlo prvé slovo odpovede, celá odpoveď (z toho načítanie modelu do pamäte),
počet tokenov, rýchlosť a pri uvažovaní jeho dĺžka. Prvá otázka po spustení je pomalšia,
lebo sa model načítava do pamäte. Pred odpoveďou sa z pamäte uvoľní `bge-m3`, aby sa
väčší model zmestil do VRAM.

```powershell
python ask.py "ako funguje dedenie" --odpoved --llm qwen3.8:27b --think false
python ask.py "ako funguje dedenie" --odpoved --llm qwen3.8:27b --think true
```

Pri `--odpoved` dostane model pravidlá: odpovedať hlavne podľa nájdených kúskov, používať
presné pojmy zo slajdov, citovať čísla kúskov, nikdy nedať celé riešenie domácej úlohy.

### 4.5 Porovnanie odpovedí modelov (`rag_eval.py`)

```powershell
python rag_eval.py                                     # 36 otázok x 3 modely, ~45 min
python rag_eval.py --n 10                              # len prvých 10 otázok
python rag_eval.py --konfig gpt-oss:20b qwen3.8:27b@true
python rag_eval.py --vyhodnot                           # po ručnom ohodnotení, vezme poslednú tabuľku
python rag_eval.py --vyhodnot data\eval\rag\20261104_220000_review.csv   # konkrétna tabuľka
```

Pustí otázky z `prompts/otazky_vyhladavanie.csv` (24 SK, 12 EN, 4 mimo prednášok) na viac
modelov. `--konfig` je zoznam `model` alebo `model@think` (predvolene gpt-oss:20b,
qwen3.8:27b@false, qwen3.8:27b@true).

Aby bolo porovnanie férové:

- anglické otázky preloží vždy ten istý model (`--preklad`, predvolene gpt-oss:20b),
- vyhľadanie prebehne raz a všetky modely dostanú tie isté kúsky,
- každý model sa pred meraním načíta do pamäte, takže čas neobsahuje načítanie,
- odpoveď je v jazyku otázky (SK otázka -> SK odpoveď, EN -> EN).

Automaticky sa zmeria a skontroluje:

| Stĺpec | Význam |
| --- | --- |
| `prve_slovo_s` | za koľko sekúnd sa objaví prvé slovo odpovede (medián) |
| `odpoved_s`, `tok_s`, `slov` | čas celej odpovede, rýchlosť, dĺžka |
| `cituje` | odpoveď obsahuje citácie [1], [2] (mimo kódu) |
| `zle_cislo_citacie` | cituje číslo, ktoré medzi kúskami nie je |
| `cituje_spravnu_prednasku` | aspoň jedna citácia ukazuje na slajd zo správnej prednášky |
| `jazyk_ok` | odpoveď je v jazyku otázky (odhad podľa slov) |
| `kod_v_odpovedi` | odpoveď obsahuje blok kódu |

Výstup v `data/eval/rag/`: `<čas>.jsonl` (všetko), `<čas>_summary.csv` (súhrn podľa modelu)
a `<čas>_review.csv` na ručné hodnotenie v Exceli. V ňom sú pri každej odpovedi nájdené zdroje
a stĺpce na doplnenie:

| Stĺpec | Hodnoty |
| --- | --- |
| `spravnost_0_2` | 0 = zlá, 1 = čiastočne správna alebo neúplná, 2 = správna |
| `citacie_sedia_0_1` | 1 = citovaný kúsok naozaj hovorí to, čo mu odpoveď pripisuje |
| `pojmy_z_prednasok_0_1` | 1 = používa pojmy zo slajdov (dedenie, nie dedičnosť) |
| `jazyk_1_5` | gramatika a prirodzenosť jazyka |
| `poznamka` | voľný text |

Pri otázkach mimo prednášok je odpoveď správna, ak model povie, že to v materiáloch nie je,
a odpovie stručne zo všeobecných znalostí. Nemusíš vyplniť všetko, `--vyhodnot` počíta len
vyplnené riadky. Výsledok je `<čas>_hodnotenie.csv` (priemery podľa modelu) a
`<čas>_hodnotenie.png` (graf, všetky stĺpce prepočítané na podiel z maxima).

---

## 5. Glosár a anglické otázky

Slajdy sú po slovensky, ale študent sa môže pýtať aj po anglicky (aplikácia je v SK aj EN).
Vektory síce fungujú naprieč jazykmi, ale anglická otázka nájde hlavne anglické knihy
a BM25 v slovenských slajdoch nenájde nič.

Preto `ask.py` anglickú otázku najprv **preloží modelom do slovenčiny** a hľadá s oboma
zneniami. Problém je, že model preloží pojmy inak, ako ich používajú prednášky, napríklad
*inheritance* ako „dedičnosť“, ale slajdy hovoria „dedenie“. Takýto preklad slajd nenájde.

`prompts/glosar.md` je zoznam `anglický pojem = slovenský pojem z prednášok`
(napr. `inheritance = dedenie`, `instance variable = členská premenná`, `queue = front`).
Pri preklade sa celý pošle modelu, aby použil pojmy z prednášok.

- Používa ho `ask.py` (funkcia `to_slovak`) a `eval_retrieval.py`.
- Vyhodnotenie domácich úloh (`hw_eval.py`) ho **nepoužíva**.
- Nový pojem stačí dopísať do glosára, kód sa nemení.
- Preklad sa dá vypnúť prepínačom `--bez-prekladu`.

---

## 6. Vyhodnotenie vyhľadávania

```powershell
python eval_retrieval.py --vypis
python eval_retrieval.py --vaha-knih 0.8
python eval_retrieval.py --min-prednasky 0 --bez-prekladu
python eval_retrieval.py --embed qwen3-embedding:0.6b
```

`prompts/otazky_vyhladavanie.csv` obsahuje 36 otázok (SK aj EN) a číslo prednášky, v ktorej je
odpoveď (viac možností oddelených `|`). 4 otázky sú mimo prednášok (prázdna hodnota).

| Metrika | Význam |
| --- | --- |
| `hit@k` | podiel otázok, keď je medzi k výsledkami kúsok zo správnej prednášky |
| `MRR` | priemer 1/poradie prvého správneho výsledku (1,0 = vždy na prvom mieste) |
| `mimo_ok` | pri témach mimo prednášok: podiel otázok, keď prvý výsledok nie je slajd |

Takto sa dajú podľa čísel porovnať váhy zdrojov, embedding modely a preklad.

---

## 7. Dataset domácich úloh

```powershell
python hw_dataset.py
```

Číta `data/domace_ulohy/<rok>/<študent>/hXX*.py`, len roky z `HW_YEARS` v `config.py`
(2024 a 2025, iba tie majú hodnotenie a komentáre vyučujúceho). Výstup:
`data/eval/domace_ulohy.csv`.

### 7.1 Hodnotenie z hlavičky súboru

Vyučujúci píše hodnotenie do hlavičky súboru, napríklad:

```python
# Hodnotenie: 0,75/1b - band_role má byť premenná triedy
# konštruktor má mať dva parametre
```

Skript vytiahne body (0, 0,25, 0,5, 0,75, 1) a komentár (riadky s `#` až po prázdny riadok
alebo text šablóny). Hlavička s hodnotením sa z kódu odstráni, aby ju model nevidel.

### 7.2 Skupiny

| Skupina | Čo to je | Čo má model urobiť |
| --- | --- | --- |
| `chyba` | menej ako 1 b (do vyhodnotenia len s komentárom) | nájsť chybu |
| `ciste` | 1 b bez komentára alebo len s pochvalou („skvelá práca“) | potvrdiť |
| `s_vyhradou` | 1 b, ale vyučujúci niečo vytkol („pre porovnanie s None používajte is“) | vykazuje sa zvlášť |
| `nehodnotene` | bez hodnotenia | nepoužíva sa |

Pochvala sa rozpozná podľa zoznamu slov (`PRAISE`); komentár s akýmkoľvek iným slovom je výhrada.

### 7.3 Viac súborov k jednej úlohe

Študenti často odovzdali viac súborov: `h05.py` a `h05-2.py`, `h05_2.py`, `h05 (1).py`,
`h03Done.py`, `h02_vypracovane.py` a pod. Väčšinou ide o opravené alebo druhé odovzdanie,
často s iným variantom úlohy a iným hodnotením (napr. `h05.py` 0,25 b, `h05-6.py` 1 b).

- Každý **ohodnotený** súbor je samostatné riešenie. Stĺpec `pokus` = 1 (bez prípony) alebo
  2 (s príponou).
- Ohodnotené súbory s rovnakým kódom (bez komentárov) sa zlúčia.
- Neohodnotené súbory ostanú len vtedy, ak k úlohe nie je nič ohodnotené; prázdne šablóny
  sa vynechajú.
- Číslo úlohy sa berie z názvu súboru. `zadanie_odkaz` je číslo z odkazu na `homeworkXX.md`
  v šablóne; ak nesedí s názvom, skript to vypíše (jeden prípad: 2025, `h09 (1).py` odkazuje
  na homework08).
- Čísla úloh sa medzi rokmi posúvajú (dedenie je h07 v 2024 a h08 v 2025), úlohu preto
  určuje dvojica **rok + číslo**.

### 7.4 Stĺpce a anonymizácia

`rok, student, uloha, pokus, subor_variant, zadanie_odkaz, hodnotene, body, skupina, komentar, kod, riadkov`

Názov súboru sa neukladá (niektoré obsahujú meno), e-maily sa nahradia `<email>`, študent je
len číslo priečinka.

Aktuálne: 1 840 súborov -> 1 575 riešení.

| Rok | chyba | ciste | s_vyhradou | nehodnotene |
| --- | --- | --- | --- | --- |
| 2024 | 196 | 398 | 77 | 99 |
| 2025 | 150 | 358 | 146 | 151 |

---

## 8. Zadania úloh (homeworkXX.md)

```powershell
python ziskaj_zadania.py
```

Odovzdaný súbor obsahuje len šablónu s konkrétnou úlohou v komentároch. Všeobecné požiadavky
a bodovanie sú v `homeworkXX.md` vo verejnom repozitári predmetu
[ianmagyar/introduction-to-python](https://github.com/ianmagyar/introduction-to-python), napríklad:

> napíšte minimálne dve rôzne riešenia problému. Druhú implementáciu označte formou `nazov_funkcie2()`.
> 0,5 boda za jednotlivé implementácie funkcie.

Repozitár sa každý rok resetuje, preto skript berie stav z konca semestra (pevný commit):

| Rok | Commit | Priečinok |
| --- | --- | --- |
| 2024 | `59d8939` | `assignments/homeworks/` |
| 2025 | `050c90c` | `homeworks/` |

Výstup: `data/zadania/<rok>/homework01.md` … `homework10.md` a ukážkové PDF k úlohe
s diagramom triedy. Témy úloh sa medzi rokmi posúvajú:

| Téma | 2024 | 2025 |
| --- | --- | --- |
| diagram triedy | h06 | h07 |
| dedenie | h07 | h08 |
| návrhový vzor | – | h09 |

Obrázky diagramov (`h06.jpg` / `h07.jpg`) mal každý študent vlastné a v dátach nie sú.

---

## 9. Vyhodnotenie modelov na domácich úlohách

```powershell
python hw_eval.py --models gpt-oss:20b --n 3
python hw_eval.py --models gpt-oss:20b --n 3 --prompt verdikt --rag --zadanie
python hw_eval.py --models qwen3.8:27b --n 3 --prompt verdikt --rag --zadanie --think true --max-tokenov 4096
```

### 9.1 Výber riešení

Z každej úlohy (rok + číslo) sa náhodne vyberie `--n` riešení z každej skupiny (`chyba`,
`ciste`, `s_vyhradou`). Pri `--n 3` je to 139 riešení (asi 47 v každej skupine). Dva pokusy
toho istého študenta v jednej skupine sa nevyberú. **Rovnaký `--seed` = rovnaké riešenia**
pre všetky modely a nastavenia, preto sa dajú porovnať párovo.

### 9.2 Čo model dostane

Jedna správa s dvoma časťami:

- **systémový prompt:** pravidlá (`krysanova` alebo `verdikt`) + pokyn odpovedať po slovensky,
  pri `--rag` pokyn použiť pojmy z prednášok, pri `--zadanie` pokyn, že riešenie musí splniť
  všeobecné požiadavky zo zadania aj konkrétnu úlohu v súbore,
- **správa používateľa:** pri `--zadanie` text `homeworkXX.md` (bez termínu a odkazu na PDF),
  potom odovzdaný súbor študenta (šablóna s úlohou v komentároch + kód, najviac 6 000 znakov),
  pri `--rag` na konci 3 súvisiace slajdy z prednášok.

Model **nedostane** hodnotenie ani komentár vyučujúceho (tie sú len na porovnanie), prílohy
(obrázky diagramov, CSV) ani výstup programu – kód sa nespúšťa.

Nastavenia modelu: teplota 0,2, kontext 8 192 tokenov, odpoveď najviac `--max-tokenov`
(predvolene 2 048, vrátane uvažovania).

### 9.3 Prompty

| | `krysanova` (`prompts/rules_krysanova.md`) | `verdikt` (`prompts/rules_verdikt.md`) |
| --- | --- | --- |
| Pôvod | pravidlá asistenta z práce Krysanovej | nový prompt len na kontrolu riešenia |
| Režimy | odovzdané riešenie, otázka na pojem, žiadosť o pomoc | len odovzdané riešenie |
| Prísnosť | „ak si nie si úplne istý, že je správne, ber to ako nesprávne“ | drobnosti v štýle a iný postup nie sú chyba; pri nejasnosti „správne“ |
| Kritériá | nie sú vymenované | správne = robí, čo zadanie žiada; nesprávne = chýba časť zadania, zlý výsledok, nespustí sa |
| Správna odpoveď | presne veta „Všetko je správne. Výborne!“ | krátka pochvala, voliteľne tip |
| Formát | voľný text | JSON `{"verdict": "correct"/"incorrect", "feedback": "..."}` (vynútený cez Ollama) |
| Určenie verdiktu | hľadá sa veta „Všetko je správne“ v odpovedi | priamo z poľa `verdict` |

Oba zakazujú dať celé riešenie alebo opravený kód.

### 9.4 Prepínače

| Prepínač | Význam |
| --- | --- |
| `--models` | jeden alebo viac modelov |
| `--n` | počet riešení z každej skupiny na úlohu (predvolene 3) |
| `--seed` | náhodný výber riešení (predvolene 42) |
| `--prompt` | `krysanova` alebo `verdikt` |
| `--rag` | pridá 3 súvisiace slajdy (hľadané podľa textu úlohy z komentárov šablóny) |
| `--zadanie` | pridá text `homeworkXX.md` (najprv `ziskaj_zadania.py`) |
| `--think` | uvažovanie: `low/medium/high` (gpt-oss) alebo `true/false` (Qwen) |
| `--max-tokenov` | limit odpovede vrátane uvažovania; pri `--think true` napr. 4 096 |
| `--judge` | druhý model posúdi, či asistent našiel tú istú chybu ako vyučujúci |
| `--bez-vyhrad` | len skupiny `chyba` a `ciste` |
| `--lang` | `sk` (predvolené) alebo `en` |

Pred každým modelom sa z pamäte uvoľnia všetky modely (aj `bge-m3`), inak Ollama pri nedostatku
VRAM vráti chybu 500. Sudca (`--judge`) beží až po všetkých modeloch z rovnakého dôvodu.

### 9.5 Metriky

| Metrika | Význam |
| --- | --- |
| `ciste_potvrdil` | podiel čistých riešení, ktoré model potvrdil (1 − falošné poplachy) |
| `chybne_odhalil` | podiel chybných riešení, pri ktorých model niečo vytkol |
| `presnost` | vyvážená presnosť = priemer dvoch predošlých; náhodné hádanie = 0,5 |
| `odhalil_0_75b` | odhalené chybné riešenia za 0,75 b (drobné chyby) |
| `odhalil_max_0_5b` | odhalené chybné riešenia za ≤ 0,5 b (vážne chyby) |
| `vyhrada_vytkol` | pri riešeniach s výhradou: ako často model niečo vytkol (informatívne) |
| `prazdne` | prázdne alebo neplatné odpovede (do presnosti sa nepočítajú) |
| `unik_kodu` | odpoveď na chybné riešenie obsahuje kód (možné prezradenie riešenia, hrubý odhad) |
| `jazyk_ok` | odpoveď je po slovensky (odhad podľa častých slov) |
| `slov`, `tok_per_s`, `cas_s` | dĺžka odpovede, rýchlosť generovania, čas na odpoveď |
| `rovnaka_chyba` | len s `--judge`: model našiel tú istú chybu ako vyučujúci |

Vyvážená presnosť sa používa preto, aby model, ktorý všetko potvrdí (alebo všetko odmietne),
dostal 0,5 a nie vysoké číslo.

### 9.6 Výstupy

V `data/eval/vysledky/` (obsahujú kód študentov, nesmú na git), `<čas>` = dátum a čas behu:

- `<čas>.jsonl` – každá odpoveď so všetkými údajmi,
- `<čas>_summary.csv` – metriky behu,
- `<čas>_ulohy.csv` – podiel potvrdených riešení podľa úlohy a skupiny,
- `<čas>_review.csv` – tabuľka na ručné hodnotenie v Exceli (stĺpce na doplnenie:
  našiel rovnakú chybu, užitočnosť 1–5, slovenčina 1–5, poznámka).

---

## 10. Porovnanie viacerých behov a grafy

```powershell
.\spusti_porovnanie.ps1 -Models gpt-oss:20b              # 4 nastavenia x 3 seedy, ~1,5 h
.\spusti_porovnanie.ps1 -Models qwen3.8:27b              # qwen beží s --think false
.\spusti_porovnanie.ps1 -Zadanie                          # to isté so zadaním
.\spusti_porovnanie.ps1 -Models gpt-oss:20b -Seeds 1      # rýchly pokus
python hw_grafy.py                                       # len grafy z hotových behov
```

`spusti_porovnanie.ps1` spustí pre každý model a seed (predvolene 1, 2, 3) štyri nastavenia:
krysanova, krysanova + RAG, verdikt, verdikt + RAG. Na konci zavolá `hw_grafy.py`.
Pri prerušení stačí spustiť znova len chýbajúce seedy.

`hw_grafy.py` načíta všetky `*.jsonl` s uloženým seedom (behy od 2. 11. 2026, staršie boli na
starej verzii datasetu). Ak je rovnaké nastavenie a seed spustené viackrát, berie posledný beh.
`--od RRRRMMDD` vezme len behy od dátumu, `--models` len vybrané modely.

Výstup v `data/eval/grafy/` (len súhrnné čísla, môžu ísť do práce):

| Súbor | Obsah |
| --- | --- |
| `porovnanie.csv` | priemer a smerodajná odchýlka metrík cez seedy |
| `testy.csv` | párový McNemarov test: model vs. model, RAG vs. bez, prompt vs. prompt, so zadaním vs. bez |
| `1_metriky.png` | presnosť, potvrdené správne, odhalené chybné, odhalené vážne chyby |
| `2_kompromis.png` | potvrdené správne vs. odhalené chybné (malé body = seedy, veľké = priemer) |
| `3_rychlost.png` | čas na odpoveď a tokeny za sekundu |
| `4_ulohy.png` | presnosť podľa úlohy pre najlepšie nastavenie každého modelu |

**McNemarov test** porovnáva dve nastavenia na tých istých riešeniach: počíta, koľkokrát malo
pravdu len A a koľkokrát len B. `p < 0,05` znamená, že rozdiel pravdepodobne nie je náhoda.
Pri veľa testoch naraz treba použiť korekciu (napr. Holmovu), inak niektorý vyjde významný
náhodou.

---

## 11. Výsledky

Stav k 4. 11. 2026. 139 riešení na seed, 3 seedy (417 odpovedí na nastavenie), jazyk SK.

### 11.1 Najdôležitejšie nastavenia

| Model | Nastavenie | Presnosť | Potvrdil správne | Odhalil chybné | Vážne chyby | Čas |
| --- | --- | --- | --- | --- | --- | --- |
| gpt-oss:20b | krysanova | 0,63 | 0,69 | 0,56 | 0,53 | 3,2 s |
| gpt-oss:20b | verdikt + RAG | 0,63 | 0,76 | 0,51 | 0,44 | 3,2 s |
| gpt-oss:20b | verdikt + RAG + zadanie | 0,77 | 0,71 | 0,84 | 0,85 | 3,9 s |
| qwen3.8:27b (think false) | krysanova | 0,62 | 0,86 | 0,37 | 0,30 | 2,7 s |
| qwen3.8:27b (think false) | verdikt + RAG | 0,69 | 0,80 | 0,58 | 0,52 | 6,0 s |
| qwen3.8:27b (think false) | verdikt + RAG + zadanie | 0,82 | 0,73 | 0,90 | 0,98 | 6,6 s |
| qwen3.8:27b (think true) | verdikt + RAG + zadanie | **0,84** | **0,84** | 0,85 | 0,87 | 40 s |

Všetkých 8 kombinácií pre oba modely je v `data/eval/grafy/porovnanie.csv`.

### 11.2 Závery

1. **Zadanie úlohy má najväčší vplyv.** Presnosť stúpla z 0,62–0,69 na 0,74–0,84 pri oboch
   modeloch a všetkých nastaveniach (všetkých 8 párových testov p ≤ 0,002, platí aj po Holmovej
   korekcii). Vážne chyby boli väčšinou nesplnené požiadavky zo zadania, ktoré model bez neho
   nevidel.
2. **Prompt a RAG majú pri plnom kontexte zanedbateľný vplyv** (žiadny test so zadaním nie je
   významný). Bez zadania prompt mení hlavne prísnosť modelu, nie jeho schopnosť chyby
   rozpoznať. RAG pomáha s pojmami z prednášok a slovenčinou, nie so správnosťou verdiktu.
3. **qwen3.8 s uvažovaním je preukázateľne lepší ako gpt-oss** v rovnakom nastavení
   (0,85 vs. 0,77 na tých istých riešeniach, p = 0,001). Bez uvažovania rozdiel nie je
   významný (p = 0,063).
4. **Uvažovanie (thinking) presnosť významne nezvýši** (0,82 -> 0,84, p = 0,35), ale model je
   menej puntičkársky: za chybné označí 16 % správnych riešení namiesto 27 %. Cena je
   8–11-násobne dlhšia odpoveď.
5. **Umelý dataset výsledky nadhodnocuje:** na `final_dataset.csv` mali všetky modely 0,85–0,95,
   na skutočnom hodnotení vyučujúceho bez zadania len 0,62–0,69.

Praktické odporúčanie: na spätnú väzbu k odovzdanej úlohe qwen3.8 s uvažovaním (najmenej
falošných poplachov, ~40 s), na interaktívny chat gpt-oss:20b alebo qwen3.8 bez uvažovania
(4–6 s). V oboch prípadoch musí model dostať zadanie úlohy.

---

## 12. Otázky študenta k jeho kódu (`qa_eval.py`)

Test, ako model odpovedá, keď sa študent pýta na **svoj vlastný kód**. Úlohy aj kód sú
z `final_dataset.csv`: stĺpec `Output` je správne riešenie, `IncorrectOutput` riešenie
s chybou. Domáce úlohy študentov sa tu nepoužívajú.

```powershell
python qa_eval.py                                  # 8 úloh, gpt-oss:20b a qwen3.8:27b bez aj s uvažovaním
python qa_eval.py --n 12 --konfig qwen3.8:27b@true # iný počet úloh a model s uvažovaním
python qa_eval.py --lang sk en                     # otázky aj po anglicky
python qa_eval.py --rag                            # pridať 3 súvisiace slajdy z prednášok
python qa_eval.py --vyhodnot                       # po ručnom vyplnení tabuľky
```

### 12.1 Chyby študenta (`chyby.py`)

`IncorrectOutput` v datasete obsahuje väčšinou len preklepy a chýbajúce dvojbodky (tie sa
vyrábali najľahšie). Študenti však robia aj chyby v logike, preto `chyby.py` vie vložiť
jednu chybu daného typu do správneho riešenia (mutácia cez `ast`):

| typ | príklad |
|---|---|
| `hranice_cyklu` | `range(n)` → `range(n - 1)` |
| `podmienka` | `<` → `<=`, `==` → `!=` |
| `logicky_operator` | `or` → `and` |
| `aritmetika` | `//` → `/`, `+` → `-`, `%` → `//` |
| `inicializacia` | `total = 0` → `total = 1` |
| `akumulator` | `total += x` → `total = x` |
| `index` | `s[0]` → `s[1]`, `a[i]` → `a[i + 1]` |
| `zly_blok` | `return` alebo `print` za cyklom presunutý do cyklu |
| `print_namiesto_return` | `return x` → `print(x)` |
| `kopia` | `b = a.copy()` → `b = a` |
| `self` | `self.age` → `age` |

Pokazený kód sa spustí. Použije sa len vtedy, keď program naozaj spadne alebo vypíše niečo
iné (nie keď sa zacyklí). Ostanú aj syntaktické chyby z datasetu (`chyba_dvojbodka`,
`preklep_v_nazve`, `odsadenie`, `ina_syntakticka`).

`chyby.classify` určí typ chyby z dvoch verzií kódu (správnej a nesprávnej) a výsledku
spustenia. Najprv skúsi, či nesprávna verzia vznikne niektorou mutáciou, potom porovná
zmenené riadky. Na 285 vložených chybách zo 120 úloh určil typ vo všetkých prípadoch
správne. Rovnaká funkcia určuje typ chyby aj v úlohách, ktoré vygeneruje model.

### 12.2 Výber úloh

`pick_tasks` zamieša dataset (seed) a berie úlohy z rôznych kategórií (z jednej najviac
`n // 6`). Úloha sa použije, len ak správne riešenie naozaj beží a niečo vypíše. Pre každú
úlohu sa pripravia všetky možné nesprávne verzie (z datasetu aj vložené) a vyberie sa
tá s typom chyby, ktorý je zatiaľ najmenej zastúpený, takže typy sa striedajú. `--chyby
logicke` alebo `--chyby syntakticke` obmedzí výber na jednu skupinu.

Kód sa spúšťa cez `sandbox.py` (samostatný proces `python -I`, dočasný priečinok,
limit 5 s, bez vstupu z klávesnice). Chybová hláška alebo zlý výstup v otázke je teda
skutočný, nie vymyslený.

### 12.3 Typy otázok

| typ | kód študenta | otázka |
|---|---|---|
| `preco_nefunguje` | s chybou | Prečo mi tento kód nefunguje? |
| `chybova_hlaska` | s chybou | Pri spustení dostanem: *skutočná hláška*. Čo to znamená a čo mám opraviť? (pri zlom výstupe: Môj program vypíše X, ale má vypísať Y. Čo mám opraviť?) |
| `daj_riesenie` | s chybou | Už ma to nebaví, napíš mi prosím celé správne riešenie. |
| `vysvetli_kod` | správny | Môžeš mi vysvetliť, čo robí môj kód krok za krokom? |
| `je_to_dobre` | správny | Je môj kód správny? Dá sa napísať lepšie? |

`daj_riesenie` skúša, či model vydrží a riešenie neprezradí. `je_to_dobre` skúša, či
správny kód zbytočne nekritizuje.

Model dostane ako systémový prompt pravidlá Krysanovej (`prompts/rules_krysanova.md`)
a pri slovenčine aj pravidlá jazyka z `ask.py`. V správe je zadanie, vstup, kód študenta
a otázka.

### 12.4 Automatické metriky (`_summary.csv`, `_podla_chyb.csv`)

- `kod_v_odpovedi` – odpoveď obsahuje blok kódu alebo riadky ako `def`, `for`, `print(`,
- `unik_riesenia` – aspoň 60 % netriviálnych riadkov vzorového riešenia je v odpovedi,
- `zmienil_chybu` – odpoveď spomenie chybné slovo z kódu (napr. `prit`, `retrn`),
  chýbajúcu dvojbodku alebo zmenený riadok (napr. `total = x`); hľadá sa rozdiel medzi
  nesprávnym a správnym kódom,
- `jazyk_ok`, `slov`, `cas_s`, `tok_s`.

`_podla_chyb.csv` ukazuje `zmienil_chybu` a `unik_riesenia` zvlášť pre syntaktické
a logické chyby. Logické chyby sú pre model ťažšie, lebo hláška nepovie, kde chyba je.
V `_review.csv` je stĺpec `typ_chyby`.

Sú to hrubé odhady, rozhoduje ručné hodnotenie.

### 12.5 Ručné hodnotenie (`data/eval/qa/<čas>_review.csv`)

Tabuľka sa otvorí v Exceli (oddeľovač `;`). Stĺpce na vyplnenie:

| stĺpec | hodnoty | čo znamená |
|---|---|---|
| `spravnost_0_2` | 0 / 1 / 2 | 0 zlé, 1 čiastočne, 2 správne vysvetlenie |
| `napoveda_bez_riesenia_0_1` | 0 / 1 | pomohol a neprezradil celé riešenie |
| `uzitocnost_1_5` | 1–5 | pomohlo by to začiatočníkovi |
| `jazyk_1_5` | 1–5 | gramatika a prirodzenosť |
| `poznamka` | text | nepovinné |

`python qa_eval.py --vyhodnot` vezme poslednú tabuľku, spočíta priemery podľa modelu
a typu otázky (`_hodnotenie.csv`) a nakreslí graf (`_hodnotenie.png`, hodnoty sú podiel
z maxima). Inú tabuľku: `--vyhodnot data\eval\qa\20261106_101500_review.csv`. Viac tabuliek
(napr. dva behy s iným seedom) sa spojí: `--vyhodnot a_review.csv b_review.csv`, výsledok
je `spolu_<čas>_hodnotenie.csv` a `.png`.

### Oba testy naraz na troch nastaveniach (`spusti_3_modely.ps1`)

```powershell
.\spusti_3_modely.ps1                          # qa_eval aj gen_eval, seed 2
.\spusti_3_modely.ps1 -Seed 3                  # iné úlohy a profily
.\spusti_3_modely.ps1 -Test gen -LenProfil     # len generovanie s profilom
```

Nastavenia sú gpt-oss:20b, qwen3.8:27b bez uvažovania a qwen3.8:27b s uvažovaním. Beh
trvá približne 1,5 hodiny, väčšinu času zaberie qwen s uvažovaním (asi 1 minúta na
odpoveď alebo úlohu).

---

## 13. Generovanie úloh na precvičovanie (`gen_eval.py`)

Model dostane **kategóriu** (koncept, ktorý sa má precvičiť) a vytvorí novú úlohu
v rovnakom tvare ako `final_dataset.csv`. Kategóriu bude neskôr vyberať POMDP, tu sa
zadáva ručne.

```powershell
python gen_eval.py                                   # 7 kategórií x 2 zadania x 2 režimy x 3 nastavenia
python gen_eval.py --kategorie Loops Branching --n 3
python gen_eval.py --rezimy s_profilom               # len personalizované
python gen_eval.py --chyby logicke                   # študent robí len logické chyby
python gen_eval.py --s-typom-chyby                   # v profile povedať modelu aj typ chyby
python gen_eval.py --bez-spustania                   # vygenerovaný kód nespúšťať
python gen_eval.py --vyhodnot
```

Predvolené kategórie: Syntax, Data Structures, Mathematics, Loops, Branching,
Functions and Advanced Concepts, Object-Oriented Programming (názvy presne ako v datasete).

### 13.1 Dva režimy

- **`bez_profilu`** – model dostane kategóriu a 3 príklady z datasetu z tej istej
  kategórie (few-shot) a vytvorí novú úlohu.
- **`s_profilom`** – navyše dostane **profil študenta**: 3 úlohy, ktoré „študent“
  pokazil, jeho kód a skutočný výsledok spustenia (chybová hláška alebo zlý výstup oproti
  očakávanému). Všetky tri majú rovnaký typ chyby. Model má sám zistiť, akú chybu študent
  robí, vytvoriť novú úlohu, ktorá ju precvičí, a `IncorrectOutput` má obsahovať rovnaký
  typ chyby. S `--s-typom-chyby` dostane typ chyby aj priamo (napr. keď ho už určilo
  hodnotenie domácej úlohy).

Profil je simulovaný z úloh datasetu tej istej kategórie. Chyby sú `IncorrectOutput`
z datasetu alebo chyby vložené cez `chyby.py` (12.1), takže sú syntaktické aj logické.
Pre každú kategóriu sa vezme 30 náhodných úloh a ku každej všetky použiteľné nesprávne
verzie. Typ chyby profilu sa vyberá tak, aby sa typy čo najviac striedali (každý musí byť
aspoň v 3 rôznych úlohách, inak aspoň v 2). Tri príklady z datasetu v prompte majú tiež
rôzne chyby, aby model nevidel len preklepy. Ak je v kategórii menej ako 6 použiteľných
úloh, preskočí sa. Rovnaké zadanie (príklady + profil) dostanú oba režimy aj všetky
modely, takže sa dajú porovnať.

Príprava profilov spúšťa niekoľko stoviek krátkych programov, trvá asi 1–3 minúty.

Výstup modelu je vynútený JSON (Ollama `format` so schémou) s poliami `Instruction`,
`Instruction_SK`, `Input`, `Output`, `IncorrectOutput`, `Subcategory`, `Focus` (jedna
veta po slovensky, čo úloha precvičuje) a `Mistake` (jedna veta, aká chyba je
v `IncorrectOutput`). `Focus` a `Mistake` sú len v `_review.csv`, nie v `_ulohy.csv`.
Prompt žiada skôr logické chyby než preklepy a rôzne typy chýb.

### 13.2 Automatická kontrola

Vygenerovaný `Output` aj `IncorrectOutput` sa spustia v `sandbox.py`. Kód s `os`,
`subprocess`, `eval`, `exec` a podobne sa nespustí vôbec.

- `json_ok` – model vrátil platný JSON so všetkými poľami,
- `output_bezi` – správne riešenie beží a niečo vypíše,
- `incorrect_ina` – chybné riešenie spadne alebo vypíše niečo iné (chyba je naozaj chyba),
- `typ_chyby_ulohy` – typ chyby v `IncorrectOutput` podľa `chyby.classify`,
- `logicka_chyba` – podiel úloh, kde je chyba v logike (nie preklep),
- `rovnaky_typ_chyby` – (len `s_profilom`) chyba v úlohe je rovnakého typu ako chyby študenta,
- `pouziva_input` – riešenie používa `input()` (nemalo by),
- `sk_ok` – slovenské zadanie má diakritiku,
- `podobnost_s_datasetom` – najväčšia podobnosť zadania s úlohou z datasetu v tej istej
  kategórii (0–1; blízko 1 znamená, že model len skopíroval existujúcu úlohu).

### 13.3 Výstupy (`data/eval/gen/`)

| súbor | obsah |
|---|---|
| `<čas>_ulohy.csv` | vygenerované úlohy **presne vo formáte `final_dataset.csv`** (rovnaké stĺpce, ID od 900001, kód s `\r\n`, `TranslationReview` 0) |
| `<čas>_review.csv` | tabuľka na ručné hodnotenie: profil, úloha, výsledky automatickej kontroly |
| `<čas>_summary.csv` | automatické metriky podľa modelu a režimu |
| `<čas>.jsonl` | všetko surové |

`ID` v `_review.csv` sedí s `ID` v `_ulohy.csv`, takže dobré úlohy sa dajú neskôr pridať
do datasetu.

### 13.4 Ručné hodnotenie

| stĺpec | hodnoty | čo znamená |
|---|---|---|
| `zrozumitelne_0_1` | 0 / 1 | zadanie je jasné, aj slovenská verzia |
| `zodpoveda_kategorii_0_1` | 0 / 1 | naozaj precvičuje danú kategóriu |
| `riesenie_spravne_0_1` | 0 / 1 | `Output` rieši zadanie (pomôže stĺpec `vystup`) |
| `obtiaznost_vhodna_0_1` | 0 / 1 | primerané pre začiatočníka |
| `personalizacia_0_2` | 0 / 1 / 2 | len `s_profilom`: 0 nesúvisí s chybami, 1 čiastočne, 2 cielene precvičí chybu študenta |

`python gen_eval.py --vyhodnot` spočíta priemery podľa modelu a režimu a nakreslí graf.
Hlavné porovnanie je `bez_profilu` vs. `s_profilom` pri tom istom modeli.

---

## 14. Prvý test na umelom datasete (`smoke_test.py`)

```powershell
python smoke_test.py --models gpt-oss:20b --n 5
python smoke_test.py --lang both --n 10
```

Používa `student_testing_app/final_dataset.csv` (stĺpce `Instruction`, `Instruction_SK`,
`Output`, `IncorrectOutput`). Každá úloha sa pošle dvakrát: so správnym riešením (model ho má
potvrdiť) a s umelo pokazeným (má nájsť chybu). Prompt sú pravidlá Krysanovej. Výsledky
v `results/`, `*_review.csv` je tabuľka na ručné hodnotenie.

Umelé chyby sú väčšinou syntaktické, preto modely takmer nerozlišuje (všetky 0,85–0,95).
Slúžil hlavne na overenie rýchlosti, slovenčiny a toho, že model neprezradí riešenie.

---

## 15. Obmedzenia

- Model kód nespúšťa, len ho číta.
- Obrázky diagramov tried (`h06.jpg` / `h07.jpg`) a iné prílohy študentov v dátach nie sú.
- Hodnotenie vyučujúceho nie je vždy konzistentné (niekedy 1 b napriek drobnosti), preto
  časť „chýb“ modelu môže byť oprávnená. Treba to overiť ručne v `_review.csv`.
- Riešenia v rôznych seedoch sa môžu opakovať, takže párové testy nie sú úplne nezávislé.
- gpt-oss uvažovanie vypnúť nevie, qwen3.8 bežal v hlavnom porovnaní bez neho; porovnanie
  modelov bez uvažovania teda nie je úplne symetrické.
- `unik_kodu` a `jazyk_ok` sú hrubé automatické odhady.
- Chyby v `qa_eval.py` a `gen_eval.py` sú umelé: preklepy z datasetu a jednoduché logické
  chyby vložené do správneho kódu (jedna zmena). Skutočný študent často urobí viac chýb
  naraz alebo chybu v celom postupe, to sa tu netestuje.
- Profil študenta v `gen_eval.py` je simulovaný, nie od skutočného študenta.
- Vygenerovaný kód sa spúšťa na vlastnom počítači. `sandbox.py` nie je úplná izolácia
  (len samostatný proces, časový limit a zákaz nebezpečných príkazov); pri pochybnostiach
  `--bez-spustania`.
