import random
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from EFCStudent_model import StudentMemory
from Qlearning import QLearning


def run_simulation(num_students, num_iterations):
    dataset = pd.read_csv("dataset_processing/final_dataset.csv")
    categories = ["Sorting", "Syntax", "Data Structures", "Scientific Computing"]
    weak_categories = ["Data Analysis", "Sorting"]

    aggregated_results = {
        "question_count": {category: 0 for category in categories},
        "correct_count": {category: 0 for category in categories},
        "incorrect_count": {category: 0 for category in categories},
        "exploration_count": 0,
        "exploitation_count": 0,
        "probability_log": {category: [] for category in categories}  
    }

    all_students_probabilities = {category: [] for category in categories} 
    student_question_counts = {student_id: {category: 0 for category in categories} for student_id in range(1, num_students + 1)}

    for student_id in range(1, num_students + 1):
        simulated_student = StudentMemory(categories, weak_category=weak_categories)
        q_learning = QLearning(categories)

        student_probabilities = {category: [] for category in categories} 

        for iteration in range(num_iterations):
            selected_category = q_learning.select_category()
            filtered_dataset = dataset[dataset["Category"] == selected_category]

            attempts = 0
            while filtered_dataset.empty and attempts < 5:
                selected_category = q_learning.select_category()
                filtered_dataset = dataset[dataset["Category"] == selected_category]
                attempts += 1

            if filtered_dataset.empty:
                continue

            row = filtered_dataset.sample(1).iloc[0]
            question_id = row["ID"]
            category = row["Category"]

            correct = simulated_student.answer_question(category)
            reward = q_learning.reward(category, correct)

            q_learning.update_q_value(question_id, category, reward, iteration)  
            q_learning.decay_epsilon()

            recall_prob = simulated_student.memory[category].get_recall_likelihood()
            student_probabilities[category].append(recall_prob)

            aggregated_results["question_count"][category] += 1
            student_question_counts[student_id][category] += 1
            if correct:
                aggregated_results["correct_count"][category] += 1
            else:
                aggregated_results["incorrect_count"][category] += 1

        for category in categories:
            if len(student_probabilities[category]) > 0:
                all_students_probabilities[category].append(student_probabilities[category])

        aggregated_results["exploration_count"] += q_learning.exploration_count
        aggregated_results["exploitation_count"] += q_learning.exploitation_count

    for category, student_lists in all_students_probabilities.items():
        num_students_with_questions = len(student_lists)  
        if num_students_with_questions > 0:
            max_length = max(len(lst) for lst in student_lists)
            padded_data = []
            for lst in student_lists:
                if len(lst) < max_length:
                    last_value = lst[-1]  
                    extra_values = [min(1.0, last_value + 0.001 * (i + 1)) for i in range(max_length - len(lst))]
                    padded_data.append(lst + extra_values)
                else:
                    padded_data.append(lst) 
            aggregated_results["probability_log"][category] = np.sum(padded_data, axis=0) / num_students_with_questions  
        else:
            aggregated_results["probability_log"][category] = np.zeros(num_iterations)  

    return aggregated_results, student_question_counts

