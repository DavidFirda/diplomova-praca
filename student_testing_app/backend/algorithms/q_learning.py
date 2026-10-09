import random
import json
import csv
import os

from algorithms.storage import save_json

class QLearning:
    def __init__(self, categories, weak_categories=None, alpha=0.1, gamma=0.9, epsilon=0.3, epsilon_decay=0.989, q_table_file="q_table.json", log_file="question_log.csv"):
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

        self.load_q_table()

        if not os.path.exists(self.log_file):
            self.init_log_file()

    def init_log_file(self):
        with open(self.log_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ID_log", "Question_ID", "Category", "Answer", "Old Q-Value", "New Q-Value"])

    def save_q_table(self):
        data = {
            "q_table": self.q_table,
            "incorrect_streak": self.incorrect_streak,
            "category_performance": self.category_performance,
            # epsilon a počítadlá sa ukladajú, aby výber nezávisel od toho, ktorý
            # worker/proces práve odpovedá (selektor sa vytvára pri každom requeste)
            "epsilon": self.epsilon,
            "exploration_count": self.exploration_count,
            "exploitation_count": self.exploitation_count,
        }
        save_json(self.q_table_file, data)

    def reset_q_table(self):
        self.q_table = {category: 0 for category in self.categories}
        self.save_q_table()

    def load_q_table(self):
        try:
            with open(self.q_table_file, "r") as f:
                data = json.load(f)
                self.q_table = data.get("q_table", {c: 0 for c in self.categories})
                self.incorrect_streak = data.get("incorrect_streak", {c: 0 for c in self.categories})
                self.category_performance = data.get("category_performance", {})
                self.epsilon = data.get("epsilon", self.epsilon)
                self.exploration_count = data.get("exploration_count", self.exploration_count)
                self.exploitation_count = data.get("exploitation_count", self.exploitation_count)
        except FileNotFoundError:
            self.reset_q_table()

    def update_q_value(self, question_ID, category, reward, question_order):
        old_q_value = self.q_table[category]
        max_future_q = max([self.q_table[c] for c in self.categories])
        self.q_table[category] += self.alpha * (reward + self.gamma * max_future_q - old_q_value)
        new_q_value = self.q_table[category]

        for cat in self.categories:
            if cat != category:
                self.incorrect_streak[cat] = 0

        correct = reward < 0
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

        print(f"[UPDATE] Category: {category}, Correct: {correct}, Q: {old_q_value:.2f} → {new_q_value:.2f}", flush=True)
        print(f"[STATS] Performance: {self.category_performance[category]}", flush=True)
        print(f"[STREAK] Incorrect streaks: {self.incorrect_streak}", flush=True)

        self.log_interaction(question_order, question_ID, category, "Correct" if correct else "Incorrect", old_q_value, new_q_value)

    def log_interaction(self, question_order, question_id, category, answer, old_q_value, new_q_value):
        with open(self.log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([question_order, question_id, category, answer, old_q_value, new_q_value])

    def select_category(self):
        print("[DEBUG] select_category() called", flush=True)
        for category, streak in self.incorrect_streak.items():
            print(f"[DEBUG] streak for {category}: {streak}", flush=True)
            if streak >= 3:
                strong_categories = [c for c in self.categories if not self.is_weak_category(c)]
                
                if strong_categories:
                    selected_category = random.choice(strong_categories)
                    print(f"[SELECT] 3x wrong in {category} → switching to strong category: {selected_category}", flush=True)
                    self.incorrect_streak[category] = 0
                    self.exploration_count += 1
                    return selected_category
                else:
                    print(f"[SELECT] 3x wrong in {category} but no strong categories available – fallback to normal selection", flush=True)
                    break

        if random.random() < self.epsilon:
            self.exploration_count += 1
            selected_category = random.choice(self.categories)
            print(f"[SELECT] Random (ε={self.epsilon:.3f}): {selected_category}", flush=True)
        else:
            self.exploitation_count += 1
            selected_category = max(self.q_table, key=self.q_table.get)
            print(f"[SELECT] Greedy (ε={self.epsilon:.3f}): {selected_category}", flush=True)

        return selected_category

    def is_weak_category(self, category):
        stats = self.category_performance.get(category, {"correct": 0, "incorrect": 0})
        total_attempts = stats["correct"] + stats["incorrect"]
        if total_attempts == 0:
            return False
        accuracy = stats["correct"] / total_attempts
        is_weak = accuracy < 0.6
        print(f"[CHECK] {category} → accuracy={accuracy:.2%}, weak={is_weak}", flush=True)
        return is_weak

    def reward(self, category, correct):
        weak = self.is_weak_category(category)
        reward_value = -15 if (correct and weak) else -10 if correct else 10 if weak else 5
        print(f"[REWARD] Category: {category}, Correct: {correct}, Weak: {weak}, Reward: {reward_value}", flush=True)
        return reward_value

    def decay_epsilon(self):
        print(f"[EPSILON] Before decay: {self.epsilon:.4f}", flush=True)
        self.epsilon *= self.epsilon_decay
        print(f"[EPSILON] After decay: {self.epsilon:.4f}", flush=True)

    def get_q_table(self):
        return self.q_table

    def get_question_count(self):
        return self.question_count