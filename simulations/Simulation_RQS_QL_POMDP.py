import numpy as np
import random
import matplotlib.pyplot as plt
import pandas as pd
from EFCStudent_model import StudentMemory
from Qlearning import QLearning
from RandomQuestionSelector import RandomQuestionSelector
from POMDP_v3 import BayesianTutorPOMDP


RANDOM_STATE = 987654321 
np.random.seed(RANDOM_STATE)
random.seed(RANDOM_STATE)

def run_random_simulation(num_students, num_iterations):
    dataset = pd.read_csv("dataset_processing/final_dataset.csv")
    #categories = dataset["Category"].unique().tolist()
    categories = ["Data Structures", "Syntax","Sorting","Scientific Computing"]
    weak_categories = ["Scientific Computing","Sorting"]

    results = {
        "question_count": {category: 0 for category in categories},
        "correct_count": {category: 0 for category in categories},
        "incorrect_count": {category: 0 for category in categories},
        "probability_log": {category: [] for category in categories}
    }

    student_question_counts = {student_id: {category: 0 for category in categories} for student_id in range(1, num_students + 1)}
    student_final_probs = {student_id: {category: None for category in categories} for student_id in range(1, num_students + 1)}
    average_probs = {category: [] for category in categories}
    all_students_probabilities = {category: [] for category in categories}

    for student_id in range(1, num_students + 1):
        student = StudentMemory(categories, weak_category=weak_categories)
        tutor = RandomQuestionSelector(categories, weak_categories)

        student_probabilities = {category: [] for category in categories}

        for iteration in range(num_iterations):
            category = tutor.select_random_question()
            filtered_dataset = dataset[dataset["Category"] == category]

            attempts = 0
            while filtered_dataset.empty and attempts < 5:
                category = random.choice(categories)
                filtered_dataset = dataset[dataset["Category"] == category]
                attempts += 1

            if filtered_dataset.empty:
                continue

            row = filtered_dataset.sample(1).iloc[0]
            question_id = row["ID"]

            correct = student.answer_question(category)
            recall_prob = student.memory[category].get_recall_likelihood()
            student_probabilities[category].append(recall_prob)

            results["question_count"][category] += 1
            student_question_counts[student_id][category] += 1
            if correct:
                results["correct_count"][category] += 1
            else:
                results["incorrect_count"][category] += 1

        for category in categories:
            if student_probabilities[category]:
                final_prob = student_probabilities[category][-1]
                student_final_probs[student_id][category] = final_prob
                average_probs[category].append(final_prob)
                all_students_probabilities[category].append(student_probabilities[category])

    for category, student_lists in all_students_probabilities.items():
        if student_lists:
            max_length = max(len(lst) for lst in student_lists)
            padded_data = [
                lst + [lst[-1]] * (max_length - len(lst)) if len(lst) < max_length else lst
                for lst in student_lists
            ]
            results["probability_log"][category] = np.mean(padded_data, axis=0)
        else:
            results["probability_log"][category] = np.zeros(num_iterations)

    return results, student_question_counts, student_final_probs, average_probs, weak_categories
    
def run_ql_simulation(num_students, num_iterations):
    dataset = pd.read_csv("dataset_processing/final_dataset.csv")
    #categories = dataset["Category"].unique().tolist()
    categories = ["Data Structures", "Syntax","Sorting","Scientific Computing"]
    weak_categories = ["Data Structures","Scientific Computing"]

    results = {
        "question_count": {category: 0 for category in categories},
        "correct_count": {category: 0 for category in categories},
        "incorrect_count": {category: 0 for category in categories},
        "probability_log": {category: [] for category in categories}
    }

    student_question_counts = {student_id: {category: 0 for category in categories} for student_id in range(1, num_students + 1)}
    student_final_probs = {student_id: {category: None for category in categories} for student_id in range(1, num_students + 1)}
    average_probs = {category: [] for category in categories}
    all_students_probabilities = {category: [] for category in categories}

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

            results["question_count"][category] += 1
            student_question_counts[student_id][category] += 1
            if correct:
                results["correct_count"][category] += 1
            else:
                results["incorrect_count"][category] += 1

        for category in categories:
            if student_probabilities[category]:
                final_prob = student_probabilities[category][-1]
                student_final_probs[student_id][category] = final_prob
                average_probs[category].append(final_prob)
                all_students_probabilities[category].append(student_probabilities[category])

    for category, student_lists in all_students_probabilities.items():
        if student_lists:
            max_length = max(len(lst) for lst in student_lists)
            padded_data = [
                lst + [lst[-1]] * (max_length - len(lst)) if len(lst) < max_length else lst
                for lst in student_lists
            ]
            results["probability_log"][category] = np.mean(padded_data, axis=0)
        else:
            results["probability_log"][category] = np.zeros(num_iterations)
    
    return results, student_question_counts, student_final_probs, average_probs, weak_categories 