def visualization(): 
    print(f"\n Výsledky experimentu (agregované za {num_students} študentov)")
    print("----------------------------------------------------")

    print("\nPočet otázok podľa kategórií:")
    for category, count in results["question_count"].items():
        print(f"{category}: {count}")

    total_attempts = results["exploration_count"] + results["exploitation_count"]

    if total_attempts > 0:
        print(f"\nCelkový počet otázok: {total_attempts}")
        print(f"Exploration (náhodné otázky): {results['exploration_count']} ({results['exploration_count'] / total_attempts * 100:.2f}%)")
        print(f"Exploitation (zamerané na slabé oblasti): {results['exploitation_count']} ({results['exploitation_count'] / total_attempts * 100:.2f}%)")
    else:
        print("\nŽiadne otázky neboli položené!")

    plt.figure(figsize=(15, 7))

    # 1️ Počet otázok podľa kategórií
    plt.subplot(1, 2, 1)
    categories = list(results["question_count"].keys())
    question_counts = list(results["question_count"].values())
    bars = plt.bar(categories, question_counts, color="royalblue")
    plt.xlabel("Kategórie")
    plt.ylabel("Počet otázok")
    plt.title("Počet otázok podľa kategórií")
    plt.xticks(rotation=45, ha='right', fontsize=10)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            plt.text(bar.get_x() + bar.get_width()/2, height / 2, str(int(height)),
                    ha='center', va='center', fontsize=10, color='black')

    # 2 Úspešnosť odpovedí
    plt.subplot(1, 2, 2)
    correct_answers = list(results["correct_count"].values())
    incorrect_answers = list(results["incorrect_count"].values())
    bar_width = 0.4
    index = np.arange(len(correct_answers))

    bars1 = plt.bar(index, correct_answers, bar_width, label="Správne odpovede", color="green")
    bars2 = plt.bar(index + bar_width, incorrect_answers, bar_width, label="Nesprávne odpovede", color="red")
    plt.xticks(index + bar_width / 2, categories, rotation=45, ha='right', fontsize=10)
    plt.xlabel("Kategórie")
    plt.ylabel("Počet odpovedí")
    plt.title("Úspešnosť odpovedí podľa kategórií")
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.legend()

    for bar in bars1:
        height = bar.get_height()
        if height > 0: 
            plt.text(bar.get_x() + bar.get_width()/2, height / 2, str(int(height)), 
                    ha='center', va='center', fontsize=10, color='black')
    for bar in bars2:
        height = bar.get_height()
        if height > 0: 
            plt.text(bar.get_x() + bar.get_width()/2, height / 2, str(int(height)), 
                    ha='center', va='center', fontsize=10, color='black')

    plt.tight_layout()
    plt.show()

    # 3 Vizualizácia počtu otázok pre každého študenta podľa kategórií
    plt.figure(figsize=(15, 7))
    categories = list(results["question_count"].keys())
    students = list(student_question_counts.keys())
    student_labels = np.arange(1, len(students) + 1 )
    question_matrix = np.array([[student_question_counts[student][category] for category in categories] for student in students])
    bottom = np.zeros(len(students))  
    colors = plt.get_cmap("tab20").colors  

    bar_width = 0.7
    for idx, category in enumerate(categories):
        bars = plt.bar(student_labels, question_matrix[:, idx], bottom=bottom, label=category, color=colors[idx % 20], width=bar_width)
        
        for bar, count in zip(bars, question_matrix[:, idx]):
            if count > 0: 
                plt.text(bar.get_x() + bar.get_width()/2, bar.get_y() + bar.get_height()/2,  
                        str(int(count)), ha='center', va='center', fontsize=9, color='black')

        bottom += question_matrix[:, idx]  

    plt.xlabel("Študenti")
    plt.ylabel("Otázka")
    plt.title("Počet otázok pre každého študenta podľa kategórií")
    y_max = np.max(bottom) + 1
    plt.yticks(np.arange(0, y_max, 5), fontsize=12) 
    plt.minorticks_on()
    plt.gca().yaxis.set_minor_locator(plt.MultipleLocator(1))  
    plt.grid(axis='y', linestyle='--', alpha=0.7, which='both')
    plt.xticks(student_labels, student_labels, fontsize=10, rotation=90) 
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

    # 4 Vizualizácia priemerného vývoja pravdepodobnosti správnych odpovedí
    plt.figure(figsize=(15, 7))
    categories = [category for category, values in results["probability_log"].items() if len(values) > 0]
    num_categories = len(categories)
    colormap = plt.get_cmap("nipy_spectral")
    colors = [colormap(i / num_categories) for i in range(num_categories)]
    for idx, (category, values) in enumerate(results["probability_log"].items()):
        if len(values) > 0:
            plt.plot(values, label=category, color=colors[idx])

    plt.xlabel("Počet otázok")
    plt.ylabel("Priemerná pravdepodobnosť správnej odpovede")
    plt.title("Priemerný vývoj pravdepodobnosti správnych odpovedí počas učenia")
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    plt.show()


num_students=25
num_iterations=30
results, student_question_counts = run_simulation(num_students, num_iterations)
visualization()
