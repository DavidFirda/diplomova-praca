import random
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from EFCStudent_model import StudentMemory
from Qlearning import QLearning
#from POMDP import TutorPOMDP
from POMDP_v3 import BayesianTutorPOMDP
#from POMDP_v2 import TutorPOMDPv2

RANDOM_STATE = 82
np.random.seed(RANDOM_STATE)
random.seed(RANDOM_STATE) 

def run_ql_simulation(num_students, num_iterations):
    dataset = pd.read_csv("dataset_processing/final_dataset.csv")
    categories = dataset["Category"].unique().tolist()
    weak_categories = ["Data Analysis", "Testing and Debugging"]

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
    
    # Výpis pravdepodobností
    print("\n📊 Pravdepodobnosti správnych odpovedí pre slabé kategórie:")
    for student_id, probs in student_final_probs.items():
        print(f"\n🧑‍🎓 Študent {student_id}:")
        for category, prob in probs.items():
            if prob is not None:
                print(f"  - {category}: {prob:.2f}")
            else:
                print(f"  - {category}: N/A (žiaden pokus)")

    print("\n📊 Priemerná pravdepodobnosť správnych odpovedí v slabých kategóriách:")
    for category, probs in average_probs.items():
        valid_probs = [p for p in probs if p is not None]
        if valid_probs:
            avg_prob = sum(valid_probs) / len(valid_probs)
            print(f"  - {category}: {avg_prob:.2f}")
        else:
            print(f"  - {category}: N/A (žiaden pokus)")
    
    return results, student_question_counts, student_final_probs, average_probs, weak_categories

def run_pomdp_simulation(num_students, num_iterations):
    dataset = pd.read_csv("dataset_processing/final_dataset.csv")
    categories = dataset["Category"].unique().tolist()
    #weak_categories = ["Data Analysis", "Sorting"]
    weak_categories = ["Loops", "Sorting"]
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

        #print(f"\n🎓 Študent {student_id} začína simuláciu...\n")

        for iteration in range(num_iterations):
            category = tutor.agent.policy_model.sample(tutor.agent.belief).category
            #print(f"🔄 Iterácia {iteration + 1}: Tutor kladie otázku na {category}") 

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

def visualize_results(QL_results, student_question_counts_QL, POMDP_results, student_question_counts_POMDP,student_final_probs, average_probs, weak_categories, average_probs1, weak_categories1, student_final_probs1):
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
    weak_category_probs1 = {category: average_probs1[category] for category in weak_categories1 if category in average_probs1}
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

    bars = plt.bar(weak_category_labels1, avg_probs1, color="red")
    plt.xlabel("Slabé kategórie")
    plt.ylabel("Priemerná pravdepodobnosť správnej odpovede Q")
    plt.title("Priemerná úspešnosť v slabých kategóriách")
    plt.ylim(0, 1)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    for bar, prob in zip(bars, avg_probs1):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f"{prob:.2f}",
                 ha='center', va='bottom', fontsize=10, color='black')
        

    plt.subplot(1, 2, 2)  
    weak_category_probs = {category: average_probs[category] for category in weak_categories if category in average_probs}
    avg_probs = []
    weak_category_labels = []  

    for category, probs in weak_category_probs.items():
        valid_probs = [p for p in probs if p is not None] 
        if valid_probs:
            avg_prob = np.mean(valid_probs)
        else:
            avg_prob = 0  
        avg_probs.append(avg_prob)
        weak_category_labels.append(category)

    bars = plt.bar(weak_category_labels, avg_probs, color="purple")
    plt.xlabel("Slabé kategórie")
    plt.ylabel("Priemerná pravdepodobnosť správnej odpovede")
    plt.title("Priemerná úspešnosť v slabých kategóriách")
    plt.ylim(0, 1)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    for bar, prob in zip(bars, avg_probs):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f"{prob:.2f}",
                 ha='center', va='bottom', fontsize=10, color='black')  
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

def save_simulation_results_to_excel(results, student_question_counts, student_final_probs, average_probs, QL_results, student_question_counts_QL, average_probs1, student_final_probs1, filename="simulation_results.xlsx"):
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

num_students=25
num_iterations=30
QL_results, student_question_counts_QL, student_final_probs1, average_probs1, weak_categories1 = run_ql_simulation(num_students, num_iterations)
POMDP_results, student_question_counts_POMDP, student_final_probs, average_probs, weak_categories = run_pomdp_simulation(num_students, num_iterations)

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

visualize_results(QL_results, student_question_counts_QL, POMDP_results, student_question_counts_POMDP, student_final_probs, average_probs, weak_categories, average_probs1, weak_categories1, student_final_probs1)
save_simulation_results_to_excel(POMDP_results, student_question_counts_POMDP, student_final_probs, average_probs, QL_results, student_question_counts_QL, average_probs1, student_final_probs1)      