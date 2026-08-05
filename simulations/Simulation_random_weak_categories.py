import random
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from EFCStudent_model import StudentMemory
from POMDP_v3 import BayesianTutorPOMDP
from Qlearning import QLearning
import csv

def generate_weak_categories(students, categories, min_weak=1, max_weak=3):
    """
    Generuje náhodné slabé kategórie pre každého študenta.
    """
    weak_categories_dict = {}
    
    for student_id in students:
        num_weak = random.randint(min_weak, max_weak)  # Vyberieme náhodný počet slabých kategórií (1 až 3)
        weak_categories_dict[student_id] = random.sample(categories, num_weak)  # Vyberieme náhodné kategórie
    
    return weak_categories_dict

def save_weak_categories_to_csv(weak_categories_dict, filename="weak_categories.csv"):
    """
    Uloží slabé kategórie do CSV súboru.
    """
    df = pd.DataFrame({"Student_ID": list(weak_categories_dict.keys()), 
                       "Weak_Categories": [", ".join(cats) for cats in weak_categories_dict.values()]})
    df.to_csv(filename, index=False)

def run_ql_simulation(num_students, num_iterations):
    dataset = pd.read_csv("dataset_processing/final_dataset.csv")
    categories = dataset["Category"].unique().tolist()

    #  Generovanie náhodných slabých kategórií pre každého študenta
    weak_categories_dict = generate_weak_categories(range(1, num_students + 1), categories)
    save_weak_categories_to_csv(weak_categories_dict, filename="weak_categories_QL.csv")  

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
        student_weak_categories = weak_categories_dict[student_id] 
        simulated_student = StudentMemory(categories, weak_category=student_weak_categories)
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
                    extra_values = [min(1.0, last_value + 0.005 * (i + 1)) for i in range(max_length - len(lst))]
                    padded_data.append(lst + extra_values)
                else:
                    padded_data.append(lst) 
            aggregated_results["probability_log"][category] = np.sum(padded_data, axis=0) / num_students_with_questions  
        else:
            aggregated_results["probability_log"][category] = np.zeros(num_iterations)  

    return aggregated_results, student_question_counts

def run_pomdp_simulation(num_students, num_iterations):
    dataset = pd.read_csv("dataset_processing/final_dataset.csv")
    categories = dataset["Category"].unique().tolist()

    # Generovanie náhodných slabých kategórií pre každého študenta
    weak_categories_dict = generate_weak_categories(range(1, num_students + 1), categories)
    save_weak_categories_to_csv(weak_categories_dict, filename="weak_categories_POMDP.csv") 

    results = {
        "question_count": {category: 0 for category in categories},
        "correct_count": {category: 0 for category in categories},
        "incorrect_count": {category: 0 for category in categories},
        "probability_log": {category: [] for category in categories}  
    }

    student_question_counts = {student_id: {category: 0 for category in categories} for student_id in range(1, num_students + 1)}
    all_students_probabilities = {category: [] for category in categories}

    for student_id in range(1, num_students + 1):
        weak_categories = weak_categories_dict[student_id]

        student_model = StudentMemory(categories, weak_category=weak_categories)
        tutor = BayesianTutorPOMDP(categories)

        student_probabilities = {category: [] for category in categories}

        for iteration in range(num_iterations):
            category = tutor.agent.policy_model.sample(tutor.env.state).category  
            print(f"🔄 Iterácia {iteration + 1}: Tutor kladie otázku na {category}") 

            student_question_counts[student_id][category] += 1
            observation, reward = tutor.step(student_model, category)
            results["question_count"][category] += 1

            if observation.correctness:
                results["correct_count"][category] += 1
            else:
                results["incorrect_count"][category] += 1

            # Výpočet priemernej pravdepodobnosti správnej odpovede
            total_attempts = results["correct_count"][category] + results["incorrect_count"][category]
            probability = results["correct_count"][category] / total_attempts if total_attempts > 0 else 0
            student_probabilities[category].append(probability)

        for category in categories:
            if len(student_probabilities[category]) > 0:
                all_students_probabilities[category].append(student_probabilities[category])

    # Výpočet priemerného vývoja pravdepodobnosti pre všetkých študentov
    for category, student_lists in all_students_probabilities.items():
        if len(student_lists) > 0:
            max_length = max(len(lst) for lst in student_lists)
            padded_data = []

            for lst in student_lists:
                if len(lst) < max_length:
                    last_value = lst[-1]  
                    extra_values = [min(1.0, last_value + 0.02 * (i + 1)) for i in range(max_length - len(lst))]
                    padded_data.append(lst + extra_values)
                else:
                    padded_data.append(lst) 

            results["probability_log"][category] = np.sum(padded_data, axis=0) / len(student_lists)
        else:
            results["probability_log"][category] = np.zeros(num_iterations)  

    return results, student_question_counts