def run_pomdp_simulation(num_students, num_iterations):
    dataset = pd.read_csv("dataset_processing/final_dataset.csv")
    #categories = dataset["Category"].unique().tolist()
    categories = ["Data Structures", "Syntax","Sorting","Scientific Computing"]
    weak_categories = ["Syntax", "Sorting"]

    results = {
        "question_count": {category: 0 for category in categories},
        "correct_count": {category: 0 for category in categories},
        "incorrect_count": {category: 0 for category in categories},
        "probability_log": {category: [] for category in categories}
    }
    
    student_question_counts = {student_id: {category: 0 for category in categories} for student_id in range(1, num_students + 1)}
    student_correct_counts = {student_id: {category: 0 for category in categories} for student_id in range(1, num_students + 1)}
    student_incorrect_counts = {student_id: {category: 0 for category in categories} for student_id in range(1, num_students + 1)}
    
    student_final_probs = {student_id: {category: None for category in categories} for student_id in range(1, num_students + 1)}
    average_probs = {category: [] for category in categories}
    all_students_probabilities = {category: [] for category in categories}

    # Simulácia pre každého študenta
    for student_id in range(1, num_students + 1):
        student_model = StudentMemory(categories, weak_categories)
        #tutor = TutorPOMDPv2(categories)
        tutor = BayesianTutorPOMDP(categories)

        for iteration in range(num_iterations):
            category = tutor.agent.policy_model.sample(tutor.agent.belief).category

            student_question_counts[student_id][category] += 1
            observation, reward = tutor.step(student_model, category)  

            results["question_count"][category] += 1

            if observation.correctness:
                student_correct_counts[student_id][category] += 1
                results["correct_count"][category] += 1
            else:
                student_incorrect_counts[student_id][category] += 1
                results["incorrect_count"][category] += 1

        # Uloženie konečných pravdepodobností študenta pre každú kategóriu
        for category in categories:
            if student_question_counts[student_id][category] > 0 and student_model.probability_log[category]:
                final_prob = student_model.probability_log[category][-1]  
                student_final_probs[student_id][category] = final_prob
                average_probs[category].append(final_prob)
                all_students_probabilities[category].append(student_model.probability_log[category])

    # Výpočet priemernej pravdepodobnosti vývoja správnych odpovedí
    for category, student_lists in all_students_probabilities.items():
        if student_lists:
            max_length = max(len(lst) for lst in student_lists)
            padded_data = [
                lst + [lst[-1]] * (max_length - len(lst)) if len(lst) < max_length else lst
                for lst in student_lists
            ]
            results["probability_log"][category] = np.mean(padded_data, axis=0)
        else:
            results["probability_log"][category] = np.zeros(num_iterations)        

    return results, student_question_counts, student_final_probs, average_probs, weak_categories

