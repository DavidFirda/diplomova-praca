from matplotlib import pyplot as plt
import pandas as pd
import pomdp_py
import random
import numpy as np
from EFCStudent_model import StudentMemory
from POMDP import TutorPOMDP
from POMDP_v2 import TutorPOMDPv2
from POMDP_v3 import BayesianTutorPOMDP

RANDOM_STATE = 82
np.random.seed(RANDOM_STATE)
random.seed(RANDOM_STATE)

def run_pomdp_simulation1(num_students, num_iterations):
    dataset = pd.read_csv("dataset_processing/final_dataset.csv")
    categories = dataset["Category"].unique().tolist()
    weak_categories = ["Data Analysis", "Sorting"]

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
        tutor = TutorPOMDP(categories)

        print(f"\n🎓 Študent {student_id} začína simuláciu...\n")

        for iteration in range(num_iterations):
            category = tutor.agent.policy_model.sample(tutor.agent.belief).category
            print(f"🔄 Iterácia {iteration + 1}: Tutor kladie otázku na {category}") 

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

    return results, average_probs, weak_categories

def run_pomdp_simulation2(num_students, num_iterations):
    dataset = pd.read_csv("dataset_processing/final_dataset.csv")
    categories = dataset["Category"].unique().tolist()
    weak_categories = ["Data Analysis", "Sorting"]

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
        tutor = TutorPOMDPv2(categories)

        print(f"\n🎓 Študent {student_id} začína simuláciu...\n")

        for iteration in range(num_iterations):
            category = tutor.agent.policy_model.sample(tutor.agent.belief).category
            print(f"🔄 Iterácia {iteration + 1}: Tutor kladie otázku na {category}") 

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

    return results, average_probs, weak_categories

def run_pomdp_simulation3(num_students, num_iterations):
    dataset = pd.read_csv("dataset_processing/final_dataset.csv")
    categories = dataset["Category"].unique().tolist()
    weak_categories = ["Data Analysis", "Sorting"]

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
        tutor = BayesianTutorPOMDP(categories)

        print(f"\n🎓 Študent {student_id} začína simuláciu...\n")

        for iteration in range(num_iterations):
            category = tutor.agent.policy_model.sample(tutor.agent.belief).category
            print(f"🔄 Iterácia {iteration + 1}: Tutor kladie otázku na {category}") 

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

    return results, average_probs, weak_categories

def visualize_updated_results(results1, average_probs1, weak_categories1,
                                results2, average_probs2, weak_categories2,
                              results3, average_probs3, weak_categories3):
    categories1 = list(results1["question_count"].keys())
    correct_answers1 = list(results1["correct_count"].values())
    incorrect_answers1 = list(results1["incorrect_count"].values())
    
    categories2 = list(results2["question_count"].keys())
    correct_answers2 = list(results2["correct_count"].values())
    incorrect_answers2 = list(results2["incorrect_count"].values())
    
    categories3 = list(results3["question_count"].keys())
    correct_answers3 = list(results3["correct_count"].values())
    incorrect_answers3 = list(results3["incorrect_count"].values())
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    bar_width = 0.4
    
    datasets = [
        (categories1, results1["question_count"].values(), correct_answers1, incorrect_answers1, "v1"),
        (categories2, results2["question_count"].values(), correct_answers2, incorrect_answers2, "v2"),
        (categories3, results3["question_count"].values(), correct_answers3, incorrect_answers3, "v3"),
    ]
    
    for i, (categories, question_counts, correct_answers, incorrect_answers, version) in enumerate(datasets):
        index = np.arange(len(categories))
        
        # Počet otázok podľa kategórií
        ax1 = axes[0, i]
        bars = ax1.bar(categories, question_counts, color="royalblue")
        ax1.set_xlabel("Kategórie")
        ax1.set_ylabel("Počet otázok")
        ax1.set_title(f"Počet otázok podľa kategórií {version}")
        ax1.set_xticks(index)
        ax1.set_xticklabels(categories, rotation=45, ha='right', fontsize=10)
        ax1.grid(axis='y', linestyle='--', alpha=0.7)
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax1.text(bar.get_x() + bar.get_width()/2, height / 2, str(int(height)), ha='center', va='center', fontsize=10, color='black')
        
        # Úspešnosť odpovedí podľa kategórií
        ax2 = axes[1, i]
        bars1 = ax2.bar(index, correct_answers, bar_width, label="Správne odpovede", color="green")
        bars2 = ax2.bar(index + bar_width, incorrect_answers, bar_width, label="Nesprávne odpovede", color="red")
        
        ax2.set_xticks(index + bar_width / 2)
        ax2.set_xticklabels(categories, rotation=45, ha='right', fontsize=10)
        ax2.set_xlabel("Kategórie")
        ax2.set_ylabel("Počet odpovedí")
        ax2.set_title(f"Úspešnosť odpovedí podľa kategórií {version}")
        ax2.legend()
        ax2.grid(axis='y', linestyle='--', alpha=0.7)
        
        for bar in bars1 + bars2:
            height = bar.get_height()
            if height > 0:
                ax2.text(bar.get_x() + bar.get_width()/2, height / 2, str(int(height)), ha='center', va='center', fontsize=10, color='black')
    
    plt.tight_layout()
    plt.show()

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    datasets = [
        (average_probs1, weak_categories1, "v1"),
        (average_probs2, weak_categories2, "v2"),
        (average_probs3, weak_categories3, "v3"),
    ]
    
    for i, (average_probs, weak_categories, version) in enumerate(datasets):
        weak_category_probs = {category: average_probs[category] for category in weak_categories if category in average_probs}
        avg_probs = []
        weak_category_labels = []  
        
        for category, probs in weak_category_probs.items():
            valid_probs = [p for p in probs if p is not None] 
            avg_prob = np.mean(valid_probs) if valid_probs else 0  
            avg_probs.append(avg_prob)
            weak_category_labels.append(category)
        
        bars = axes[i].bar(weak_category_labels, avg_probs, color="purple")
        axes[i].set_xlabel("Slabé kategórie")
        axes[i].set_ylabel("Priemerná pravdepodobnosť správnej odpovede")
        axes[i].set_title(f"Priemerná úspešnosť v slabých kategóriách {version}")
        axes[i].set_ylim(0, 1)
        axes[i].grid(axis='y', linestyle='--', alpha=0.7)
        
        for bar, prob in zip(bars, avg_probs):
            axes[i].text(bar.get_x() + bar.get_width()/2, bar.get_height(), f"{prob:.2f}",
                         ha='center', va='bottom', fontsize=10, color='black')
    
    plt.tight_layout()
    plt.show()  

num_students = 25
num_iterations = 30
pomdp_results1, average_probs1, weak_categories1 = run_pomdp_simulation1(num_students, num_iterations)
pomdp_results2, average_probs2, weak_categories2 = run_pomdp_simulation2(num_students, num_iterations)
pomdp_results3, average_probs3, weak_categories3 = run_pomdp_simulation3(num_students, num_iterations)
visualize_updated_results(pomdp_results1, average_probs1, weak_categories1,
                          pomdp_results2, average_probs2, weak_categories2,
                          pomdp_results3, average_probs3, weak_categories3)