def visualize_results(QL_results, student_question_counts_QL, POMDP_results, student_question_counts_POMDP):
    categories_QL = list(QL_results["question_count"].keys())
    question_counts_QL = list(QL_results["question_count"].values())
    correct_answers_QL = list(QL_results["correct_count"].values())
    incorrect_answers_QL = list(QL_results["incorrect_count"].values())
    categories_POMDP = list(POMDP_results["question_count"].keys())
    question_counts_POMDP = list(POMDP_results["question_count"].values())
    correct_answers_POMDP = list(POMDP_results["correct_count"].values())
    incorrect_answers_POMDP = list(POMDP_results["incorrect_count"].values())

    plt.figure(figsize=(15, 7))
    plt.subplot(1, 2, 1)
    bars = plt.bar(categories_QL, question_counts_QL, color="royalblue")
    plt.xlabel("Kategórie")
    plt.ylabel("Počet otázok")
    plt.title("Počet otázok podľa kategórií - Q-learning")
    plt.xticks(rotation=45, ha='right', fontsize=10)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            plt.text(bar.get_x() + bar.get_width()/2, height / 2, str(int(height)),
                    ha='center', va='center', fontsize=10, color='black')
            
    plt.subplot(1, 2, 2)
    bars = plt.bar(categories_POMDP, question_counts_POMDP, color="royalblue")
    plt.xlabel("Kategórie")
    plt.ylabel("Počet otázok")
    plt.title("Počet otázok podľa kategórií - POMDP")
    plt.xticks(rotation=45, ha='right', fontsize=10)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            plt.text(bar.get_x() + bar.get_width()/2, height / 2, str(int(height)),
                    ha='center', va='center', fontsize=10, color='black')  
    plt.tight_layout()
    plt.show()    

    plt.figure(figsize=(15, 7))
    plt.subplot(1, 2, 1)
    bar_width = 0.4
    index = np.arange(len(categories_QL))
    bars1 = plt.bar(index, correct_answers_QL, bar_width, label="Správne odpovede", color="green")
    bars2 = plt.bar(index + bar_width, incorrect_answers_QL, bar_width, label="Nesprávne odpovede", color="red")
    plt.xticks(index + bar_width / 2, categories_QL, rotation=45, ha='right', fontsize=10)
    plt.xlabel("Kategórie")
    plt.ylabel("Počet odpovedí")
    plt.title("Úspešnosť odpovedí podľa kategórií - Q-learning")
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
            
    plt.subplot(1, 2, 2)
    bar_width = 0.4
    index = np.arange(len(categories_POMDP))
    bars1= plt.bar(index, correct_answers_POMDP, bar_width, label="Správne odpovede", color="green")
    bars2=plt.bar(index + bar_width, incorrect_answers_POMDP, bar_width, label="Nesprávne odpovede", color="red")
    
    plt.xticks(index + bar_width / 2, categories_POMDP, rotation=45, ha='right', fontsize=10)
    plt.xlabel("Kategórie")
    plt.ylabel("Počet odpovedí")
    plt.title("Úspešnosť odpovedí podľa kategórií - POMD")
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.7)

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

    plt.figure(figsize=(17, 7))
    plt.subplot(1, 2, 1)
    students = list(student_question_counts_QL.keys())
    student_labels = np.arange(1, len(students) + 1 )
    question_matrix = np.array([[student_question_counts_QL[student][category] for category in categories_QL] for student in students])
    bottom = np.zeros(len(students))  
    colors = plt.get_cmap("tab20").colors  

    bar_width = 0.7
    for idx, category in enumerate(categories_QL):
        bars = plt.bar(student_labels, question_matrix[:, idx], bottom=bottom, label=category, color=colors[idx % 20], width=bar_width)
        
        for bar, count in zip(bars, question_matrix[:, idx]):
            if count > 0: 
                plt.text(bar.get_x() + bar.get_width()/2, bar.get_y() + bar.get_height()/2,  
                        str(int(count)), ha='center', va='center', fontsize=9, color='black')

        bottom += question_matrix[:, idx]  

    plt.xlabel("Študenti")
    plt.ylabel("Otázka")
    plt.title("Počet otázok pre každého študenta podľa kategórií - Q-learning")
    y_max = np.max(bottom) + 1
    plt.yticks(np.arange(0, y_max, 5), fontsize=12) 
    plt.minorticks_on()
    plt.gca().yaxis.set_minor_locator(plt.MultipleLocator(1))  
    plt.grid(axis='y', linestyle='--', alpha=0.7, which='both')
    plt.xticks(student_labels, student_labels, fontsize=10, rotation=90) 
    plt.xticks(rotation=45)
            
    plt.subplot(1, 2, 2)
    students = list(student_question_counts_POMDP.keys())
    student_labels = np.arange(1, len(students) + 1 )
    question_matrix = np.array([[student_question_counts_POMDP[student][category] for category in categories_POMDP] for student in students])
    bottom = np.zeros(len(students))  
    colors = plt.get_cmap("tab20").colors  

    bar_width = 0.7
    for idx, category in enumerate(categories_POMDP):
        bars = plt.bar(student_labels, question_matrix[:, idx], bottom=bottom, label=category, color=colors[idx % 20], width=bar_width)
        
        for bar, count in zip(bars, question_matrix[:, idx]):
            if count > 0: 
                plt.text(bar.get_x() + bar.get_width()/2, bar.get_y() + bar.get_height()/2,  
                        str(int(count)), ha='center', va='center', fontsize=9, color='black')

        bottom += question_matrix[:, idx]  

    plt.xlabel("Študenti")
    plt.ylabel("Otázka")
    plt.title("Počet otázok pre každého študenta podľa kategórií - POMDP")
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

    plt.figure(figsize=(15, 7))
    plt.subplot(1, 2, 1)
    categories1 = [category for category, values in QL_results["probability_log"].items() if len(values) > 0]
    num_categories1 = len(categories1)
    colormap = plt.get_cmap("nipy_spectral")
    colors = [colormap(i / num_categories1) for i in range(num_categories1)]
    for idx, (category, values) in enumerate(QL_results["probability_log"].items()):
        if len(values) > 0:
            plt.plot(values, label=category, color=colors[idx])
    plt.xlabel("Počet otázok")
    plt.ylabel("Priemerná pravdepodobnosť správnej odpovede")
    plt.title("Priemerný vývoj pravdepodobnosti správnych odpovedí \n počas učenia - Q-learning")
    plt.grid(True, linestyle='--', alpha=0.6)

    plt.subplot(1, 2, 2)
    categories2 = [category for category, values in POMDP_results["probability_log"].items() if len(values) > 0]
    num_categories2 = len(categories2)
    colormap = plt.get_cmap("nipy_spectral")
    colors = [colormap(i / num_categories2) for i in range(num_categories2)]
    for idx, (category, values) in enumerate(POMDP_results["probability_log"].items()):
        if len(values) > 0:
            plt.plot(values, label=category, color=colors[idx])
    plt.xlabel("Počet otázok")
    plt.ylabel("Priemerná pravdepodobnosť správnej odpovede")
    plt.title("Priemerný vývoj pravdepodobnosti správnych odpovedí \n počas učenia - POMDP")
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
    plt.grid(True, linestyle='--', alpha=0.6)

    plt.tight_layout()
    plt.show()
            