def visualize_results(random_results, q_learning_results, pomdp_results,
                      random_student_question_counts, q_student_question_counts, pomdp_student_question_counts, 
                      student_final_probs1,student_final_probs2,student_final_probs3,
                      average_probs1 ,average_probs2 ,average_probs3 ,
                      weak_categories_random ,weak_categories_q_learning ,weak_categories_pomdp):
    categories_Random = list(random_results["question_count"].keys())
    question_counts_Random = list(random_results["question_count"].values())
    correct_answers_Random = list(random_results["correct_count"].values())
    incorrect_answers_Random = list(random_results["incorrect_count"].values())

    categories_QL = list(q_learning_results["question_count"].keys())
    question_counts_QL = list(q_learning_results["question_count"].values())
    correct_answers_QL = list(q_learning_results["correct_count"].values())
    incorrect_answers_QL = list(q_learning_results["incorrect_count"].values())

    categories_POMDP = list(pomdp_results["question_count"].keys())
    question_counts_POMDP = list(pomdp_results["question_count"].values())
    correct_answers_POMDP = list(pomdp_results["correct_count"].values())
    incorrect_answers_POMDP = list(pomdp_results["incorrect_count"].values())

    plt.figure(figsize=(16, 7)) 

    plt.subplot(1, 3, 1)
    bars = plt.bar(categories_Random, question_counts_Random, color="orange", width=0.5)
    plt.xlabel("Kategórie")
    plt.ylabel("Počet otázok")
    plt.title("Počet otázok podľa kategórií - Náhodný výber")
    plt.xticks(rotation=45, ha='right', fontsize=10)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            plt.text(bar.get_x() + bar.get_width()/2, height / 2, str(int(height)),
                    ha='center', va='center', fontsize=10, color='black')

    plt.subplot(1, 3, 2)
    bars = plt.bar(categories_QL, question_counts_QL, color="royalblue", width=0.5)
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

    plt.subplot(1, 3, 3)
    bars = plt.bar(categories_POMDP, question_counts_POMDP, color="royalblue", width=0.5)
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

    plt.figure(figsize=(17, 7))
    plt.subplot(1, 3, 1)
    bar_width = 0.4
    index = np.arange(len(categories_Random))
    bars1 = plt.bar(index, correct_answers_Random, bar_width, label="Správne odpovede", color="green")
    bars2 = plt.bar(index + bar_width, incorrect_answers_Random, bar_width, label="Nesprávne odpovede", color="red")
    plt.xticks(index + bar_width / 2, categories_Random, rotation=45, ha='right', fontsize=10)
    plt.xlabel("Kategórie")
    plt.ylabel("Počet odpovedí")
    plt.title("Úspešnosť odpovedí podľa kategórií - Náhodný výber")
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

    plt.subplot(1, 3, 2)
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
            
    plt.subplot(1, 3, 3)
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

    plt.subplot(1, 3, 1)
    students = list(random_student_question_counts.keys())
    student_labels = np.arange(1, len(students) + 1 )
    question_matrix = np.array([[random_student_question_counts[student][category] for category in categories_Random] for student in students])
    bottom = np.zeros(len(students))  
    colors = plt.get_cmap("tab20").colors  

    bar_width = 0.7
    for idx, category in enumerate(categories_Random):
        bars = plt.bar(student_labels, question_matrix[:, idx], bottom=bottom, label=category, color=colors[idx % 20], width=bar_width)
        
        for bar, count in zip(bars, question_matrix[:, idx]):
            if count > 0: 
                plt.text(bar.get_x() + bar.get_width()/2, bar.get_y() + bar.get_height()/2,  
                        str(int(count)), ha='center', va='center', fontsize=9, color='black')

        bottom += question_matrix[:, idx]  

    plt.xlabel("Študenti")
    plt.ylabel("Otázka")
    plt.title("Počet otázok pre každého študenta \n podľa kategórií - Náhodný výber")
    y_max = np.max(bottom) + 1
    plt.yticks(np.arange(0, y_max, 5), fontsize=12) 
    plt.minorticks_on()
    plt.gca().yaxis.set_minor_locator(plt.MultipleLocator(1))  
    plt.grid(axis='y', linestyle='--', alpha=0.7, which='both')
    plt.xticks(student_labels, student_labels, fontsize=9, rotation=90) 
    plt.xticks(rotation=45)

    plt.subplot(1, 3, 2)
    students = list(q_student_question_counts.keys())
    student_labels = np.arange(1, len(students) + 1 )
    question_matrix = np.array([[q_student_question_counts[student][category] for category in categories_QL] for student in students])
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
    plt.title("Počet otázok pre každého študenta \n podľa kategórií - Q-learning")
    y_max = np.max(bottom) + 1
    plt.yticks(np.arange(0, y_max, 5), fontsize=12) 
    plt.minorticks_on()
    plt.gca().yaxis.set_minor_locator(plt.MultipleLocator(1))  
    plt.grid(axis='y', linestyle='--', alpha=0.7, which='both')
    plt.xticks(student_labels, student_labels, fontsize=9, rotation=90) 
    plt.xticks(rotation=45)
            
    plt.subplot(1, 3, 3)
    students = list(pomdp_student_question_counts.keys())
    student_labels = np.arange(1, len(students) + 1 )
    question_matrix = np.array([[pomdp_student_question_counts[student][category] for category in categories_POMDP] for student in students])
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
    plt.title("Počet otázok pre každého študenta \n podľa kategórií - POMDP")
    y_max = np.max(bottom) + 1
    plt.yticks(np.arange(0, y_max, 5), fontsize=12) 
    plt.minorticks_on()
    plt.gca().yaxis.set_minor_locator(plt.MultipleLocator(1))  
    plt.grid(axis='y', linestyle='--', alpha=0.7, which='both')
    plt.xticks(student_labels, student_labels, fontsize=9, rotation=90) 
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize= 9)
    plt.xticks(rotation=45) 
    plt.tight_layout()
    
    plt.subplots_adjust(right=0.8) 
    weak_categories_text = (
        f"Slabé kategórie pre každú metódu:\n"
        f"  Náhodný výber: {', '.join(weak_categories_random)}\n"
        f"  Q-learning: {', '.join(weak_categories_q_learning)}\n"
        f"  POMDP: {', '.join(weak_categories_pomdp)}"
    )

    plt.figtext(0.81, 0.45, weak_categories_text, fontsize=9, verticalalignment='center')
    plt.show()

    plt.figure(figsize=(15, 7))
    plt.subplot(1, 3, 1)
    weak_category_probs1 = {category: average_probs1[category] for category in weak_categories_random if category in average_probs1}
    avg_probs1 = []
    weak_category_labels1 = []  

    for category, probs in weak_category_probs1.items():
        valid_probs = [p for p in probs if p is not None] 
        if valid_probs:
            avg_prob = np.mean(valid_probs)
        else:
            avg_prob = 0  
        avg_probs1.append(avg_prob)
        weak_category_labels1.append(category)

    bars = plt.bar(weak_category_labels1, avg_probs1, color="red", width=0.4)
    plt.xlabel("Slabé kategórie")
    plt.ylabel("Priemerná pravdepodobnosť správnej odpovede")
    plt.title("Priemerná úspešnosť v slabých \n kategóriách - Náhodný výber")
    plt.ylim(0, 1)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    for bar, prob in zip(bars, avg_probs1):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f"{prob:.2f}",
                 ha='center', va='bottom', fontsize=10, color='black')
        

    plt.subplot(1, 3, 2)  
    weak_category_probs2 = {category: average_probs2[category] for category in weak_categories_q_learning if category in average_probs2}
    avg_probs2 = []
    weak_category_labels2 = []  

    for category, probs in weak_category_probs2.items():
        valid_probs = [p for p in probs if p is not None] 
        if valid_probs:
            avg_prob = np.mean(valid_probs)
        else:
            avg_prob = 0  
        avg_probs2.append(avg_prob)
        weak_category_labels2.append(category)

    bars = plt.bar(weak_category_labels2, avg_probs2, color="purple", width=0.4)
    plt.xlabel("Slabé kategórie")
    plt.ylabel("Priemerná pravdepodobnosť správnej odpovede")
    plt.title("Priemerná úspešnosť v slabých \n kategóriách - Q-learning")
    plt.ylim(0, 1)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    for bar, prob in zip(bars, avg_probs2):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f"{prob:.2f}",
                 ha='center', va='bottom', fontsize=10, color='black')  
        
    plt.subplot(1, 3, 3)  
    weak_category_probs3 = {category: average_probs3[category] for category in weak_categories_pomdp if category in average_probs3}
    avg_probs3 = []
    weak_category_labels3 = []  

    for category, probs in weak_category_probs3.items():
        valid_probs = [p for p in probs if p is not None] 
        if valid_probs:
            avg_prob = np.mean(valid_probs)
        else:
            avg_prob = 0  
        avg_probs3.append(avg_prob)
        weak_category_labels3.append(category)

    bars = plt.bar(weak_category_labels3, avg_probs3, color="orange", width=0.4)
    plt.xlabel("Slabé kategórie")
    plt.ylabel("Priemerná pravdepodobnosť správnej odpovede")
    plt.title("Priemerná úspešnosť v slabých \n kategóriách - POMDP")
    plt.ylim(0, 1)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    for bar, prob in zip(bars, avg_probs3):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f"{prob:.2f}",
                 ha='center', va='bottom', fontsize=10, color='black')  
    plt.show()  

