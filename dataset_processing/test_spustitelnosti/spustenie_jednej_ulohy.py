"""
import pandas as pd

# Funkcia na zachytenie výstupu alebo chyby
def capture_output(source_code):
    import io
    import contextlib
    import builtins
    import random
    import numpy as np
    RANDOM_STATE = 82

    buffer = io.StringIO()
    try:
        # 🔐 Uisti sa, že random je deterministický
        random.seed(RANDOM_STATE)
        np.random.seed(RANDOM_STATE)

        with contextlib.redirect_stdout(buffer):
            exec(source_code, {"__builtins__": builtins.__dict__, "random": random, "np": np}, {})
        return buffer.getvalue().strip(), None
    except Exception as e:
        return "", str(e)
# Načítanie dát
df = pd.read_csv("final_dataset.csv")

# Predpokladáme, že otázky sú v stĺpci 'output'
first_question_output = df.iloc[186]['Output']

# Otestovanie výstupu
expected_output, expected_error = capture_output(first_question_output)

# Výpis výsledku
if expected_error:
    print("Výstup nie je správny. Skús to ešte raz opraviť:")
    print("Chyba:", expected_error)
else:
    print("✅ Výstup bol úspešne spustený:")
    print(expected_output)

"""

import io, contextlib
import builtins
import random
import numpy as np
import pandas as pd
import re

RANDOM_STATE = 82

def capture_output(source_code):
    # Odstráni problematické importy
    source_code = "\n".join([
        line for line in source_code.splitlines()
        if not re.match(r"^\s*(import random|from random import|import numpy|from numpy import)", line)
    ])

    buffer = io.StringIO()
    try:
        rnd = random.Random(RANDOM_STATE)
        np_rng = np.random.RandomState(RANDOM_STATE)

        local_env = {
            "__builtins__": builtins.__dict__,
            "random": rnd,
            "np": np_rng
        }

        with contextlib.redirect_stdout(buffer):
            exec(source_code, local_env)

        # Extrahujeme meno poslednej funkcie
        func_match = re.findall(r'def\s+(\w+)\s*\(', source_code)
        if func_match:
            last_func = func_match[-1]

            # Skúsime nájsť, či sa táto funkcia volala vo výpise
            called_match = re.search(rf'print\s*\(\s*{last_func}\s*\((.*?)\)\s*\)', source_code)
            if called_match:
                args_str = called_match.group(1)
                try:
                    # Evaluujeme argumenty z volania (ak neobsahujú nebezpečné veci)
                    args = eval(f"[{args_str}]")
                    result = local_env[last_func](*args)
                    return str(result), None
                except Exception:
                    pass  # fallback na stdout

        # Ak nie je funkcia volaná alebo nie je žiadna funkcia, zober stdout
        return buffer.getvalue().strip(), None

    except Exception as e:
        return "", str(e)
    
# Načítanie dát
df = pd.read_csv("final_dataset.csv")

# Predpokladáme, že otázky sú v stĺpci 'output'
first_question_output = df.iloc[143]['Output']

# Otestovanie výstupu
expected_output, expected_error = capture_output(first_question_output)

# Výpis výsledku
if expected_error:
    print("Výstup nie je správny. Skús to ešte raz opraviť:")
    print("Chyba:", expected_error)
else:
    print("✅ Výstup bol úspešne spustený:")
    print(expected_output)    