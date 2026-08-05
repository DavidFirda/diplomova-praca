import random
import json
import csv

class QLearning:
    def __init__(self, categories, weak_categories=None, alpha=0.1, gamma=0.9, epsilon=0.3, epsilon_decay=0.989, q_table_file="q_table.json", log_file="question_log.csv"):
        """
        categories: Slovník kategórií
        alpha: Miera učenia (learning rate), ako rýchlo sa Q-hodnoty prispôsobujú
        gamma: Diskontný faktor (discount factor), určuje význam budúcich odmien (medzi 0 a 1)
        epsilon: Pravdepodobnosť explorácie (náhodného výberu kategórie) v epsilon-greedy stratégii
        epsilon_decay: Faktor znižovania epsilon, ktorý určuje, ako rýchlo explorácia klesá s každou iteráciou
        q_table_file: Názov súboru pre uloženie Q-tabulky
        log_file: Názov súboru, kde sa budú zaznamenávať otázky, odpovede a zmeny Q-hodnôt
        """

        self.categories = list(categories)
        self.weak_categories = set(weak_categories) if weak_categories else set()

        self.q_table = {category: 0 for category in self.categories}
        self.correct_count = {category: 0 for category in self.categories}
        self.incorrect_count = {category: 0 for category in self.categories}
        self.incorrect_streak = {category: 0 for category in self.categories}  
        self.question_count = {category: 0 for category in self.categories}
        self.category_performance = {}  
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.q_table_file = q_table_file
        self.log_file = log_file
        self.exploration_count = 0  
        self.exploitation_count = 0 
        self.reset_q_table()
        self.init_log_file()

    def init_log_file(self):
        with open(self.log_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ID_log","Question_ID", "Category", "Answer", "Old Q-Value", "New Q-Value"])

    def save_q_table(self):
        with open(self.q_table_file, "w") as f:
            json.dump(self.q_table, f)

    def reset_q_table(self):
        self.q_table = {category: 0 for category in self.categories}
        self.save_q_table()

    def load_q_table(self):
        try:
            with open(self.q_table_file, "r") as f:
                self.q_table = json.load(f)
        except FileNotFoundError:
            self.reset_q_table()

    def update_q_value(self, question_ID, category, reward, question_order):
        old_q_value = self.q_table[category]
        max_future_q = max([self.q_table[c] for c in self.categories])  
        self.q_table[category] += self.alpha * (reward + self.gamma * max_future_q - old_q_value)
        new_q_value = self.q_table[category]

        correct = reward < 0  # Správna odpoveď = záporný reward
        if correct:
            self.correct_count[category] += 1
            self.incorrect_streak[category] = 0  
        else:
            self.incorrect_count[category] += 1
            self.incorrect_streak[category] += 1 

        self.question_count[category] += 1

        if category not in self.category_performance:
            self.category_performance[category] = {"correct": 0, "incorrect": 0}

        if correct:
            self.category_performance[category]["correct"] += 1
        else:
            self.category_performance[category]["incorrect"] += 1

        self.log_interaction(question_order, question_ID, category, "Correct" if correct else "Incorrect", old_q_value, new_q_value)

    def log_interaction(self, question_order, question_id, category, answer, old_q_value, new_q_value):
        with open(self.log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([question_order, question_id, category, answer, old_q_value, new_q_value])

    def select_category(self):
        """
        Použitá stratégia je epsilon-greedy, ale ak v kategórii boli 3 nesprávne odpovede za sebou,
        zvolíme kategóriu, ktorú študent ovláda najlepšie (najvyššia Q-hodnota).
        """
        for category, streak in self.incorrect_streak.items():
            if streak >= 3: 
                strong_categories = [c for c in self.categories if not self.is_weak_category(c)]
                
                if strong_categories: 
                    selected_category = random.choice(strong_categories)
                    print(f"Študent má 3 nesprávne odpovede v kategórii {category}. Prepíname na {selected_category}.")
                    self.incorrect_streak[category] = 0  
                    self.exploration_count += 1
                    return selected_category
            
        if random.random() < self.epsilon:
            self.exploration_count += 1
            selected_category = random.choice(self.categories)  # Náhodný výber (exploration)
        else:
            self.exploitation_count += 1
            selected_category = max(self.q_table, key=self.q_table.get)  # Vyberieme kategóriu s najvyššou Q-hodnotou (exploitation)

        return selected_category
    
    def is_weak_category(self, category):
        """
        Dynamicky určuje, či je kategória slabá (pod 60 % úspešnosť).
        """
        stats = self.category_performance.get(category, {"correct": 0, "incorrect": 0})
        total_attempts = stats["correct"] + stats["incorrect"]

        if total_attempts == 0:
            #print(f"[INFO] Kategória '{category}' nemá zatiaľ žiadne pokusy. Nie je označená ako slabá.")
            return False  

        accuracy = stats["correct"] / total_attempts
        is_weak = accuracy < 0.6

        #print(f"[DEBUG] Kategória: {category}, Správne: {stats['correct']}, Nesprávne: {stats['incorrect']}, "
        #    f"Úspešnosť: {accuracy:.2%}, Slabá: {is_weak}")
        return is_weak
    
    def reward(self, category, correct):
        """
        Priradí odmenu podľa správnosti odpovede a slabých kategórií.
        Správna odpoveď má záporný reward, nesprávna odpoveď kladný.
        """
        weak = self.is_weak_category(category)

        if correct:
            return -15 if weak else -10 
        else:
            return 10 if weak else 5
    
    def decay_epsilon(self):
        self.epsilon *= self.epsilon_decay

    def get_q_table(self):
        return self.q_table
    
    def get_question_count(self):
        return self.question_count 
    
    
