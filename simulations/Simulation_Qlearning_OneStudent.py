import matplotlib.pyplot as plt
import pandas as pd
from EFCStudent_model import StudentMemory
from Qlearning import QLearning

dataset = pd.read_csv("dataset_processing/final_dataset.csv")
categories = ["Sorting", "Syntax", "Data Structures", "Scientific Computing"]
weak_categories = ["Data Analysis", "Sorting"]
simulated_student = StudentMemory(categories, weak_category=weak_categories)
q_learning = QLearning(categories, weak_categories=weak_categories, q_table_file="q_table_onestudent.json", log_file="question_log_onestudent.csv")

total_questions = 0

for iteration in range(1, 41): 
    selected_category = q_learning.select_category()
    simulated_student.answer_question(selected_category)
    filtered_dataset = dataset[dataset["Category"] == selected_category]
    if filtered_dataset.empty:
        print(f"Žiadne otázky pre kategóriu: {selected_category}")
        continue

    row = filtered_dataset.sample(1).iloc[0]
    question_id = row["ID"]
    category = row["Category"]

    correct = simulated_student.answer_question(category)
    reward = q_learning.reward(category, correct)

    q_learning.update_q_value(question_id, category, reward, iteration)
    q_learning.decay_epsilon()
    total_questions += 1

q_learning.save_q_table()
question_count = q_learning.get_question_count()
categories = list(question_count.keys())
counts = list(question_count.values())


#-------------------------------------------
# Výpis počtu otázok podľa kategórií
print("\nPočet otázok podľa kategórií:")
for category, count in question_count.items():
    print(f"{category}: {count}")

total_attempts = total_questions#q_learning.exploration_count + q_learning.exploitation_count
print(f"Celkový počet otázok: {total_attempts}")
print(f"Exploration (náhodné otázky): {q_learning.exploration_count} ({q_learning.exploration_count / total_attempts * 100:.2f}%)")
print(f"Exploitation (zamerané na slabé oblasti): {q_learning.exploitation_count} ({q_learning.exploitation_count / total_attempts * 100:.2f}%)")    

#---------------------------------------
q_table = q_learning.get_q_table()
categories = list(q_table.keys())
q_values = list(q_table.values())
plt.figure(figsize=(8, 7))  
plt.bar(categories, q_values)
plt.xlabel('Kategórie', fontsize=12)
plt.ylabel('Q-hodnota', fontsize=12)
plt.title('Výsledky Q-learningu podľa kategórií', fontsize=14)
plt.xticks(rotation=45, ha='right', fontsize=10)
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.tight_layout()
plt.show()
#---------------------------------------

# Vizualizácia počtu otázok podľa kategórií
plt.figure(figsize=(12, 6))
categories = list(question_count.keys())
question_counts = list(question_count.values())

# Vytvorenie stĺpcového grafu
bars = plt.bar(categories, question_counts, color="royalblue")

# Pridanie textových hodnôt do stĺpcov
for bar in bars:
    height = bar.get_height()
    if height > 0:
        plt.text(bar.get_x() + bar.get_width()/2, height / 2, str(int(height)), 
                 ha='center', va='center', fontsize=10, color='black')

# Nastavenia grafu
plt.xlabel("Kategórie")
plt.ylabel("Počet otázok")
plt.title("Počet otázok pre jedného študenta podľa kategórií")
plt.xticks(rotation=45, ha='right', fontsize=10)
plt.grid(axis='y', linestyle='--', alpha=0.7)

plt.tight_layout()
plt.show()

simulated_student.plot_probabilities()