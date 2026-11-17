# AdaptPy – návod pre študenta

AdaptPy je webová aplikácia na precvičovanie programovania v Pythone. Prispôsobuje sa úrovni študenta. Menu je vľavo (na mobile cez ikonu menu hore).

## Dashboard (/dashboard)
Úvodná stránka po prihlásení. Ukazuje karty: Predtest, Úlohy (zvládnutie tém, vyriešené úlohy, rozpracovaná úloha), Cvičenia (postup v cvičeniach), Testy, Štatistika, Profil, Spätná väzba. Vpravo dole je tento asistent.

## Predtest (/predtest)
Úvodný test, ktorý zistí úroveň študenta v jednotlivých témach (kategóriách). Robí sa iba raz, rozpracovaný predtest pokračuje tam, kde študent skončil. Úlohy a Testy sa odomknú až po dokončení predtestu. Po dokončení predtest z menu zmizne.

## Úlohy (/ulohy) – samoštúdium
- Systém (adaptívny algoritmus POMDP) priebežne vyberá úlohy z tém, ktoré študent ešte nezvláda.
- Študent napíše kód do editora a klikne na „Odpovedať“. Kód sa spustí a porovná sa výstup.
- Na úlohu je 5 pokusov. Po nesprávnej odpovedi študent uvidí, čo je zle, a kód opraví sám. Po 5. nesprávnom pokuse sa ukáže správne riešenie a úloha sa počíta ako nevyriešená.
- AI asistent v Úlohách je dostupný od začiatku: vysvetľuje pojmy a chyby, ale nikdy nedá celé riešenie.
- Nápovedy (tlačidlo „Daj mi nápovedu“): najviac 3 na úlohu, odomykajú sa postupne – každá ďalšia až po ďalšom nesprávnom pokuse. 1. nápoveda ukáže, kde je chyba, 2. vysvetlí všetky chyby a logiku riešenia, 3. ukáže štruktúru (kostru) kódu.
- Každá použitá nápoveda znižuje hodnotenie úlohy: bez nápovedy 100 %, s 1 nápovedou 75 %, s 2 nápovedami 50 %, s 3 nápovedami 25 %. Ovplyvní to aj výber ďalších úloh a zvládnutie tém.
- Vkladanie textu zvonku do editora je zakázané (kontrola originality). Systém sleduje spôsob písania; pri podozrivom písaní študent potvrdí, ako kód vznikol.
- Na dashboarde v karte Úlohy je „Zvládnutie tém“ v percentách podľa výsledkov testov a úloh.

## Cvičenia (/cvicenia)
- Interaktívne zošity (podobné Jupyter notebooku) k cvičeniam predmetu: text so zadaním a bunky s kódom.
- Postupuje sa po jednom: ďalšie cvičenie sa odomkne po dokončení predchádzajúceho.
- Bunku spustí tlačidlo „Spustiť“. Bunky nad aktuálnou sa spúšťajú spolu s ňou (premenné sa zachovajú). Pre každú bunku je časový limit.
- Cez „＋ Pridať bunku sem“ si študent pridá vlastnú bunku na skúšanie (nezapočítava sa do postupu).
- Postup v percentách = podiel úspešne spustených buniek. Keď sú všetky hotové, tlačidlo „Dokončil som“ cvičenie uzavrie.
- Cvičenie sa dá stiahnuť ako .ipynb.
- Vpravo je AI asistent cvičenia: vysvetľuje látku podľa prednášok, navádza a dá kostru riešenia. Kód vie vložiť do bunky, ale len keď to študent potvrdí a vyberie bunku.

## Testy (/hlavnytest)
Adaptívne testy – otázky sa vyberajú podľa výkonnosti študenta. Dajú sa absolvovať viackrát. Dostupné až po predteste a len ak ich vyučujúci sprístupní.

## Štatistika (/analyza)
Prehľad výsledkov: počet správnych odpovedí, správnosť, percentil a výsledky predtestu podľa kategórií.

## Materiály (/materialy)
Prednášky a knihy predmetu na stiahnutie – len tie, ktoré vyučujúci sprístupnil.

## Profil (/profile)
Úprava mena, priezviska a emailu; zmena hesla cez „Zmeniť heslo“. Zabudnuté heslo sa obnoví na prihlasovacej stránke cez „Zabudol si heslo?“ (príde email).

## Spätná väzba (/feedback-form) a Dotazník (/feedback)
Formulár spätnej väzby (nápad, chyba, pochvala) je dostupný kedykoľvek. Dotazník sa zobrazí v menu, keď ho vyučujúci zverejní.

## Jazyk a téma
Prepínač SK/EN a svetlá/tmavá téma sú vpravo hore.

## Stránka predmetu
Odkaz „Stránka predmetu“ v menu vedie na GitHub predmetu s cvičeniami.
