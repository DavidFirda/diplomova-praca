import pandas as pd
import os
import string

dataset = pd.read_csv("Python Programming Questions Dataset.csv") 

dataset = dataset.drop(dataset[(dataset['Instruction'].isnull()) | (dataset['Instruction'].str.strip() == "")].index)
dataset = dataset.drop(dataset[(dataset['Output'].isnull()) | (dataset['Output'].str.strip() == "")].index)

def categorize_questions(dataset, categories):

    def to_singular(word):
        if word.lower() == "class":
            return word
        elif word.endswith("ies"):
            return word[:-3] + "y"  # "categories" -> "category"
        elif word.endswith("es"):
            return word[:-1]  #  "variables" -> "variable"
        elif word.endswith("es"):
            return word[:-2]  #  "boxes" -> "box"
        elif word.endswith("s") and len(word) > 1:
            return word[:-1]  #  "lists" -> "list"
        return word 
    
    def clean_text(text):
        text = text.replace('"', '').replace("'", "")  
        text = text.strip(string.punctuation)  
        return text

    def determine_category(instruction):
        instruction = clean_text(instruction)
        words = [word.rstrip(string.punctuation) for word in instruction.lower().split()]
        
        words = [to_singular(word) for word in words]

        for i in range(len(words)):
            for j in range(i + 1, len(words) + 1):
                phrase = " ".join(words[i:j])
                for category, keywords in categories.items():
                    if phrase in keywords:
                        return category, phrase  
        return "Uncategorized", None  
    
    dataset[['Category', 'Subcategory']] = dataset['Instruction'].apply(lambda x: pd.Series(determine_category(x)))
    return dataset

def categorize_uncategorized_by_output(dataset, categories):
    subcategory_counts = dataset['Subcategory'].value_counts() #nevracia nulove
    all_subcategories = [subcategory for keywords in categories.values() for subcategory in keywords]

    # Zahrnutie podkategórií s jednou alebo žiadnou otázkou
    underutilized_subcategories = [
        subcategory for subcategory in all_subcategories 
        if subcategory not in subcategory_counts.index or subcategory_counts.get(subcategory, 0) <= 1
    ]

    uncategorized_records = dataset[dataset['Category'] == "Uncategorized"]

    def determine_category_from_output(output):
        if not isinstance(output, str) or not output.strip():
            return "Uncategorized", None
        words = output.lower().split()
        for i in range(len(words)):
            for j in range(i + 1, len(words) + 1):
                phrase = " ".join(words[i:j])
                for category, keywords in categories.items():
                    if phrase in keywords and phrase in underutilized_subcategories:
                        print(f"Zhodná fráza: {phrase} -> Kategória: {category}")
                        return category, phrase  
        return "Uncategorized", None  
    
    # Prechádzanie 'Uncategorized' záznamov a priraďovanie kategórií
    uncategorized_records[['Category', 'Subcategory']] = uncategorized_records['Output'].apply(
        lambda x: pd.Series(determine_category_from_output(x))
    )

    dataset.update(uncategorized_records)
    return dataset

categories = {
    "Branching": ["if", "elif", "switch", "case", "decision", "condition"], 
    "Loops": ["loop", "while", "do while", "nested loop", "break", "continue", "for loop", "for each"],
    "Sorting": ["sort", "sorting", "quick sort"],
    "File Handling": ["file", "read", "open", "close", "csv", "xml"],
    "Data Analysis": ["numpy", "dataframe", "analysis", "plot", "matplotlib", "visualization", "statistics", "histogram", "distribution", 
                      "min", "max", "ptp", "std", "axis"],
    "Mathematics": ["prime", "average", "sum", "multiply", "number", "calculate", "mean", "median", "algebra", "volume", "pi"],
    # Prednáška 1: Syntax a základné koncepty
    "Syntax": ["print", "user input", "variable", "data type", "integer", "float", "boolean", "operator", "set", "duplicate", "date"],
    # Prednáška 2: Funkcie a pokročilé koncepty
    "Functions and Advanced Concepts": ["parameter", "lambda", "generator", "decorator"],
    # Prednáška 3: Údajové štruktúry
    "Data Structures": ["string", "list", "tuple", "dictionary", "tree", "stack", "queue", "linked list", "hash table", "data structure"],
    # Prednáška 4: Testovanie a ladenie
    "Testing and Debugging": ["error", "exception", "try", "catch", "try/except", "unit test", "validation", "assertion", "debug"],
    # Prednáška 5: Algoritmy a dynamické programovanie
    "Algorithms and Dynamic Programming": ["fibonacci", "knapsack", "euclidean algorithm", "memoization", "optimization", "classifies", "quicksort algorithm"],
    # Prednáška 6 a 7: Objektovo orientované programovanie
    "Object-Oriented Programming": ["class", "object", "constructor"],
    # Prednáška 10: Vedecké výpočty
    "Scientific Computing": ["pandas", "matrix", "array", "statistic", "temperature", "calculator", "random"]
}


categorized_dataset1 = categorize_questions(dataset, categories)
categorized_dataset = categorize_uncategorized_by_output(categorized_dataset1, categories)


print("Príklad kategorizovaných otázok:")
print(categorized_dataset1[['Instruction', 'Category', 'Subcategory']].head())
print("-" * 50)

print("Nové kategorizované záznamy:")
print(categorized_dataset[categorized_dataset['Category'] != "Uncategorized"].head())
print("-" * 50)

#------------------------------------------------------------------

category_counts = categorized_dataset['Category'].value_counts()

print("Počet otázok v jednotlivých kategóriách:")
for category, count in category_counts.items():
    print(f"{category}: {count} otázok")
print("-" * 50)

# Spočítanie otázok v jednotlivých podkategoriach
subcategory_counts = categorized_dataset['Subcategory'].value_counts()
subcategories_mapping = {subcategory: category for category, subcategories in categories.items() for subcategory in subcategories}
subcategories_with_zero_count = [subcategory for subcategory in subcategories_mapping.keys() if subcategory not in subcategory_counts.index]

print("Počet otázok v jednotlivých kategóriách:")
for subcategory, count in subcategory_counts.items():
    print(f"{subcategory}: {count} otázok")

print("-" * 50)
print("Podkategórie bez otázok (počet = 0):")
for subcategory in subcategories_with_zero_count:
    print(subcategory)

print("-" * 50)

#-----------------------------------

categorized_records = categorized_dataset[categorized_dataset['Category'] != "Uncategorized"]
if os.path.exists("categorized_records.csv"):
    os.remove("categorized_records.csv")
    print("Starý súbor 'categorized_records.csv' bol odstránený.")
output_file = "categorized_records.csv"
categorized_records.to_csv(output_file, index=False)
print(f"Kategorizovaný dataset bol uložený do súboru: {output_file}")
print("-" * 50)


#--------------------------------------------------

uncategorized_records = categorized_dataset[categorized_dataset['Category'] == "Uncategorized"]
if os.path.exists("uncategorized_records.csv"):
    os.remove("uncategorized_records.csv")
    print("Starý súbor 'uncategorized_records.csv' bol odstránený.")
uncategorized_output_file = "uncategorized_records.csv"
uncategorized_records.to_csv(uncategorized_output_file, index=False)
print(f"Záznamy s kategóriou 'Uncategorized' boli uložené do súboru: {uncategorized_output_file}")
print("-" * 50)
