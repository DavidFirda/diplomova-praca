import pandas as pd
import random
import os

RANDOM_SEED = 30
random.seed(RANDOM_SEED)

dataset = pd.read_csv("filtered_data.csv")

def generate_incorrect_output(correct_output, subcategory):
    incorrect_variants = []

    # Definovanie chýb pre rôzne podkategórie
    if subcategory in ["if", "elif", "switch", "case", "decision", "condition"]:
        incorrect_variants.extend([
            lambda x: x.replace("if ", "iff "),
            lambda x: x.replace("elif ", "else if "),
            lambda x: x.replace(":", ""),
            lambda x: x.replace("else", "ellse"),
            lambda x: x.replace("if ", "if False:")
        ])

    if subcategory in ["loop", "for loop", "while", "nested loop", "break", "continue", "array"]:
        incorrect_variants.extend([
            lambda x: x.replace("for ", "fr "),
            lambda x: x.replace("range(", "rang("),
            lambda x: x.replace("while ", "while True:"),
            lambda x: x.replace("break", "breakit "),
            lambda x: x.replace("continue", "cntinue"),
            lambda x: x.replace("for i in range", "for j in range")
        ])

    if subcategory in ["sort", "sorting", "quick sort"]:
        incorrect_variants.extend([
            lambda x: x.replace("sorted", "srted"),
            lambda x: x.replace("reverse", "revers"),
            lambda x: x.replace("key=", "ky="),
            lambda x: x.replace("sorted(", "reversed("),
            lambda x: x.replace("list.sort(", "list.srt("),
            lambda x: x.replace("sort(", "sorted(")
        ])

    if subcategory in ["file", "read", "open", "close", "csv", "xml"]:
        incorrect_variants.extend([
            lambda x: x.replace("open(", "opn("),
            lambda x: x.replace("close()", "# no close statement"),
            lambda x: x.replace(".read", ".red"),
            lambda x: x.replace(".write", "# no write statement"),
            lambda x: x.replace("with open", "opn file"),
            lambda x: x.replace("file.read(", "file.reaad(")
        ])

    if subcategory in ["numpy", "dataframe", "analysis", "plot", "matplotlib", "visualization", "statistics", "histogram", "distribution"]:
        incorrect_variants.extend([
            lambda x: x.replace("import numpy", "import numy"),
            lambda x: x.replace(".mean(", ".mn("),
            lambda x: x.replace(".plot(", ".plt("),
            lambda x: x.replace("axis=", "axix="),
            lambda x: x.replace(".sum(", ".summ("),
            lambda x: x.replace("pandas.DataFrame", "pandas.Data")
        ])

    if subcategory in ["sum", "multiply", "prime", "mean", "median", "number", "calculator", "variable", "calculate"]:
        incorrect_variants.extend([
            lambda x: x.replace("+", "-"),
            lambda x: x.replace("-", "+"),
            lambda x: x.replace("*", "/"),
            lambda x: x.replace("is_prime", "isprime"),
            lambda x: x.replace("return", "return x ** 3"),
            lambda x: x.replace("math.sqrt", "math.srt"),
            lambda x: x.replace("abs(", "absolute(")
        ])

    if subcategory in ["print", "variable", "data type", "boolean", "set", "duplicate", "date"]:
        incorrect_variants.extend([
            lambda x: x.replace("print", "prit"),
            lambda x: x.replace("True", "true"),
            lambda x: x.replace("False", "false"),
            lambda x: x.replace("=", "=="),
            lambda x: x.replace("int(", "integer("),
            lambda x: x.replace("len(", "length(")
        ])

    if subcategory in ["parameter", "lambda", "generator", "decorator"]:
        incorrect_variants.extend([
            lambda x: x.replace("def ", "define "),
            lambda x: x.replace("lambda", "lmbda"),
            lambda x: x.replace("args", "arg"),
            lambda x: x.replace("kwargs", "kwarg")
        ])

    if subcategory in ["list", "dictionary", "tree", "stack", "queue", "linked list"]:
        incorrect_variants.extend([
            lambda x: x.replace("**", "*"),
            lambda x: x.replace(".sort(", ".srt("),
            lambda x: x.replace("[", "("),
            lambda x: x.replace("{", "["),
            lambda x: x.replace(".append(", ".apend("),
            lambda x: x.replace(".pop(", ".pp("),
            lambda x: x.replace("list(", "lst("),
            lambda x: x.replace("dict(", "dictionary(")
        ])

    if subcategory in ["fibonacci", "optimization", "knapsack"]:
        incorrect_variants.extend([
            lambda x: x.replace("return", "retun"),
            lambda x: x.replace("for", "foor"),
            lambda x: x.replace("[i]", "[i+1]"),
            lambda x: x.replace("recursion", "recusrion"),
            lambda x: x.replace("dp", "dynamicprogram"),
            lambda x: x.replace("memoization", "memoiztion")
        ])

    if subcategory in ["error", "exception", "try", "debug"]:
        incorrect_variants.extend([
            lambda x: x.replace("try", "tyr"),
            lambda x: x.replace("except", "excep"),
            lambda x: x.replace("raise", "rase"),
            lambda x: x.replace("assert", "assrt"),
            lambda x: x.replace("finally", "fnally")
        ])

    if ":" in correct_output:
        incorrect_variants.append(lambda x: x.replace(":", ""))

    if "def " in correct_output:
        incorrect_variants.append(lambda x: x.replace("def ", "define "))

    if "return" in correct_output:
        incorrect_variants.append(lambda x: x.replace("return", "retrn"))

    if not incorrect_variants:
        return "# No meaningful incorrect variant could be generated."


    selected_changes = random.sample(incorrect_variants, min(2, len(incorrect_variants)))
    incorrect_output = correct_output
    for change in selected_changes:
        incorrect_output = change(incorrect_output)

    return incorrect_output

dataset["IncorrectOutput"] = dataset.apply(
    lambda row: generate_incorrect_output(row["Output"], row["Subcategory"]) if pd.notna(row["Output"]) else None,
    axis=1
)

if os.path.exists("dataset_with_incorrect_answers.csv"):
    os.remove("dataset_with_incorrect_answers.csv")
    print("Starý súbor 'dataset_with_incorrect_answers.csv' bol odstránený.")
output_file = "dataset_with_incorrect_answers.csv"
dataset.to_csv(output_file, index=False)
print(f"Dataset s chybnými odpoveďami bol uložený do súboru: {output_file}")

