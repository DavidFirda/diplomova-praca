import pandas as pd
import io
import contextlib
import builtins

def capture_output(source_code):
    buffer = io.StringIO()
    try:
        # Zakážeme input(), aby nespôsobil zaseknutie
        safe_builtins = dict(builtins.__dict__)
        safe_builtins['input'] = lambda *args, **kwargs: (_ for _ in ()).throw(Exception("input() is disabled"))

        with contextlib.redirect_stdout(buffer):
            exec(source_code, {"__builtins__": safe_builtins}, {})
        return buffer.getvalue().strip(), None
    except Exception as e:
        return "", str(e)

if __name__ == "__main__":
    # Načítaj dataset
    df1 = pd.read_csv("final_dataset.csv")
    ids_to_remove = [1300, 5157, 7138, 7958, 8301] 
    df = df1[~df1['ID'].isin(ids_to_remove)]

    # Zoznamy na triedenie
    runnable_with_output = []
    runnable_no_output = []
    not_runnable = []

    # Prejdi celý dataset
    for idx, row in df.iterrows():
        question_id = row['ID']
        print(f"🔍 Testujem otázku ID: {question_id}")
        code = row['Output'] # uisti sa, že je to string
        output, error = capture_output(code)

        if error:
            not_runnable.append(row)
        elif output:
            runnable_with_output.append(row)
        else:
            runnable_no_output.append(row)

    # Ulož výsledky
    pd.DataFrame(runnable_with_output).to_csv("runnable_with_output.csv", index=False)
    pd.DataFrame(runnable_no_output).to_csv("runnable_no_output.csv", index=False)
    pd.DataFrame(not_runnable).to_csv("not_runnable.csv", index=False)

    print("✅ Triedenie dokončené:")
    print("- runnable_with_output.csv")
    print("- runnable_no_output.csv")
    print("- not_runnable.csv\n")

        # Spočítaj počet otázok podľa kategórie v každom datasete
    print("📊 Počet otázok podľa kategórie:")

    print("\n✅ runnable_with_output:")
    print(pd.DataFrame(runnable_with_output)['Category'].value_counts())

    print("\n🔹 runnable_no_output:")
    print(pd.DataFrame(runnable_no_output)['Category'].value_counts())

    print("\n❌ not_runnable:")
    print(pd.DataFrame(not_runnable)['Category'].value_counts())