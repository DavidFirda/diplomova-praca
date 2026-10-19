# ============================================================
# AdaptPy - texty, ktoré server posiela študentovi v ÚLOHÁCH (SK / EN).
# Klient posiela `lang` ("sk" | "en"); neznámy jazyk -> slovenčina.
# ============================================================
TEXT = {
    "sk": {
        # --- spätná väzba k pokusu ---
        "fb.error": "Kód skončil chybou: {error}",
        "fb.no_output": "Program nič nevypísal. Skontroluj, či výsledok vypisuješ cez print().",
        "fb.line_count": "Výstup má {got} riadkov, ale očakáva sa {expected}.",
        "fb.type_differs": "Výstup má iný typ: dostali sme {got}, očakáva sa {expected}.",
        "fb.numbers_count": "Vo výstupe je {got} čísel, ale očakáva sa {expected}.",
        "fb.numbers_value": "Text výstupu sedí, ale {wrong} z {total} čísel sa nezhoduje.",
        "fb.text_differs": "Výstup sa obsahovo líši od očakávaného. Over, čo presne má program vypísať.",
        "fb.fix_alone": "Oprav kód sám a odošli ho znova.",

        # --- vysvetlenia chýb Pythonu ---
        "err.SyntaxError": "Kód má syntaktickú chybu - skontroluj dvojbodky, zátvorky a úvodzovky.",
        "err.IndentationError": "Zle odsadený kód - bloky (za dvojbodkou) musia byť odsadené rovnako.",
        "err.TabError": "Miešaš tabulátory a medzery pri odsadzovaní.",
        "err.NameError": "Používaš názov, ktorý Python nepozná - preklep alebo premenná ešte nebola vytvorená.",
        "err.TypeError": "Operácia sa použila na nesprávny typ hodnoty (napr. text + číslo).",
        "err.ValueError": "Hodnota má správny typ, ale nevhodný obsah pre danú operáciu.",
        "err.IndexError": "Pristupuješ k indexu, ktorý v zozname neexistuje.",
        "err.KeyError": "Kľúč, ktorý hľadáš, v slovníku neexistuje.",
        "err.AttributeError": "Objekt nemá vlastnosť alebo metódu, ktorú voláš.",
        "err.ZeroDivisionError": "Delíš nulou.",
        "err.ModuleNotFoundError": "Importuješ modul, ktorý nie je dostupný.",
        "err.ImportError": "Import sa nepodaril.",
        "err.RecursionError": "Rekurzia sa nikdy neukončí - chýba základný prípad.",
        "err.TimeoutError": "Kód bežal príliš dlho - možno nekonečný cyklus.",
        "err.generic": "Oprav chybu a skús to znova.",

        # --- odmietnuté odoslanie (nezapočíta sa ako pokus) ---
        "reject.empty": "Nezadal si žiadny kód. Skús niečo napísať a odoslať odpoveď.",
        "reject.duplicate": "Odoslal si rovnaký kód ako minule. Najprv ho uprav podľa spätnej väzby.",
        "void": "V tejto úlohe je chyba v zadaní, nie v tvojom riešení. Nezapočíta sa ti - dostaneš novú úlohu.",
        "no_tasks": "Žiadne ďalšie úlohy.",

        # --- agent ---
        "agent.greeting": "Ahoj, som AdaptPy asistent. Vidím, že ti to ide ťažšie. Riešenie ti neprezradím, "
                          "ale môžem vysvetliť, čo je v tvojom výstupe zlé, alebo ti dať nápovedu.",
        "agent.no_attempt": "Ešte si neodoslal žiadny pokus, nie je čo vysvetľovať.",
        "agent.explain_hint": "Ak chceš ďalší krok, požiadaj o nápovedu.",
        "agent.hint_prefix": "Nápoveda {n}/{max}:",
        "agent.no_more_hints": "Ďalšie nápovedy už nemám. Skús to ešte raz opraviť sám - každý pokus ťa posúva bližšie.",
        "agent.closed": "Táto úloha je už uzavretá, agent nie je dostupný.",
        "agent.hint1_extra_no_output": "Skontroluj, či program niečo vypisuje.",
        "agent.hint2_missing": "Správne riešenie využíva: {missing}. V tvojom kóde to chýba.",
        "agent.hint2_nothing_missing": "Tvoj kód používa podobné konštrukcie ako správne riešenie. Chyba bude skôr "
                                       "v detailoch: začiatočné hodnoty, hranice cyklu, poradie operácií alebo formát výpisu.",
        "agent.hint3": "Takto vyzerá kostra správneho riešenia (obsah riadkov je skrytý):",
        "agent.hint3_unavailable": "Skús si na papieri krok po kroku prejsť, čo má program robiť pre vstup zo zadania, "
                                   "a porovnaj to s tým, čo robí tvoj kód.",
        "cons.for": "cyklus for", "cons.while": "cyklus while", "cons.if": "podmienku if",
        "cons.def": "definíciu funkcie (def)", "cons.return": "príkaz return",
        "cons.comp": "zápis typu comprehension", "cons.lambda": "funkciu lambda",
        "cons.try": "ošetrenie výnimiek (try)", "cons.class": "triedu (class)",
        "cons.import": "import modulu", "cons.print": "výpis cez print()",
        "cat.Data Structures": "Zamysli sa, aká dátová štruktúra (list, tuple, dict, set) je vo vstupe a ako sa "
                               "k jej prvkom pristupuje alebo ako sa dopĺňa.",
        "cat.Syntax": "Skontroluj základy: priradenia, operátory, odsadenie a to, čo presne vypisuje print().",
        "cat.Sorting": "Rozmysli si, podľa čoho sa má triediť, v akom poradí (vzostupne/zostupne) a či sa má "
                       "zmeniť pôvodný zoznam alebo vzniknúť nový.",
        "cat.Scientific Computing": "Rozlož výpočet na kroky a over každý medzivýsledok; pozor na typy čísel a zaokrúhľovanie.",
        "cat.generic": "Rozlož zadanie na menšie kroky a každý si over vlastným výpisom.",
    },
    "en": {
        "fb.error": "The code ended with an error: {error}",
        "fb.no_output": "The program printed nothing. Check that you print the result with print().",
        "fb.line_count": "The output has {got} lines, but {expected} are expected.",
        "fb.type_differs": "The output has a different type: we got {got}, expected {expected}.",
        "fb.numbers_count": "The output contains {got} numbers, but {expected} are expected.",
        "fb.numbers_value": "The text matches, but {wrong} of {total} numbers differ.",
        "fb.text_differs": "The output differs in content from what is expected. Check what exactly the program should print.",
        "fb.fix_alone": "Fix the code yourself and submit it again.",

        "err.SyntaxError": "The code has a syntax error - check colons, brackets and quotes.",
        "err.IndentationError": "Wrong indentation - blocks (after a colon) must be indented consistently.",
        "err.TabError": "You are mixing tabs and spaces for indentation.",
        "err.NameError": "You use a name Python does not know - a typo, or the variable was not created yet.",
        "err.TypeError": "An operation was applied to a value of the wrong type (e.g. text + number).",
        "err.ValueError": "The value has the right type but unsuitable content for this operation.",
        "err.IndexError": "You access an index that does not exist in the list.",
        "err.KeyError": "The key you look for does not exist in the dictionary.",
        "err.AttributeError": "The object has no such attribute or method.",
        "err.ZeroDivisionError": "You are dividing by zero.",
        "err.ModuleNotFoundError": "You import a module that is not available.",
        "err.ImportError": "The import failed.",
        "err.RecursionError": "The recursion never ends - the base case is missing.",
        "err.TimeoutError": "The code ran for too long - maybe an infinite loop.",
        "err.generic": "Fix the error and try again.",

        "reject.empty": "You did not enter any code. Write something and submit your answer.",
        "reject.duplicate": "You submitted the same code as last time. Change it first, based on the feedback.",
        "void": "This task has a problem in its assignment, not in your solution. It will not count - you get a new task.",
        "no_tasks": "No more tasks.",

        "agent.greeting": "Hi, I'm the AdaptPy assistant. It looks like this one is tricky. I won't give away the "
                          "solution, but I can explain what is wrong with your output or give you a hint.",
        "agent.no_attempt": "You have not submitted any attempt yet, so there is nothing to explain.",
        "agent.explain_hint": "If you want the next step, ask for a hint.",
        "agent.hint_prefix": "Hint {n}/{max}:",
        "agent.no_more_hints": "I have no more hints. Try fixing it once more yourself - every attempt gets you closer.",
        "agent.closed": "This task is already closed, the agent is not available.",
        "agent.hint1_extra_no_output": "Check that the program prints something.",
        "agent.hint2_missing": "The correct solution uses: {missing}. Your code lacks it.",
        "agent.hint2_nothing_missing": "Your code uses similar constructs as the correct solution. The mistake is more likely "
                                       "in the details: initial values, loop bounds, order of operations or output format.",
        "agent.hint3": "This is the skeleton of the correct solution (the content of the lines is hidden):",
        "agent.hint3_unavailable": "Walk through on paper, step by step, what the program should do for the input in the "
                                   "assignment, and compare it with what your code does.",
        "cons.for": "a for loop", "cons.while": "a while loop", "cons.if": "an if condition",
        "cons.def": "a function definition (def)", "cons.return": "a return statement",
        "cons.comp": "a comprehension", "cons.lambda": "a lambda function",
        "cons.try": "exception handling (try)", "cons.class": "a class",
        "cons.import": "a module import", "cons.print": "output via print()",
        "cat.Data Structures": "Think about which data structure (list, tuple, dict, set) is in the input and how its "
                               "elements are accessed or added.",
        "cat.Syntax": "Check the basics: assignments, operators, indentation and exactly what print() outputs.",
        "cat.Sorting": "Decide what to sort by, in which order (ascending/descending) and whether the original list "
                       "should change or a new one be created.",
        "cat.Scientific Computing": "Break the computation into steps and verify each intermediate result; watch number types and rounding.",
        "cat.generic": "Break the task into smaller steps and check each one with your own print.",
    },
}


def tt(lang, key, **kwargs):
    """Text podľa jazyka (záloha: slovenčina, potom samotný kľúč)."""
    table = TEXT.get(lang) or TEXT["sk"]
    text = table.get(key)
    if text is None:
        text = TEXT["sk"].get(key, key)
    return text.format(**kwargs) if kwargs else text


def normalize_lang(lang):
    return lang if lang in TEXT else "sk"