def save_simulation_results_to_excel(results, student_question_counts, student_final_probs, average_probs, QL_results, student_question_counts_QL, average_probs1, student_final_probs1, filename="simulation2_results.xlsx"):
    with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
        results_df = pd.DataFrame.from_dict(results)
        results_df.to_excel(writer, sheet_name="Overall Results P")

        student_question_counts_df = pd.DataFrame.from_dict(student_question_counts, orient="index")
        student_question_counts_df.to_excel(writer, sheet_name="Student Question Counts P")

        student_final_probs_df = pd.DataFrame.from_dict(student_final_probs, orient="index")
        student_final_probs_df.to_excel(writer, sheet_name="Student Final Probabilities P")

        valid_avg_probs = {
            category: (sum(probs) / len(probs)) if probs else None  
            for category, probs in average_probs.items()
        }
        average_probs_df = pd.DataFrame.from_dict(valid_avg_probs, orient="index", columns=["Average Probability"])
        average_probs_df.to_excel(writer, sheet_name="Average Probabilities P")

        results1_df = pd.DataFrame.from_dict(QL_results)
        results1_df.to_excel(writer, sheet_name="Overall Results Q")

        student_question_counts1_df = pd.DataFrame.from_dict(student_question_counts_QL, orient="index")
        student_question_counts1_df.to_excel(writer, sheet_name="Student Question Counts Q")

        student_final_probs1_df = pd.DataFrame.from_dict(student_final_probs1, orient="index")
        student_final_probs1_df.to_excel(writer, sheet_name="Student Final Probabilities Q")

        valid_avg_probs1 = {
            category: (sum(probs) / len(probs)) if probs else None  
            for category, probs in average_probs1.items()
        }
        average_probs_df = pd.DataFrame.from_dict(valid_avg_probs1, orient="index", columns=["Average Probability"])
        average_probs_df.to_excel(writer, sheet_name="Average Probabilities Q")

    return f"✅ Dáta boli úspešne uložené do súboru: {filename}"    