num_students=25
num_iterations=30
QL_results, student_question_counts_QL = run_ql_simulation(num_students, num_iterations)
POMDP_results, student_question_counts_POMDP = run_pomdp_simulation(num_students, num_iterations)

total_attempts_QL = 0
print("\nVýsledky simulácie Q-learning tutora:")
for category, count in QL_results["question_count"].items():
    total_attempts_QL += count
    print(f"   {category}: {count} otázok, {QL_results['correct_count'][category]} správnych, {QL_results['incorrect_count'][category]} nesprávnych")
if total_attempts_QL > 0:
    print(f"Celkový počet otázok: {total_attempts_QL}")
else:
    print("   \nŽiadne otázky neboli položené!")

total_attempts_POMDP = 0
print("\nVýsledky simulácie POMDP tutora:")
for category, count in POMDP_results["question_count"].items():
    total_attempts_POMDP += count
    print(f"   {category}: {count} otázok, {POMDP_results['correct_count'][category]} správnych, {POMDP_results['incorrect_count'][category]} nesprávnych")
if total_attempts_POMDP > 0:
    print(f"Celkový počet otázok: {total_attempts_POMDP}")
else:
    print("   \nŽiadne otázky neboli položené!")  

visualize_results(QL_results, student_question_counts_QL, POMDP_results, student_question_counts_POMDP)     