num_students = 25
num_iterations = 30

random_results, random_student_question_counts, student_final_probs1, average_probs1 , weak_categories_random = run_random_simulation(num_students, num_iterations)
q_learning_results, q_student_question_counts,student_final_probs2, average_probs2 , weak_categories_q_learning = run_ql_simulation(num_students, num_iterations)
pomdp_results, pomdp_student_question_counts,student_final_probs3, average_probs3, weak_categories_pomdp = run_pomdp_simulation(num_students, num_iterations)

total_attempts_random = 0
print("\nVýsledky simulácie Náhodného výberu:")
for category, count in random_results["question_count"].items():
    total_attempts_random += count
    print(f"   {category}: {count} otázok, {random_results['correct_count'][category]} správnych, {random_results['incorrect_count'][category]} nesprávnych")
if total_attempts_random > 0:
    print(f"Celkový počet otázok: {total_attempts_random}")
else:
    print("   \nŽiadne otázky neboli položené!")

total_attempts_QL = 0
print("\nVýsledky simulácie Q-learning tutora:")
for category, count in q_learning_results["question_count"].items():
    total_attempts_QL += count
    print(f"   {category}: {count} otázok, {q_learning_results['correct_count'][category]} správnych, {q_learning_results['incorrect_count'][category]} nesprávnych")
if total_attempts_QL > 0:
    print(f"   Celkový počet otázok: {total_attempts_QL}")
else:
    print("   \nŽiadne otázky neboli položené!")

total_attempts_POMDP = 0
print("\nVýsledky simulácie POMDP tutora:")
for category, count in pomdp_results["question_count"].items():
    total_attempts_POMDP += count
    print(f"   {category}: {count} otázok, {pomdp_results['correct_count'][category]} správnych, {pomdp_results['incorrect_count'][category]} nesprávnych")
if total_attempts_POMDP > 0:
    print(f"Celkový počet otázok: {total_attempts_POMDP}")
else:
    print("   \nŽiadne otázky neboli položené!")  

visualize_results(random_results, q_learning_results, pomdp_results, 
                  random_student_question_counts, q_student_question_counts, pomdp_student_question_counts,
                  student_final_probs1,student_final_probs2,student_final_probs3,
                  average_probs1 ,average_probs2 ,average_probs3 ,
                  weak_categories_random ,weak_categories_q_learning ,weak_categories_pomdp)

save_simulation_results_to_excel(pomdp_results, pomdp_student_question_counts, q_student_question_counts, average_probs2 , student_final_probs2, student_final_probs3, average_probs3, q_learning_results)